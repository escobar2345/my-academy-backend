"""
BOI RSU — Web bridge to the AI learning system
==============================================
Makes the CLI-only pipeline in `ai_learning_system_v4 (14).py` usable from a
browser, and joins it to the student records in `boirsu.py`.

Why this file exists:
  * That script's filename contains spaces and parentheses, so it cannot be
    `import`ed — it has to be loaded by path via importlib.
  * Its entry points (`main`, `class_mode`, `learning_menu`) block on `input()`
    and play narration through mpg123 on the *server*. None of that can be
    reached from a web request, so we call only the pure functions and
    re-implement the two pieces that were terminal-bound: quizzes as structured
    JSON, and TTS as bytes streamed to the browser.

Everything here is safe to call from a Flask request handler.

Never call from the web layer:
  main() / class_mode() / class_mode_resume() / learning_menu()  -> block on input()
  speak_text()                                                   -> plays audio on the server
  _generate_pdf_for_course()                                     -> shells out to a
      hardcoded C:/Users/Admin/Downloads/generate_lesson_pdf.py that isn't there,
      with check=False, so it fails silently. PDFs are built in the browser instead.
"""

import os
import re
import sys
import json
import time
import uuid
import threading
import importlib.util
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

# The AI script narrates its progress with emoji and box-drawing characters
# (section("🔬 PHASE 1 — DEEP INTERNET RESEARCH") and friends). Under Flask on
# Windows stdout is cp1252, so the first of those prints raises
# UnicodeEncodeError and kills the generation thread ~10% in. Widen the console
# encoding once, here, instead of stripping the prints out of that script.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass  # not a TextIOWrapper (pytest capture, embedded interpreter, ...)

import boirsu  # career roadmaps, student records, canned quizzes

AI_SCRIPT_NAME = "ai_learning_system_v4 (14).py"
AI_SCRIPT_PATH = os.path.join(HERE, AI_SCRIPT_NAME)

# Where generated courses, cached audio and per-section video JSON live.
STORE_DIR = boirsu.BASE_DIR / "ai"
COURSES_FILE = STORE_DIR / "ai_courses.json"
AUDIO_DIR = STORE_DIR / "audio"
VIDEO_DIR = STORE_DIR / "videos"

DEEPGRAM_SPEAK_URL = "https://api.deepgram.com/v1/speak"
DEEPGRAM_CHUNK_CHARS = 3000  # Deepgram's per-request character ceiling

_HUES = ("teal", "amber", "coral", "sky")


# ------------------------------------------------------------------
# Module loading — by path, because of the spaces in the filename
# ------------------------------------------------------------------
_ai_mod = None
_ai_err = None
_mod_lock = threading.Lock()


def ai_module():
    """
    Load `ai_learning_system_v4 (14).py` once and cache it.

    Import-time side effects are benign: an auto-pip loop over deps that are
    already installed, colorama.init(), and load_env_file() — which uses
    os.environ.setdefault, so it never clobbers an existing key.
    """
    global _ai_mod, _ai_err
    if _ai_mod is not None:
        return _ai_mod
    with _mod_lock:
        if _ai_mod is not None:
            return _ai_mod
        if _ai_err is not None:
            raise RuntimeError(_ai_err)
        if not os.path.exists(AI_SCRIPT_PATH):
            _ai_err = f"AI script not found at {AI_SCRIPT_PATH}"
            raise RuntimeError(_ai_err)
        try:
            spec = importlib.util.spec_from_file_location("ai_learning_v4", AI_SCRIPT_PATH)
            mod = importlib.util.module_from_spec(spec)
            # Registered before exec so any self-reference inside resolves.
            sys.modules["ai_learning_v4"] = mod
            spec.loader.exec_module(mod)
        except Exception as exc:
            _ai_err = f"failed to load AI script: {exc}"
            sys.modules.pop("ai_learning_v4", None)
            raise RuntimeError(_ai_err) from exc
        _ai_mod = mod
        return _ai_mod


_client = None
_client_lock = threading.Lock()


def client():
    """Cached NVIDIA Build client — setup_ai() once, not per request."""
    global _client
    if _client is not None:
        return _client
    with _client_lock:
        if _client is None:
            _client = ai_module().setup_ai()
    return _client


def ai_key_ready() -> bool:
    try:
        return bool(ai_module().NVIDIA_KEY)
    except Exception:
        return False


def deepgram_ready() -> bool:
    """Deepgram key present? Read live so a newly-added key works on reload."""
    key = os.environ.get("DEEPGRAM_API_KEY", "")
    if not key:
        try:
            key = ai_module().DEEPGRAM_KEY
        except Exception:
            key = ""
    return bool(key)


def _deepgram_key() -> str:
    key = os.environ.get("DEEPGRAM_API_KEY", "")
    if key:
        return key
    try:
        return ai_module().DEEPGRAM_KEY or ""
    except Exception:
        return ""


def youtube_ready() -> bool:
    """Is Apify configured for live YouTube discovery?"""
    key = os.environ.get("APIFY_TOKEN", "")
    if not key:
        try:
            key = ai_module().APIFY_TOKEN
        except Exception:
            key = ""
    return bool(key)


def _deepgram_voice() -> str:
    voice = os.environ.get("DEEPGRAM_VOICE", "")
    if voice:
        return voice
    try:
        # The AI script and boirsu.py disagree (aura-2-thalia-en vs
        # aura-orion-en); the teaching voice from the AI script wins.
        return ai_module().DEEPGRAM_VOICE
    except Exception:
        return "aura-2-thalia-en"


def _is_ai_error(text) -> bool:
    """ai() returns '[Nemotron-3-Super error: ...]' instead of raising."""
    return isinstance(text, str) and text.lstrip().startswith("[Nemotron-3-Super error")


# ------------------------------------------------------------------
# Course store — same on-disk pattern as roadmap_progress.json
# ------------------------------------------------------------------
_store_lock = threading.Lock()


def _ensure_dirs():
    for d in (STORE_DIR, AUDIO_DIR, VIDEO_DIR):
        os.makedirs(d, exist_ok=True)


def _load_store() -> dict:
    _ensure_dirs()
    if not os.path.exists(COURSES_FILE):
        return {"courses": {}, "quizzes": {}}
    try:
        with open(COURSES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {"courses": {}, "quizzes": {}}
    data.setdefault("courses", {})
    data.setdefault("quizzes", {})
    return data


def _save_store(data: dict):
    _ensure_dirs()
    tmp = str(COURSES_FILE) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, COURSES_FILE)


def _mutate(fn):
    """Read-modify-write the store under a lock. fn(data) -> return value."""
    with _store_lock:
        data = _load_store()
        result = fn(data)
        _save_store(data)
        return result


def _read(fn):
    with _store_lock:
        return fn(_load_store())


# ------------------------------------------------------------------
# Shaping for the dashboard
# ------------------------------------------------------------------
def _date_label(when=None) -> str:
    """'Aug 5, 2026' — matches the dashboard's existing `updated` strings.
    Built by hand because %-d is not portable to Windows."""
    when = when or datetime.now()
    return f"{when.strftime('%b')} {when.day}, {when.year}"


def _initials(title: str) -> str:
    words = [w for w in re.split(r"[^A-Za-z0-9]+", title or "") if w]
    if not words:
        return "AI"
    if len(words) == 1:
        return words[0][:2].upper()
    return (words[0][0] + words[1][0]).upper()


def _hue_for(course_id: str) -> str:
    return _HUES[sum(ord(c) for c in course_id) % len(_HUES)]


def library_row(course: dict) -> dict:
    """
    Shape a course the way studentdashboard.vue's `docs` entries look, so the
    Library template needs no restructuring:
      { id, title, tag, pages, size, updated, hue, big }
    """
    sections = course.get("sections") or []
    words = sum(int(s.get("word_count") or 0) for s in sections)
    return {
        "id": course.get("id"),
        "title": course.get("title") or course.get("topic") or "Untitled course",
        "tag": "Notes",
        "pages": len(sections),
        "size": f"{max(words / 500.0, 0.1):.1f} MB" if words else "0.1 MB",
        "updated": course.get("updated_label") or "",
        "hue": course.get("hue") or _hue_for(course.get("id", "")),
        "big": _initials(course.get("topic") or course.get("title") or ""),
        "ai": True,
        "topic": course.get("topic"),
        "sections": len(sections),
        "minutes": sum(int(s.get("duration") or 0) for s in sections),
    }


def list_courses() -> list:
    courses = _read(lambda d: list(d["courses"].values()))
    courses.sort(key=lambda c: c.get("created", ""), reverse=True)
    return [library_row(c) for c in courses if c.get("status") == "ready"]


def get_course(course_id: str, include_content: bool = True) -> dict:
    course = _read(lambda d: d["courses"].get(course_id))
    if not course:
        return None
    out = dict(course)
    out["row"] = library_row(course)
    if not include_content:
        out["sections"] = [
            {k: v for k, v in s.items() if k != "content"} for s in course.get("sections", [])
        ]
    return out


def get_section(course_id: str, section_num: int) -> tuple:
    """Returns (course, section) or (None, None)."""
    course = _read(lambda d: d["courses"].get(course_id))
    if not course:
        return None, None
    for s in course.get("sections", []):
        if int(s.get("section_num") or 0) == int(section_num):
            return course, s
    return course, None


# ------------------------------------------------------------------
# Course generation — background job, because this takes minutes
# ------------------------------------------------------------------
_jobs = {}
_jobs_lock = threading.Lock()


def _set_job(job_id: str, **fields):
    with _jobs_lock:
        job = _jobs.setdefault(job_id, {"job_id": job_id})
        job.update(fields)
        return dict(job)


def get_job(job_id: str) -> dict:
    with _jobs_lock:
        job = _jobs.get(job_id)
        return dict(job) if job else None


def start_course_job(topic: str, level: str = "beginner", on_progress=None) -> str:
    """
    Kick off generation on a background thread and return a job id immediately.
    on_progress(event, payload) is called at each phase so the API layer can
    push SSE without this module knowing anything about Flask.
    """
    job_id = "job_" + uuid.uuid4().hex[:12]
    course_id = "ai_" + uuid.uuid4().hex[:10]
    _set_job(job_id, status="queued", step="Queued", pct=0,
             topic=topic, course_id=course_id, error=None)

    def emit(event, **payload):
        payload.setdefault("job_id", job_id)
        payload.setdefault("course_id", course_id)
        if on_progress:
            try:
                on_progress(event, payload)
            except Exception:
                pass

    def step(pct, text):
        _set_job(job_id, status="running", step=text, pct=pct)
        emit("ai_course_progress", step=text, pct=pct, topic=topic)

    def run():
        try:
            step(4, "Loading AI engine")
            mod = ai_module()
            cl = client()

            step(10, "Researching the topic across the web")
            notes = mod.deep_research(topic, cl)
            if _is_ai_error(notes):
                raise RuntimeError(notes)
            if not (notes or "").strip():
                raise RuntimeError("research returned nothing — check APIFY_TOKEN")

            step(40, "Writing the lesson sections")
            sections = mod.build_course(topic, notes, cl)
            if not sections:
                raise RuntimeError("course builder returned no sections")
            bad = [s for s in sections if _is_ai_error(s.get("content"))]
            if len(bad) == len(sections):
                raise RuntimeError(str(sections[0].get("content"))[:200])

            step(80, "Finding teaching videos")
            sections = _attach_videos(topic, sections, level)

            for s in sections:
                s.setdefault("summary", None)
                s.setdefault("quiz_id", None)

            step(94, "Saving your course")
            title = f"{topic} — Complete Course"
            record = {
                "id": course_id,
                "topic": topic,
                "title": title,
                "level": level,
                "status": "ready",
                "created": datetime.now().isoformat(),
                "updated_label": _date_label(),
                "hue": _hue_for(course_id),
                "research_chars": len(notes or ""),
                "sections": sections,
            }
            _mutate(lambda d: d["courses"].__setitem__(course_id, record))

            _set_job(job_id, status="done", step="Ready", pct=100)
            emit("ai_course_done", course=library_row(record), sections=len(sections))

            # The course is usable now; quizzes keep building behind it so the
            # reader's Quiz tab is a cache hit instead of a 4-minute wait.
            warm_quizzes(course_id)
        except Exception as exc:
            msg = str(exc)[:400] or exc.__class__.__name__
            _set_job(job_id, status="error", step="Failed", error=msg)
            emit("ai_course_error", error=msg, topic=topic)

    threading.Thread(target=run, name=f"ai-course-{job_id}", daemon=True).start()
    return job_id


def _attach_videos(topic: str, sections: list, level: str = "beginner") -> list:
    """
    Attach ranked teaching videos via youtube.enrich_course_with_videos.
    output_dir is passed explicitly — it defaults to 'output/videos' relative
    to the process cwd, which would scatter files wherever Flask was started.
    """
    try:
        from youtube import enrich_course_with_videos
    except Exception:
        for s in sections:
            s.setdefault("videos", [])
        return sections
    try:
        _ensure_dirs()
        return enrich_course_with_videos(
            topic, sections,
            output_dir=str(VIDEO_DIR),
            student_level=level or "beginner",
            course_context=topic,
        )
    except Exception:
        for s in sections:
            s.setdefault("videos", [])
        return sections


def course_videos(topic: str, level: str = "beginner", limit: int = 3) -> list:
    """Standalone video lookup for the dashboard (youtube.py:880)."""
    try:
        from youtube import get_boi_course_videos
    except Exception:
        return []
    try:
        return get_boi_course_videos(topic, max_results=limit, student_level=level or "beginner") or []
    except Exception:
        return []


# ------------------------------------------------------------------
# Per-section extras — summary, resources
# ------------------------------------------------------------------
def section_summary(course_id: str, section_num: int) -> str:
    course, sec = get_section(course_id, section_num)
    if not sec:
        return None
    if sec.get("summary"):
        return sec["summary"]
    text = ai_module().ai_summary(client(), sec.get("content", ""), sec.get("title", ""))
    if _is_ai_error(text):
        return None

    def _store(d):
        c = d["courses"].get(course_id)
        if not c:
            return
        for s in c.get("sections", []):
            if int(s.get("section_num") or 0) == int(section_num):
                s["summary"] = text

    _mutate(_store)
    return text


def section_resources(course_id: str, section_num: int) -> dict:
    """
    Apify-backed reading list. If Apify is not configured, return an empty
    list plus a reason rather than failing.
    """
    course, sec = get_section(course_id, section_num)
    if not sec:
        return None
    mod = ai_module()
    if not getattr(mod, "APIFY_TOKEN", ""):
        return {"resources": [], "explanation": "", "reason": "APIFY_TOKEN not set"}
    if sec.get("resources") is not None:
        return {"resources": sec["resources"], "explanation": sec.get("resources_note", "")}
    try:
        resources = mod.find_learning_resources(
            course.get("topic", ""), sec.get("title", ""), course.get("level", "beginner")
        ) or []
    except Exception as exc:
        return {"resources": [], "explanation": "", "reason": str(exc)[:200]}
    note = ""
    if resources:
        note = mod.explain_learning_resources(
            client(), course.get("topic", ""), sec.get("title", ""), resources
        )
        if _is_ai_error(note):
            note = ""

    def _store(d):
        c = d["courses"].get(course_id)
        if not c:
            return
        for s in c.get("sections", []):
            if int(s.get("section_num") or 0) == int(section_num):
                s["resources"] = resources
                s["resources_note"] = note

    _mutate(_store)
    return {"resources": resources, "explanation": note}


def section_videos(course_id: str, section_num: int) -> dict:
    """
    Ranked teaching videos attached at generation time by _attach_videos.
    APIFY_TOKEN is required for live video lookup, so this returns an empty
    list plus a human
    reason rather than a bare [] the panel can't explain.

    If a course was generated before a key was added, its sections carry no
    videos; once a key is present we do a live topic-level lookup so the tab
    fills in without regenerating. youtube.py's keyless demo fallback returns
    topic-titled cards pointing at unrelated videos, so those (id 'demo-*')
    are filtered out — a student must never click "Photosynthesis" and land
    on a Python tutorial.
    """
    course, sec = get_section(course_id, section_num)
    if not sec:
        return None
    videos = sec.get("videos") or []
    if videos:
        return {"videos": videos}
    if not youtube_ready():
        return {"videos": [], "reason": "APIFY_TOKEN not set"}
    live = [v for v in course_videos(course.get("topic", ""), course.get("level", "beginner"))
            if not str(v.get("id", "")).startswith("demo-")]
    if live:
        return {"videos": live}
    return {"videos": [], "reason": "No teaching videos found for this section."}


# ------------------------------------------------------------------
# Quizzes — structured, gradable, answers kept server-side
# ------------------------------------------------------------------
QUIZ_SHAPE_PROMPT = """Section title: {title}

Section content:
{content}

Write {n} multiple-choice questions that test real understanding of this
section. Return ONLY a JSON array — no prose, no markdown fence. Each element:

{{"q": "the question", "options": ["A) ...", "B) ...", "C) ...", "D) ..."], "answer": "A", "explanation": "why that is correct"}}

Rules: exactly four options prefixed "A) " "B) " "C) " "D) "; "answer" is a
single letter A-D; vary which letter is correct. JSON array only."""


def _extract_json_array(raw: str):
    """
    Tolerant parse — the model often wraps JSON in a fence or adds a sentence.
    Strip fences, then take the outermost [...] and try that.
    """
    if not isinstance(raw, str):
        return None
    text = raw.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text).strip()
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return parsed
    except Exception:
        pass
    start, end = text.find("["), text.rfind("]")
    if start != -1 and end > start:
        try:
            parsed = json.loads(text[start:end + 1])
            if isinstance(parsed, list):
                return parsed
        except Exception:
            return None
    return None


LETTERS = "ABCDEF"

# "B) chlorophyll" / "b. chlorophyll" / "B - chlorophyll" -> "chlorophyll"
_LABEL_RE = re.compile(r"^\s*[A-Fa-f]\s*[).:\-]\s*")


def _option_text(o) -> str:
    return _LABEL_RE.sub("", str(o)).strip().casefold()


def _letter(raw, options) -> str:
    """
    Normalize one answer/pick to a letter, accepting every shape a model or a
    client might plausibly send: "B", "b)", "B) chlorophyll", the integer 1,
    the string "1", or the bare option text.

    Two traps this exists to avoid:
      * `raw or ""` treats the integer 0 as blank, so every "A" pick submitted
        as an index would score as unanswered.
      * Matching the first character first would read the option text
        "Chemical energy ..." as the letter C. Text is matched before letters.
    """
    if raw is None or isinstance(raw, bool):
        return None
    options = [str(o) for o in (options or [])]
    span = LETTERS[:len(options)] or LETTERS[:4]

    if isinstance(raw, int):
        return span[raw] if 0 <= raw < len(span) else None

    s = str(raw).strip()
    if not s:
        return None

    # Full option text (or a labelled option) wins over a bare-letter reading.
    if len(s) > 1:
        target = _option_text(s)
        for i, o in enumerate(options):
            if target and target == _option_text(o) and i < len(span):
                return span[i]

    head = s[:1].upper()
    if head in span and (len(s) == 1 or _LABEL_RE.match(s)):
        return head
    if s.isdigit():
        i = int(s)
        return span[i] if 0 <= i < len(span) else None
    if len(s) == 1 and head in LETTERS:
        return head  # letter beyond the option count — caller marks it wrong
    return None


def _clean_questions(items) -> list:
    """Keep only well-formed questions in boirsu's {q, options, answer} shape."""
    out = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        q = str(item.get("q") or item.get("question") or "").strip()
        options = item.get("options")
        if not q or not isinstance(options, list) or len(options) < 2:
            continue
        answer = _letter(item.get("answer"), options)
        # `answer not in "ABCD"` would be True for "" — a substring test lets an
        # answerless question through, and it can then never be got right.
        if answer not in tuple(LETTERS[:len(options)]):
            continue
        out.append({
            "q": q,
            "options": [str(o) for o in options],
            "answer": answer,
            "explanation": str(item.get("explanation") or "").strip(),
        })
    return out


def _fallback_questions(topic: str, course_title: str) -> list:
    """boirsu already ships canned quizzes in the exact same shape."""
    try:
        items = boirsu.generate_quiz(topic, course_title)
        cleaned = _clean_questions(items)
        if cleaned:
            return cleaned
    except Exception:
        pass
    try:
        return _clean_questions(boirsu.generate_generic_quiz(topic))
    except Exception:
        return []


def _quiz_payload(record: dict) -> dict:
    """The client-safe view of a stored quiz."""
    return {
        "quiz_id": record["quiz_id"],
        "title": record.get("title") or record.get("topic") or "",
        "source": record.get("source", "ai"),
        # Answers and explanations are deliberately withheld until submit,
        # otherwise the grade is trivially fake-able from devtools.
        "questions": [{"q": q["q"], "options": q["options"]} for q in record.get("questions", [])],
    }


def cached_quiz(course_id: str, section_num: int) -> dict:
    """The quiz already built for this section, or None."""
    def _find(d):
        course = d["courses"].get(course_id)
        if not course:
            return None
        for s in course.get("sections", []):
            if int(s.get("section_num") or 0) == int(section_num):
                qid = s.get("quiz_id")
                return d["quizzes"].get(qid) if qid else None
        return None

    record = _read(_find)
    return _quiz_payload(record) if record and record.get("questions") else None


def build_quiz(course_id: str, section_num: int, n: int = 5, fresh: bool = False) -> dict:
    """
    Returns {quiz_id, title, questions:[{q, options}]} — **without** answers.

    ai_quiz() in the AI script returns prose, which cannot be auto-graded, so
    we ask for the same JSON shape boirsu.generate_quiz() already uses
    (boirsu.py:446) and fall back to it when parsing fails.

    The model call costs minutes, so a built quiz is cached against the section
    and reused. fresh=True re-rolls it (the reader's "Try another quiz").
    """
    if not fresh:
        hit = cached_quiz(course_id, section_num)
        if hit:
            return hit

    course, sec = get_section(course_id, section_num)
    if not sec:
        return None

    questions = []
    try:
        raw = ai_module().ai(
            client(),
            QUIZ_SHAPE_PROMPT.format(
                title=sec.get("title", ""), content=(sec.get("content") or "")[:6000], n=n
            ),
            max_tokens=2000,
        )
        if not _is_ai_error(raw):
            questions = _clean_questions(_extract_json_array(raw))
    except Exception:
        questions = []

    source = "ai"
    if not questions:
        source = "fallback"
        questions = _fallback_questions(course.get("topic", ""), course.get("title", ""))
    if not questions:
        return None

    quiz_id = "quiz_" + uuid.uuid4().hex[:12]
    record = {
        "quiz_id": quiz_id,
        "course_id": course_id,
        "section_num": int(section_num),
        # `topic` is what boirsu.record_quiz_score() files the grade under, so it
        # must be the COURSE topic — using the section title would give one
        # Grades row per section (8 rows, 8 invented course codes, for one
        # course). `title` is the display heading for this quiz only.
        "topic": course.get("topic") or sec.get("title") or "",
        "title": sec.get("title") or course.get("topic") or "",
        "source": source,
        "created": datetime.now().isoformat(),
        "questions": questions,          # with answers — server side only
    }

    def _store(d):
        d["quizzes"][quiz_id] = record
        # Keep the store from growing without bound.
        if len(d["quizzes"]) > 200:
            oldest = sorted(d["quizzes"].items(), key=lambda kv: kv[1].get("created", ""))
            for k, _ in oldest[:len(d["quizzes"]) - 200]:
                d["quizzes"].pop(k, None)
        c = d["courses"].get(course_id)
        if c:
            for s in c.get("sections", []):
                if int(s.get("section_num") or 0) == int(section_num):
                    s["quiz_id"] = quiz_id

    _mutate(_store)

    return _quiz_payload(record)


_warming = set()
_warm_lock = threading.Lock()


def warm_quizzes(course_id: str) -> bool:
    """
    Pre-build every section's quiz on a background thread.

    A quiz costs one model call of a few minutes, which is far longer than any
    browser is willing to wait, so paying it lazily means the reader's Quiz tab
    fails the first time it is opened. Building them right after the course
    lands means they are cached before a student gets there. Sequential on
    purpose: concurrent calls to the same endpoint come back as errors and fall
    through to the 2-question generic bank.
    """
    with _warm_lock:
        if course_id in _warming:
            return False
        _warming.add(course_id)

    def run():
        try:
            course = _read(lambda d: d["courses"].get(course_id))
            for s in (course or {}).get("sections", []):
                num = int(s.get("section_num") or 0)
                if not num or cached_quiz(course_id, num):
                    continue
                try:
                    build_quiz(course_id, num)
                except Exception:
                    pass  # one bad section must not stop the rest
        finally:
            with _warm_lock:
                _warming.discard(course_id)

    threading.Thread(target=run, name=f"quiz-warm-{course_id}", daemon=True).start()
    return True


def grade_quiz(quiz_id: str, answers, student_id: str = None) -> dict:
    """
    Grade server-side, then hand the score to boirsu.record_quiz_score(), which
    already maintains avg_quiz_score and re-derives overall_grade (boirsu.py:1432).
    """
    quiz = _read(lambda d: d["quizzes"].get(quiz_id))
    if not quiz:
        return None

    questions = quiz.get("questions", [])
    if isinstance(answers, dict):
        given = [answers.get(str(i), answers.get(i)) for i in range(len(questions))]
    else:
        given = list(answers or [])
    given += [None] * (len(questions) - len(given))

    results, score = [], 0
    for i, q in enumerate(questions):
        picked = _letter(given[i], q.get("options"))
        correct = picked is not None and picked == q["answer"]
        if correct:
            score += 1
        results.append({
            "index": i,
            "picked": picked,
            "answer": q["answer"],
            "correct": correct,
            "explanation": q.get("explanation", ""),
        })

    total = len(questions)
    out = {
        "quiz_id": quiz_id,
        "topic": quiz.get("topic"),
        "score": score,
        "total": total,
        "percentage": round((score / total) * 100) if total else 0,
        "results": results,
        "student": None,
        "recorded": False,
    }

    if student_id:
        try:
            student = boirsu.record_quiz_score(student_id, quiz.get("topic", ""), score, total)
        except Exception:
            student = None
        if student:
            out["student"] = student
            out["recorded"] = True
    return out


# ------------------------------------------------------------------
# Tutor Q&A
# ------------------------------------------------------------------
def ask(question: str, course_id: str = None, section_num: int = None) -> str:
    """Answer a student's question, grounded in the section they're reading."""
    question = (question or "").strip()
    if not question:
        return None
    context = ""
    if course_id:
        course, sec = get_section(course_id, section_num or 1)
        if course:
            context = f"The student is studying \"{course.get('topic', '')}\"."
            if sec:
                context += (
                    f"\nCurrent section: {sec.get('title', '')}\n"
                    f"Section content:\n{(sec.get('content') or '')[:4000]}\n"
                )
    prompt = (
        f"{context}\n\nStudent's question: {question}\n\n"
        "Answer directly and warmly, as their tutor. Keep it under 180 words. "
        "If the question is outside the section, still answer it helpfully."
    )
    text = ai_module().ai(client(), prompt, max_tokens=900)
    return None if _is_ai_error(text) else text


# ------------------------------------------------------------------
# Live classroom tutor — grounded in the YouTube lesson + shared screen
# ------------------------------------------------------------------
# The /classroom page plays a YouTube lesson and lets students share a
# screen. Questions from its AI tab carry the lesson identity and, when the
# student is sharing, a fresh JPEG snapshot of their screen. Grounding works
# like AI-TUTOR/youtube_content.py: captions via youtube-transcript-api (no
# key needed), Apify subtitles as fallback, cached on disk so the first
# question pays the fetch cost only once per video.

CLASSROOM_SYSTEM_PROMPT = (
    "You are the AI Teacher inside a MiroFish live classroom. Students ask "
    "questions while watching a YouTube lesson and possibly sharing a screen. "
    "Answer like an excellent, warm, accurate teacher: correct mistakes "
    "gently, explain step by step with short paragraphs and concrete "
    "examples. Ground every answer in the LESSON CONTEXT (title, topic, "
    "captions) when relevant — if the captions do not cover something, say so "
    "briefly, then answer from your own knowledge clearly labelled as beyond "
    "the video. When a SCREEN SNAPSHOT is attached it is the student's live "
    "shared screen: read exactly what is on it (text, code, diagrams, errors) "
    "and relate it to the question. Never invent quotes or timestamps. Keep "
    "answers under 180 words unless asked to elaborate."
)

CLASSROOM_TRANSCRIPT_DIR = os.path.join(str(STORE_DIR), "transcripts")
_CLASSROOM_MAX_TRANSCRIPT_CHARS = 12000
# Hard cap on caption fetching per video; a hung request degrades to
# title/topic grounding instead of stalling the student's question.
CLASSROOM_TRANSCRIPT_TIMEOUT = float(os.environ.get("CLASSROOM_TRANSCRIPT_TIMEOUT", "45"))

_transcript_cache: dict = {}  # video_id -> transcript text ("" = unavailable)
_transcript_lock = threading.Lock()


def _video_id_from(url_or_id: str) -> str:
    """Best-effort YouTube id extraction; '' when nothing looks like an id."""
    text = (url_or_id or "").strip()
    match = re.search(r"(?:v=|youtu\.be/|embed/|shorts/|/)([0-9A-Za-z_-]{11})(?:[?&/]|$)", text)
    if match:
        return match.group(1)
    if re.fullmatch(r"[0-9A-Za-z_-]{11}", text):
        return text
    return ""


def _fetch_transcript_text(video_id: str) -> str:
    """
    Caption text for one video. youtube-transcript-api first (fast, keyless),
    then the Apify YouTube actor's subtitles. Returns '' when neither has
    captions — callers teach from title/topic instead.
    """
    try:
        from youtube_transcript_api import YouTubeTranscriptApi

        lines = []
        try:
            for snippet in YouTubeTranscriptApi().fetch(video_id):
                lines.append(snippet.text)
        except AttributeError:
            # pre-1.0 package: classmethod returning [{'text','start',...}]
            for seg in YouTubeTranscriptApi.get_transcript(video_id):
                lines.append(seg.get("text", ""))
        text = re.sub(r"\s+", " ", " ".join(l.strip() for l in lines if l and l.strip())).strip()
        if text:
            return text[:_CLASSROOM_MAX_TRANSCRIPT_CHARS]
    except Exception:
        pass  # no captions / blocked -> fall through to Apify

    try:
        mod = ai_module()
        token = getattr(mod, "APIFY_TOKEN", "") or os.environ.get("APIFY_TOKEN", "")
        if not token:
            return ""
        from apify_client import ApifyClient

        apify = ApifyClient(token)
        actor = os.environ.get(
            "APIFY_YOUTUBE_ACTOR",
            getattr(mod, "APIFY_YOUTUBE_ACTOR", "streamers/youtube-scraper"),
        )
        run = apify.actor(actor).call(run_input={
            "startUrls": [{"url": f"https://www.youtube.com/watch?v={video_id}"}],
            "downloadSubtitles": True,
        })
        item = next(iter(apify.dataset(run["defaultDatasetId"]).iterate_items()), None)
        raw = (item or {}).get("subtitles") or (item or {}).get("captions") \
            or (item or {}).get("transcript") or ""
        if isinstance(raw, dict):
            raw = raw.get("text") or raw.get("transcript") or ""
        if isinstance(raw, list):
            parts = []
            for entry in raw:
                if isinstance(entry, str):
                    parts.append(entry)
                elif isinstance(entry, dict):
                    t = entry.get("text") or entry.get("textOriginal") or ""
                    if isinstance(t, list):
                        t = " ".join(str(p) for p in t)
                    if t:
                        parts.append(str(t))
            raw = " ".join(parts)
        text = re.sub(r"\s+", " ", str(raw)).strip()
        return text[:_CLASSROOM_MAX_TRANSCRIPT_CHARS] if text else ""
    except Exception:
        return ""


def lesson_transcript(video_id: str) -> str:
    """Cached transcript text for a lesson video ('' when unavailable).

    The fetch runs in a worker thread with a hard timeout so a hung captions
    request can never stall a student's question — worst case we answer from
    title/topic alone.
    """
    video_id = _video_id_from(video_id)
    if not video_id:
        return ""
    with _transcript_lock:
        if video_id in _transcript_cache:
            return _transcript_cache[video_id]

    text = ""
    path = os.path.join(CLASSROOM_TRANSCRIPT_DIR, f"{video_id}.txt")
    if os.path.exists(path) and os.path.getsize(path) > 32:
        try:
            with open(path, "r", encoding="utf-8") as fh:
                text = fh.read().strip()
        except Exception:
            text = ""
    if not text:
        result = {}
        worker = threading.Thread(target=lambda: result.update(text=_fetch_transcript_text(video_id)),
                                  daemon=True)
        worker.start()
        worker.join(timeout=CLASSROOM_TRANSCRIPT_TIMEOUT)
        text = (result.get("text") or "").strip()
        if text:
            try:
                os.makedirs(CLASSROOM_TRANSCRIPT_DIR, exist_ok=True)
                tmp = path + ".tmp"
                with open(tmp, "w", encoding="utf-8") as fh:
                    fh.write(text)
                os.replace(tmp, path)
            except Exception:
                pass  # cache-write failures must never break a question

    with _transcript_lock:
        _transcript_cache[video_id] = text
    return text


def _clean_history(history, max_turns=8, max_chars=1000) -> list:
    """Keep the last few chat turns as plain {'role','content'} messages."""
    cleaned = []
    for msg in history or []:
        role = "assistant" if msg.get("role") == "assistant" else "user"
        content = re.sub(r"\s+", " ", str(msg.get("content") or "")).strip()[:max_chars]
        if content:
            cleaned.append({"role": role, "content": content})
    return cleaned[-max_turns:]


def _strip_image_prefix(image_b64: str) -> str:
    """Accept raw base64 or a data URI; always keep raw base64."""
    return re.sub(r"^data:image/[a-zA-Z]+;base64,", "", (image_b64 or "").strip())


# Model chains for the classroom tutor. NVIDIA Build retires models
# occasionally (z-ai's previous model went EOL 2026-08-21), so classroom_ask
# tries these in order, remembers the winner, and buries any id the server
# reports as gone (404/410). Override either chain with env:
#   CLASSROOM_TUTOR_MODEL / CLASSROOM_TUTOR_VISION_MODEL
_CLASSROOM_TEXT_MODELS = [
    "nvidia/nemotron-3-super-120b-a12b",
    "moonshotai/kimi-k3",
    "openai/gpt-oss-120b",
    "meta/llama-3.3-70b-instruct",
]
_CLASSROOM_VISION_MODELS = [
    # inkling already takes image_url parts elsewhere in this repo
    # (AI-TUTOR/ai_client.ask_inkling_with_image).
    "thinkingmachines/inkling",
    "nvidia/nemotron-nano-12b-v2-vl",
    "meta/llama-3.2-90b-vision-instruct",
]
_models_lock = threading.Lock()
_text_model_in_use = ""
_vision_model_in_use = ""
_dead_models = set()


def _model_chain(kind: str) -> list:
    """Ordered, de-duplicated model ids for 'text' or 'vision'."""
    env_key = "CLASSROOM_TUTOR_MODEL" if kind == "text" else "CLASSROOM_TUTOR_VISION_MODEL"
    defaults = _CLASSROOM_TEXT_MODELS if kind == "text" else _CLASSROOM_VISION_MODELS
    with _models_lock:
        current = _text_model_in_use if kind == "text" else _vision_model_in_use
    chain = [(os.environ.get(env_key) or "").strip(), current, *defaults]
    seen, out = set(), []
    for model_id in chain:
        if model_id and model_id not in seen:
            seen.add(model_id)
            out.append(model_id)
    return out


def _chat_with_fallback(kind: str, messages: list, max_tokens: int):
    """One completion via the model chain; remembers the winner per kind."""
    global _text_model_in_use, _vision_model_in_use
    last_exc = None
    # Interactive asks keep the snappy 90s budget; long content asks (textbook
    # chapters at 4000-16000 tokens) need room or the timeout kills a healthy
    # call mid-generation and the chain never finishes the book.
    timeout = 90 if int(max_tokens or 0) <= 900 else max(
        240.0, float(max_tokens) / 25.0)
    for model_id in _model_chain(kind):
        if model_id in _dead_models:
            continue
        # Reasoning models (nemotron family) burn the SAME max_tokens budget on
        # hidden reasoning_content before writing one content token - on big
        # asks that starves the answer (books came back as empty skeletons).
        # Verified on the live endpoint; non-nemotron models never see it.
        extra = ({"chat_template_kwargs": {"enable_thinking": False}}
                 if "nemotron" in str(model_id).lower() else None)
        try:
            completion = client().chat.completions.create(
                model=model_id,
                messages=messages,
                temperature=0.4,
                top_p=0.95,
                max_tokens=max_tokens,
                stream=False,
                timeout=timeout,
                **({"extra_body": extra} if extra else {}),
            )
        except Exception as exc:
            status = getattr(exc, "status_code", None)
            print(f"[classroom-tutor] {kind} model {model_id} failed "
                  f"(status={status}): {str(exc)[:160]}")
            if status in (401, 403):
                # Auth is broken — no other model will pass either. Fail fast
                # with a message the student-facing UI can surface.
                raise RuntimeError(
                    "NVIDIA API rejected the API key (401/403). "
                    "Check NVIDIA_API_KEY in backend/.env — keys from "
                    "build.nvidia.com start with 'nvapi-'."
                ) from exc
            if status in (400, 404, 410):
                with _models_lock:
                    _dead_models.add(model_id)
            last_exc = exc
            continue
        with _models_lock:
            if kind == "text":
                _text_model_in_use = model_id
            else:
                _vision_model_in_use = model_id
        return completion
    raise last_exc or RuntimeError("no tutor model available")


def classroom_ask(question: str, lesson: dict = None, history: list = None,
                  image_b64: str = None, max_tokens: int = 900):
    """
    Answer a live-classroom question grounded in the YouTube lesson being
    watched and, when provided, a snapshot of the student's shared screen.

    Returns the answer text, or None on any model failure (the endpoint maps
    that to 503 exactly like ask()). A vision failure degrades to one
    text-only retry instead of failing the whole answer.
    """
    question = (question or "").strip()
    if not question:
        return None

    lesson = lesson if isinstance(lesson, dict) else {}
    context_lines = ["LESSON CONTEXT"]
    topic = str(lesson.get("topic") or "").strip()
    title = str(lesson.get("title") or "").strip()
    channel = str(lesson.get("channel") or "").strip()
    url = str(lesson.get("url") or lesson.get("watch_url") or "").strip()
    duration = str(lesson.get("duration_display") or lesson.get("duration") or "").strip()

    video_id = _video_id_from(url) or _video_id_from(title)
    if video_id:
        context_lines.append(f"Video URL: https://www.youtube.com/watch?v={video_id}")
        if title:
            context_lines.append(f"Title: {title}")
        if channel:
            context_lines.append(f"Channel: {channel}")
        if duration:
            context_lines.append(f"Duration: {duration}")
        if topic:
            context_lines.append(f"Course topic: {topic}")
        transcript = lesson_transcript(video_id)
        if transcript:
            context_lines.append("Captions/transcript of the video:\n" + transcript)
        else:
            context_lines.append(
                "(No captions were available for this video — teach from the "
                "title/topic above and your own knowledge.)"
            )
    elif topic:
        context_lines.append(f"Course topic: {topic}")

    image_b64 = _strip_image_prefix(image_b64)
    screen_attached = bool(image_b64) and len(image_b64) < 6_000_000
    if screen_attached:
        context_lines.append(
            "SCREEN SNAPSHOT: attached to this message — the student's live "
            "shared screen at the moment they asked."
        )

    turns = _clean_history(history)
    turn_lines = [f"{m['role']}: {m['content']}" for m in turns] or ["(none yet)"]
    user_text = "\n".join(
        ["\n".join(context_lines), "\nRecent conversation:", *turn_lines,
         f"\nStudent's question: {question}"]
    )

    content = [{"type": "text", "text": user_text}]
    if screen_attached:
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"},
        })
    messages = [
        {"role": "system", "content": CLASSROOM_SYSTEM_PROMPT},
        {"role": "user", "content": content},
    ]

    try:
        completion = _chat_with_fallback(
            "vision" if screen_attached else "text", messages, max_tokens)
    except Exception:
        if not screen_attached:
            return None
        try:  # vision unavailable/rate-limited — degrade to text-only once
            messages[1]["content"] = user_text + (
                "\n\n(Note: the screen snapshot could not be analyzed this "
                "time; answer from the lesson context alone.)"
            )
            completion = _chat_with_fallback("text", messages, max_tokens)
        except Exception:
            return None

    text = ((completion.choices[0].message.content or "") if completion.choices else "").strip()
    return None if (not text or _is_ai_error(text)) else text


# ------------------------------------------------------------------
# Deepgram TTS — audio mode for the generated lesson / PDF
# ------------------------------------------------------------------
def _chunk_for_tts(text: str) -> list:
    """
    Same ≤3000-char split at sentence boundaries that speak_text() uses
    (ai_learning_system_v4:185) so Deepgram never hits its character limit.
    """
    chunks, current = [], ""
    for sentence in re.split(r"(?<=[.!?])\s+", (text or "").strip()):
        if len(current) + len(sentence) + 1 > DEEPGRAM_CHUNK_CHARS:
            if current:
                chunks.append(current.strip())
            current = sentence
        else:
            current = (current + " " + sentence).strip()
    if current:
        chunks.append(current.strip())
    return [c for c in chunks if c]


def synthesize(text: str) -> bytes:
    """
    Deepgram Aura-2 -> MP3 bytes for the browser.

    Same request contract as speak_text() (POST /v1/speak?model=<voice> with a
    Token header), but the bytes are returned instead of written to a temp file
    and played through mpg123 on the server.

    Raises RuntimeError with a readable message on failure.
    """
    key = _deepgram_key()
    if not key:
        raise RuntimeError("DEEPGRAM_API_KEY not set")
    if not (text or "").strip():
        raise RuntimeError("nothing to read")

    import requests  # already a dependency of the AI script

    headers = {"Authorization": f"Token {key}", "Content-Type": "application/json"}
    audio, errors = bytearray(), []
    for chunk in _chunk_for_tts(text):
        try:
            response = requests.post(
                DEEPGRAM_SPEAK_URL,
                params={"model": _deepgram_voice()},
                headers=headers,
                json={"text": chunk},
                timeout=60,
            )
        except Exception as exc:
            errors.append(str(exc)[:120])
            continue
        if response.status_code != 200:
            errors.append(f"{response.status_code}: {response.text[:120]}")
            continue
        audio.extend(response.content)

    if not audio:
        raise RuntimeError("Deepgram returned no audio" + (f" ({errors[0]})" if errors else ""))
    return bytes(audio)


def section_audio(course_id: str, section_num: int) -> bytes:
    """
    MP3 for one lesson section, cached on disk so re-listening is free.
    This is the same text the browser-side PDF contains, so "read the PDF
    aloud" and "read page N" are one feature.
    """
    course, sec = get_section(course_id, section_num)
    if not sec:
        return None
    _ensure_dirs()
    path = os.path.join(AUDIO_DIR, f"{course_id}_s{int(section_num)}.mp3")
    if os.path.exists(path) and os.path.getsize(path) > 1024:
        with open(path, "rb") as f:
            return f.read()

    spoken = f"{sec.get('title', '')}. {sec.get('content', '')}"
    audio = synthesize(spoken)
    try:
        tmp = path + ".tmp"
        with open(tmp, "wb") as f:
            f.write(audio)
        os.replace(tmp, path)
    except Exception:
        pass
    return audio


# ------------------------------------------------------------------
# Diagnostics
# ------------------------------------------------------------------
def status() -> dict:
    """Cheap health payload — never raises, so /health stays reliable."""
    try:
        mod = ai_module()
        loaded, load_error = True, None
        model = getattr(mod, "MODEL_ID", None)
        apify = bool(getattr(mod, "APIFY_TOKEN", ""))
        nvidia = bool(getattr(mod, "NVIDIA_KEY", ""))
    except Exception as exc:
        loaded, load_error, model = False, str(exc)[:200], None
        apify = nvidia = False
    try:
        courses = len(list_courses())
    except Exception:
        courses = 0
    return {
        "ai_script_loaded": loaded,
        "load_error": load_error,
        "model": model,
        "keys": {"nvidia": nvidia, "apify": apify,
             "deepgram": deepgram_ready(),
                 "youtube": youtube_ready()},
        "courses": courses,
        "store": str(COURSES_FILE),
    }
