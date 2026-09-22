"""
BOI RSU â€” Realtime API Server
=============================
Bridges the Vue roadmap frontend with:
  - boirsu.py                     (career roadmaps, student records, progress)
  - ai_learning_system_v4 (14).py (AI-powered live class generation)

Real-time updates use Server-Sent Events (SSE) â€” no extra dependencies
needed beyond Flask + flask-cors, which are already installed.

Run:
  python api_server.py
Serves on http://localhost:5055
"""

import os
import re
import sys
import json
import queue
import base64
import threading
import subprocess
import time
import uuid
from datetime import datetime, date, timedelta

from flask import Flask, jsonify, request, Response, stream_with_context, send_file
from flask_cors import CORS

# ---- load backend/.env BEFORE anything that reads the AI keys ----
# ai_learning_system_v4 (14).py reads NVIDIA_API_KEY at import time, and the
# AI engines are imported lazily on first request, so the key must already be
# in os.environ by then. `python api_server.py` from the boi-rsu folder used
# to skip backend/.env entirely -> every AI call failed -> empty fallback
# textbooks. Same search order as app/config.py; existing env vars win.
def _load_backend_env():
    here = os.path.dirname(os.path.abspath(__file__))          # .../backend/app/boi-rsu
    backend_dir = os.path.dirname(os.path.dirname(here))       # .../backend
    for cand in (os.path.join(backend_dir, ".env"),
                 os.path.join(backend_dir, ".env.local"),
                 os.path.join(os.path.dirname(backend_dir), ".env")):
        try:
            if not os.path.isfile(cand):
                continue
            with open(cand, "r", encoding="utf-8-sig", errors="replace") as fh:
                for line in fh:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, _, v = line.partition("=")
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    if k and v and k not in os.environ:
                        os.environ[k] = v
            print("[api_server] loaded env from " + cand)
        except Exception as exc:
            print("[api_server] env load failed for %s: %s" % (cand, str(exc)[:120]))


_load_backend_env()

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import boirsu  # noqa: E402  (career roadmaps, student management, AI launch)
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import boirsu  # noqa: E402  (career roadmaps, student management, AI launch)

app = Flask(__name__)
CORS(app)

# ------------------------------------------------------------------
# SSE (Server-Sent Events) â€” one broadcast hub, many browser clients
# ------------------------------------------------------------------
_subscribers: "list[queue.Queue]" = []
_subscribers_lock = threading.Lock()


def broadcast(event: str, payload: dict):
    """Push an event to every connected browser."""
    message = {"event": event, "data": payload, "ts": datetime.now().isoformat()}
    with _subscribers_lock:
        dead = []
        for q in _subscribers:
            try:
                q.put_nowait(message)
            except Exception:
                dead.append(q)
        for q in dead:
            _subscribers.remove(q)


@app.get("/api/stream")
def stream():
    """SSE endpoint the frontend subscribes to for live updates."""
    def gen():
        q: queue.Queue = queue.Queue(maxsize=100)
        with _subscribers_lock:
            _subscribers.append(q)
        # greet the new client so it knows the pipe is open
        yield f"data: {json.dumps({'event': 'connected', 'data': {}})}\n\n"
        try:
            while True:
                try:
                    msg = q.get(timeout=20)
                    yield f"data: {json.dumps(msg)}\n\n"
                except queue.Empty:
                    # heartbeat keeps proxies from closing the connection
                    yield ": keep-alive\n\n"
        finally:
            with _subscribers_lock:
                if q in _subscribers:
                    _subscribers.remove(q)

    return Response(stream_with_context(gen()), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/health")
def health():
    return jsonify({"ok": True, "service": "boi-rsu-realtime-api",
                    "clients": len(_subscribers)})


# ------------------------------------------------------------------
# ROADMAP DATA â€” shaped for roadmap.vue (topics -> tasks)
# ------------------------------------------------------------------
# Legacy / loose slug aliases -> canonical CAREER_ROADMAPS keys. Early
# enrollment stored underscore slugs ("frontend_developer") and course names
# were slugged verbatim ("graphic-design-and-branding"), so the dashboard's
# /api/timetable and /api/ai/daily-plan calls 404ed for those students.
_CAREER_ALIASES = {
    "frontend_developer": "frontend-developer",
    "backend_developer": "backend-developer",
    "data_scientist": "data-scientist",
    "mobile_developer": "mobile-developer",
    "ui_ux_designer": "ui-ux-designer",
    "ui-ux-designer": "ui-ux-designer",
    "graphic-design-and-branding": "graphic-design-branding",
    "graphic-design": "graphic-design-branding",
    "seo-and-content-writing": "seo-content-writing",
}


def _resolve_career_path(career_path: str) -> str:
    """Normalise a client-supplied career path to a canonical roadmap slug."""
    key = (career_path or "").strip().lower().replace("_", "-").replace(" ", "-")
    key = re.sub(r"-+", "-", key)
    key = re.sub(r"[^a-z0-9-]", "", key)
    return _CAREER_ALIASES.get(key, key)


def _roadmap_to_topics(career_path: str) -> list:
    """Convert a CAREER_ROADMAPS monthly plan into the node/task shape
    the Vue roadmap expects: [{short, title, blurb, tasks[]}]."""
    key = _resolve_career_path(career_path)
    roadmap = boirsu.CAREER_ROADMAPS.get(key)
    if not roadmap:
        return []

    topics = []
    for month in roadmap.get("monthly_plan", []):
        month_no = month.get("month")
        tasks = list(month.get("topics", []))
        if month.get("project"):
            tasks.append(f"Project: {month['project']}")
        topics.append({
            "short": f"Month {month_no}",
            "title": month.get("title", f"Month {month_no}"),
            "blurb": f"{roadmap.get('title', career_path)} â€” month {month_no} of "
                     f"{len(roadmap.get('monthly_plan', []))}.",
            "tasks": tasks,
            "career_path": key,
            "month": month_no,
        })
    return topics


@app.get("/api/careers")
def list_careers():
    """All available career paths for a picker in the UI."""
    out = []
    for slug, rm in boirsu.CAREER_ROADMAPS.items():
        out.append({
            "slug": slug,
            "title": rm.get("title", slug),
            "duration": rm.get("duration", ""),
            "description": rm.get("description", ""),
            "months": len(rm.get("monthly_plan", [])),
        })
    return jsonify({"success": True, "careers": out})


@app.get("/api/roadmap/<career_path>")
def get_roadmap(career_path):
    """Live roadmap topics for the chosen career path."""
    topics = _roadmap_to_topics(career_path)
    if not topics:
        return jsonify({"success": False, "error": f"Unknown career path: {career_path}"}), 404
    return jsonify({"success": True, "career_path": career_path, "topics": topics})


# ------------------------------------------------------------------
# PROGRESS â€” persisted per (career_path) so refreshes keep state.
# Stored beside boirsu's own workspace so it survives restarts.
# ------------------------------------------------------------------
PROGRESS_FILE = boirsu.BASE_DIR / "roadmap_progress.json"


def _load_progress() -> dict:
    if PROGRESS_FILE.exists():
        try:
            return json.loads(PROGRESS_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_progress(data: dict):
    PROGRESS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


@app.get("/api/progress/<career_path>")
def get_progress(career_path):
    """Return saved completion map: {"<topicIndex>": [bool, bool, ...]}."""
    prog = _load_progress().get(career_path, {})
    return jsonify({"success": True, "career_path": career_path, "progress": prog})


@app.post("/api/progress/<career_path>")
def set_progress(career_path):
    """Save one task's done-state and broadcast it live to other clients."""
    body = request.get_json(silent=True) or {}
    topic_index = body.get("topicIndex")
    task_index = body.get("taskIndex")
    done_value = bool(body.get("done"))

    if topic_index is None or task_index is None:
        return jsonify({"success": False, "error": "topicIndex and taskIndex required"}), 400

    all_prog = _load_progress()
    course = all_prog.setdefault(career_path, {})
    row = course.setdefault(str(topic_index), [])
    while len(row) <= task_index:
        row.append(False)
    row[task_index] = done_value
    _save_progress(all_prog)

    broadcast("progress_updated", {
        "career_path": career_path,
        "topicIndex": topic_index,
        "taskIndex": task_index,
        "done": done_value,
    })
    return jsonify({"success": True, "progress": course})

def _auto_advance_roadmap(student: dict, career_path: str) -> int:
    """
    Attendance-driven roadmap completion (no student clicking needed).

    The roadmap page's nodes are the course months; each node's tasks are the
    month's topics. Every class the student attends completes the next task in
    order across the whole path, so nodes turn green in real time as classes
    are attended on the timetable/classroom. Writes the same
    roadmap_progress.json store the roadmap page reads, and broadcasts an SSE
    `progress_snapshot` so any open roadmap tab updates instantly.
    Returns how many tasks flipped.
    """
    try:
        topics = _roadmap_to_topics(career_path)
        attended = int(student.get("classes_attended") or 0)
        if not topics:
            return 0
        if attended <= 0:
            return 0

        all_prog = _load_progress()
        course = all_prog.setdefault(career_path, {})
        flipped = 0
        remaining = attended
        for ti, topic in enumerate(topics):
            row = course.setdefault(str(ti), [])
            tasks = topic.get("tasks") or []
            while len(row) < len(tasks):
                row.append(False)
            for task_i in range(len(tasks)):
                if remaining <= 0:
                    break
                if row[task_i] is not True:
                    row[task_i] = True
                    flipped += 1
                    remaining -= 1
            if remaining <= 0:
                break
        if flipped:
            _save_progress(all_prog)
            broadcast("progress_snapshot", {
                "career_path": career_path,
                "progress": course,
                "reason": "attendance",
            })
        return flipped
    except Exception as exc:
        print(f"[WARN] _auto_advance_roadmap failed: {exc}")
        return 0


# ------------------------------------------------------------------
# TIMETABLE — weekly class schedule derived LIVE from boirsu's
# monthly plan (same week-splitting as generate_roadmap_pdf) plus
# cohort session times chosen from the student's track.
# ------------------------------------------------------------------
_TRACK_DEFAULT_TIMES = {"daytime": "10:00", "weekend": "11:00", "evening": "18:00"}
_DAILY_DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
_TIME_RE = re.compile(r"^([01]?\d|2[0-3]):[0-5]\d$")


def _sanitize_time(value, default: str = "18:00") -> str:
    """Keep only a sane HH:MM 24h clock — the student's preferred class time."""
    v = str(value or "").strip()
    if _TIME_RE.match(v):
        h, m = v.split(":")
        return f"{int(h):02d}:{m}"
    return default


def _parse_daily_times(value) -> dict:
    """Accept the student's per-day class times from registration or from an API
    query string.

    `value` can be:
      - a plain HH:MM string (legacy single-time registration) -> every day at that time
      - a JSON string encoding a dict like
        '{"Monday":"18:00","Tuesday":"14:00","Wednesday":"","Saturday":"09:00",...}'
        — the timetable and daily-plan endpoints pass this via ?daily_times=.
      - a dict like {"Monday": "18:00", "Wednesday": "", "Saturday": "09:00", ...}
        where an empty / missing / "none" value means "no class that day"
    Returns a dict {weekday: "HH:MM"} for days that have a class, only for valid
    weekdays and valid times.
    """
    out = {}
    if isinstance(value, dict):
        for day in _DAILY_DAYS:
            v = value.get(day, value.get(day.lower(), ""))
            v = str(v or "").strip().lower()
            if v in ("", "none", "off", "0", "false"):
                continue
            clock = _sanitize_time(v, "")
            if clock:
                out[day] = clock
        return out
    # A JSON string from an API query param like ?daily_times=... -> decode it.
    if isinstance(value, str) and value.strip():
        import json as _json
        try:
            parsed = _json.loads(value)
            if isinstance(parsed, dict):
                return _parse_daily_times(parsed)
        except (ValueError, TypeError):
            pass
        # Not valid JSON — fall through to the legacy single-time string path.
    # Legacy single-time string -> treat as "all days at that time".
    clock = _sanitize_time(value, "")
    if clock:
        for day in _DAILY_DAYS:
            out[day] = clock
    return out


def _track_sessions(track: str = "", time: str = "", daily_times=None) -> list:
    """BOI RSU runs DAILY live classes (Mon–Sun) for the days the student
    actually chose on their registration form.

    `daily_times` is the per-day dict persisted from registration.vue
    ( {"Monday":"18:00", "Tuesday":"14:00", "Saturday":"09:00"} ). When it is
    empty / missing, the legacy `time` param (one global hour) is used for every
    day so old registrations and the API still behave sensibly.
    """
    chosen = _parse_daily_times(daily_times) if daily_times else {}
    if chosen:
        return [(day, chosen[day]) for day in _DAILY_DAYS if day in chosen]
    # Legacy path: one global hour for every day.
    t = (track or "").lower()
    if "daytime" in t:
        default = _TRACK_DEFAULT_TIMES["daytime"]
    elif "weekend" in t:
        default = _TRACK_DEFAULT_TIMES["weekend"]
    else:
        default = _TRACK_DEFAULT_TIMES["evening"]
    clock = _sanitize_time(time, default)
    return [(day, clock) for day in _DAILY_DAYS]


def _student_daily_times(student_id: str) -> "dict | None":
    """The saved per-day class grid of one enrolled student, straight from the
    students table. Lets the timetable/daily-plan endpoints honour the days the
    student chose at registration even when the caller could not send them yet
    (e.g. the dashboard's first paint, before the profile has hydrated)."""
    sid = (student_id or "").strip()
    if not sid:
        return None
    try:
        import pgdb as _pgdb  # imported lazily — api_server imports it inside functions
        rows = _pgdb._run(
            "SELECT preferred_daily_times FROM students WHERE student_id = %s LIMIT 1",
            (sid,),
        ) or []
        raw = rows[0].get("preferred_daily_times") if rows else None
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except (ValueError, TypeError):
                raw = None
        if isinstance(raw, dict) and raw:
            return raw
    except Exception:
        pass
    return None


@app.get("/api/timetable/<career_path>")
def get_timetable(career_path):
    """Weekly timetable for a career path's current (or given) month.
    Classes run DAILY at the student's preferred time (?time=HH:MM)."""
    month_no = request.args.get("month", type=int)
    track = request.args.get("track", "")
    time = request.args.get("time", "")
    daily_times = request.args.get("daily_times", "")
    if not daily_times:
        # The caller could not send the per-day grid (first paint, roadmap page,
        # etc.) — fall back to the student's SAVED registration grid so opted-out
        # days (Monday/Thursday for the Bank of Industry student) never come back.
        daily_times = _student_daily_times(request.args.get("student_id", "")) or ""

    topics = _roadmap_to_topics(career_path)
    if not topics:
        return jsonify({"success": False,
                        "error": f"Unknown career path: {career_path}"}), 404

    node = None
    if month_no:
        node = next((t for t in topics if t.get("month") == month_no), None)
    if node is None:
        node = topics[0]
        month_no = node.get("month")

    tasks = list(node.get("tasks", []))
    sessions = _track_sessions(track, time, daily_times)
    per_week = max(1, len(tasks) // 4 + 1)   # mirrors the PDF generator

    weeks = []
    for w in range(4):
        week_tasks = tasks[w * per_week:(w + 1) * per_week]
        if not week_tasks:
            # Daily classes: keep every chosen day busy by cycling the month's topics.
            week_tasks = tasks or ["Class & project work"]
        rows = []
        for j, (day, time_s) in enumerate(sessions):
            rows.append({"day": day, "time": time_s,
                         "topic": week_tasks[j % len(week_tasks)]})
        weeks.append({"week": f"Week {w + 1}", "sessions": rows})

    return jsonify({
        "success": True,
        "career_path": career_path,
        "month": month_no,
        "month_title": node.get("title"),
        "timezone": "Africa/Lagos (WAT)",
        "duration_mins": 60,
        "weeks": weeks,
    })


# ------------------------------------------------------------------
# DAILY PLAN — the fine-grained, day-by-day lesson schedule.
# The roadmap says WHAT a month covers; this says what happens in EVERY
# class meeting: the exact lesson topic, the teaching breakdown, the
# hands-on deliverable and the YouTube search for the lesson video.
# When NVIDIA_API_KEY is configured, MiroFish AI writes all of it;
# otherwise a deterministic expansion keeps every day still concrete.
# Plans are cached per (career_path, month, track) and every connected
# dashboard refreshes live via the "daily_plan_updated" SSE event.
# ------------------------------------------------------------------
_DAILY_PLANS_PATH = boirsu.TIMETABLES_DIR / "daily_plans.json"
_daily_plan_jobs: "dict[str, dict]" = {}

_WEEKDAY_INDEX = {"Monday": 0, "Tuesday": 1, "Wednesday": 2, "Thursday": 3,
                  "Friday": 4, "Saturday": 5, "Sunday": 6}


def _load_daily_plans() -> dict:
    return boirsu._json_file_load(str(_DAILY_PLANS_PATH)) or {}


def _save_daily_plans(all_plans: dict):
    boirsu._json_file_save(str(_DAILY_PLANS_PATH), all_plans)


def _daily_fingerprint(daily_times) -> str:
    """Collapse a per-day class-time dict into a short cache-key fragment.

    Only the SET of chosen weekdays affects the plan CONTENT (the clock is
    re-labelled on output), so the fingerprint is the sorted chosen days.
    An empty dict means 'no per-day override' -> the daily default (all 7)."""
    chosen = _parse_daily_times(daily_times) if daily_times else {}
    if not chosen:
        return "daily7"
    return "daily7-" + "".join(d[:2] for d in _DAILY_DAYS if d in chosen)


def _plan_key(career_path: str, month, track: str, daily_times=None) -> str:
    # "v2-daily" — plans are now daily (7 days × 4 weeks at the student's
    # preferred hours). The per-day weekday fingerprint keeps separate caches
    # for "default all 7 days" vs. "Mon/Tue/Thu/Fri/Sat only", so a student who
    # picks fewer days never shadows (or is shadowed by) the daily default.
    fp = _daily_fingerprint(daily_times)
    return f"{career_path}|{int(month or 1)}|{(track or '').strip().lower()}|{fp}|v2-daily"


def _plan_dates(track: str, weeks: int = 4, time: str = "",
                daily_times=None) -> "list[dict]":
    """Real upcoming dates for every class meeting the student chose
    (Mon–Sun, only on chosen days, at the chosen hour): week, weekday, time, date."""
    slots = _track_sessions(track, time, daily_times)
    if not slots:
        # Neither per-day times nor a legacy single time were supplied. In BOI RSU
        # every student has daily classes, so fall back to all 7 days at 18:00 WAT
        # rather than a 3-day weekday-only schedule.
        slots = [(day, "18:00") for day in _DAILY_DAYS]
    today = datetime.now().date()
    first_idx = _WEEKDAY_INDEX.get(slots[0][0], 1)
    base = today + timedelta(days=(first_idx - today.weekday()) % 7)
    out = []
    for w in range(1, weeks + 1):
        anchor = base + timedelta(days=7 * (w - 1))
        for day, clock in slots:
            offset = (_WEEKDAY_INDEX.get(day, 1) - anchor.weekday()) % 7
            out.append({"week": w, "weekday": day, "time": clock,
                        "date": (anchor + timedelta(days=offset)).isoformat()})
    return out


_LEARN_BREAKDOWN = [
    "Why {t} matters in {c} and where you'll use it",
    "Core concepts of {t}, explained and live-coded step by step",
    "The key terms you must be able to explain by the end of class",
    "Common beginner mistakes with {t} — spotted and fixed live",
    "Recap, your questions answered, and what the next class builds on it",
]
_BUILD_BREAKDOWN = [
    "Quick recap of the {t} ideas from the previous class",
    "Code-along: we build a real mini-project that uses {t}",
    "You rebuild the same thing yourself while the teacher guides",
    "Debug clinic — the errors {t} produces and their fixes",
    "Deliverable submitted in the classroom before the next class",
]
_DEEP_BREAKDOWN = [
    "Advanced angles of {t} that most tutorials skip",
    "Quality checklist: what separates amateur from professional {t} work",
    "Fix-it session: broken real-world examples repaired together",
    "Speed drills so {t} becomes muscle memory",
    "Q&A plus a preview of the next topic on the roadmap",
]
_PLAN_KINDS = [
    ("Concepts & live walkthrough", _LEARN_BREAKDOWN,
     "Write down 3 things you learned about {t} and 1 question to ask next class."),
    ("Guided practice — build with it", _BUILD_BREAKDOWN,
     "Finish and submit the mini-project built in class using {t}."),
    ("Deep dive, mistakes & fixes", _DEEP_BREAKDOWN,
     "Redo the {t} exercise from scratch without help, then compare with the class solution."),
]
_VIDEO_ANGLES = ["full course for beginners", "project tutorial for beginners", "common mistakes explained"]
_VIDEO_CHECKLISTS = [
    ["What {t} is and why it matters", "Core concepts explained step by step",
     "A worked example to follow along", "Recap and what to learn next"],
    ["Setup and tools needed for {t}", "Building a real example step by step",
     "Fixing errors made along the way", "Finished result you can copy"],
    ["Advanced angles of {t}", "Quality checklist for professional work",
     "Fixing broken real-world examples", "Common beginner mistakes and fixes"],
]


def _fallback_daily_plan(course: str, month_title: str, topics: "list[str]",
                         track: str, month_no: int, time: str = "",
                         daily_times=None) -> "list[dict]":
    """Deterministic per-day expansion of the roadmap topics — no AI key needed.
    Every class day the student chose still gets a concrete topic, breakdown, task
    and video search. Days the student left blank have no class."""
    dates = _plan_dates(track, time=time, daily_times=daily_times)
    clean_topics = [str(t).strip() for t in (topics or []) if str(t).strip()] or [course]
    per_topic = max(1, round(len(dates) / len(clean_topics)))
    days = []
    for i, slot in enumerate(dates):
        parent = clean_topics[min(len(clean_topics) - 1, i // per_topic)]
        kind_idx = i % len(_PLAN_KINDS)
        kind, bullets, task_tpl = _PLAN_KINDS[kind_idx]
        days.append({
            "n": i + 1, **slot,
            "parent": parent,
            "topic": f"{parent} — {kind}",
            "breakdown": [b.format(t=parent, c=course) for b in bullets],
            "task": task_tpl.format(t=parent),
            "video_query": f"{parent} {(_VIDEO_ANGLES[kind_idx])}",
            "video_alt_query": f"{parent} tutorial for beginners",
            "video_checklist": [c.format(t=parent) for c in _VIDEO_CHECKLISTS[kind_idx]],
        })
    return days


def _ai_daily_plan(course: str, month_title: str, topics: "list[str]",
                   track: str, month_no: int, time: str = "",
                   daily_times=None, progress=None) -> "list[dict] | None":
    """MiroFish AI writes the detailed day-by-day lessons for every class day the
    student chose (one week at a time — a whole month in one request overflows the
    model's output window). Returns None on any failure so the caller keeps
    the deterministic plan instead of going empty. `progress(pct, step)` is
    called after each week so the dashboard job can show real movement."""
    try:
        dates = _plan_dates(track, time=time, daily_times=daily_times)
        clean = [str(t).strip() for t in (topics or []) if str(t).strip()] or [course]
        listing = "\n".join(f"- {t}" for t in clean)
        week_numbers = sorted({d["week"] for d in dates})
        total_weeks = len(week_numbers)
        days = []
        for wi, week_no in enumerate(week_numbers):
            week_dates = [d for d in dates if d["week"] == week_no]
            n = len(week_dates)
            done_so_far = ", ".join(d["topic"] for d in days[-3:]) or "none — this is the first week"
            slot_lines = "\n".join(
                f"Day slot {i + 1}: {d['weekday']} {d['time']} (date {d['date']})"
                for i, d in enumerate(week_dates))
            prompt = (
                f"You are MiroFish AI, the curriculum designer AND educational video finder "
                f"for BOI RSU, a live online school.\n"
                f"Course: {course}\n"
                f"Month {month_no} of the program: \"{month_title}\". Classes run DAILY.\n"
                f"The month's roadmap topics are:\n{listing}\n\n"
                f"This is WEEK {week_no} of {total_weeks} of the month. The class meets {n} times this week:\n"
                f"{slot_lines}\n"
                f"Lessons already planned in earlier weeks: {done_so_far}.\n\n"
                f"Write this week's detailed daily lessons: ONE lesson per class slot, "
                f"advancing through the roadmap topics without repeating earlier lessons "
                f"(a hard topic may span several days; easier ones share a day).\n"
                f"Return ONLY a JSON array with exactly {n} objects, in this exact shape:\n"
                f'[{{"topic": "specific lesson title for that day (under 90 chars, concrete — e.g. '
                f"'CSS box model: margin, border, padding & box-sizing')\", "
                f"\"parent\": \"which roadmap topic this day belongs to\", "
                f"\"breakdown\": [\"4-5 short bullets: exactly what will be taught/live-coded, in teaching order\"], "
                f"\"task\": \"the concrete hands-on task or deliverable for that day (1-2 sentences)\", "
                f"\"video_query\": \"the ONE YouTube search phrase a beginner should watch for this lesson\", "
                f"\"video_alt_query\": \"a second, broader YouTube search phrase as backup if the first finds nothing\", "
                f"\"video_checklist\": [\"3-5 short items (max 8 words each) the ideal lesson video MUST cover, fundamentals first\"]}}]\n"
                f"VIDEO FINDER RULES (apply to every video_query and video_alt_query):\n"
                f"- Topic first, depth word after — build each phrase from these templates: "
                f"'[topic] full course', '[topic] complete guide for beginners', "
                f"'[topic] crash course', '[topic] explained'. "
                f"Choose the template that best matches the day's lesson.\n"
                f"- Name the day's key sub-skills inside the phrase so the search matches THIS "
                f"lesson, not the whole topic in general.\n"
                f"- Target long-form teaching videos (15+ minutes, not Shorts). For fast-moving "
                f"subjects (software, AI, frameworks, tools) add the current year "
                f"({datetime.now().year}) to the phrase.\n"
                f"- Default level is beginner — include 'for beginners' when it adds precision.\n"
                f"- video_alt_query must be BROADER than video_query (drop the narrowest "
                f"sub-skill) so a failed first search still finds something worth watching.\n"
                f"- Never invent or name specific channels, video titles, URLs, dates or view "
                f"counts — you only describe WHAT to search for; the video pipeline verifies "
                f"every real result later.\n"
                f"Teaching rules: beginner-friendly and practical, no generic filler. Every bullet must name "
                f"real sub-skills, commands or artifacts. No text outside the JSON."
            )
            raw = ai_bridge.ai_module().ai(ai_bridge.client(), prompt, max_tokens=6000)
            if ai_bridge._is_ai_error(raw):
                # One retry for transient provider hiccups (e.g. "Connection error")
                raw = ai_bridge.ai_module().ai(ai_bridge.client(), prompt, max_tokens=6000)
            arr = [] if ai_bridge._is_ai_error(raw) else (ai_bridge._extract_json_array(raw) or [])
            rows = []
            if arr:
                for i, slot in enumerate(week_dates):
                    item = arr[i] if i < len(arr) and isinstance(arr[i], dict) else {}
                    topic = str(item.get("topic") or "").strip()
                    if not topic:
                        rows = []            # incomplete AI answer -> fallback week
                        break
                    rows.append((slot, item, topic))
            if not rows:
                # This week's AI call failed twice: fill it from the deterministic
                # expansion instead of discarding the weeks already planned.
                fb = {d.get("date"): d for d in _fallback_daily_plan(
                    course, month_title, clean, track, month_no, time, daily_times)}
                for slot in week_dates:
                    d = dict(fb.get(slot.get("date")) or {})
                    if not d:
                        continue
                    d["n"] = len(days) + 1
                    d["source"] = "standard"
                    days.append(d)
                if progress:
                    progress(15 + int(75 * (wi + 1) / total_weeks),
                             f"Week {week_no} of {total_weeks} from the standard plan (AI busy)")
                continue
            for slot, item, topic in rows:
                breakdown = [str(b).strip()[:220] for b in (item.get("breakdown") or []) if str(b).strip()]
                raw_check = item.get("video_checklist")
                if isinstance(raw_check, str):   # some models send one string, not a list
                    raw_check = [raw_check]
                checklist = [str(c).strip()[:120] for c in (raw_check or [])[:6] if str(c).strip()]
                days.append({
                    "n": len(days) + 1, **slot,
                    "parent": str(item.get("parent") or "").strip()[:90] or clean[0],
                    "topic": topic[:130],
                    "breakdown": breakdown[:8],
                    "task": str(item.get("task") or "").strip()[:400],
                    "video_query": str(item.get("video_query") or topic).strip()[:140],
                    "video_alt_query": str(item.get("video_alt_query") or "").strip()[:140],
                    "video_checklist": checklist,
                    "source": "ai",
                })
            if progress:
                progress(15 + int(75 * (wi + 1) / total_weeks),
                         f"Week {week_no} of {total_weeks} planned — {len(days)} daily lessons written")
        return days
    except Exception:
        return None


def _daily_plan_response(career_path: str, month_no: int, track: str,
                         time: str = "", daily_times=None) -> "dict | None":
    career_path = _resolve_career_path(career_path)
    roadmap = boirsu.CAREER_ROADMAPS.get(career_path)
    if not roadmap:
        return None
    months = roadmap.get("monthly_plan") or []
    node = next((m for m in months if m.get("month") == month_no), months[0] if months else None)
    if not node:
        return None
    course = roadmap.get("title") or career_path
    key = _plan_key(career_path, node.get("month"), track, daily_times)
    plan = _load_daily_plans().get(key)
    if not plan:
        plan = {
            "key": key, "career_path": career_path, "course": course,
            "month": node.get("month", 1), "month_title": node.get("title", ""),
            "track": track, "duration_mins": 60, "source": "standard",
            "generated": datetime.now().isoformat(timespec="seconds"),
            "days": _fallback_daily_plan(course, node.get("title", ""),
                                         list(node.get("topics") or []), track,
                                         node.get("month", 1), time, daily_times),
        }
        all_plans = _load_daily_plans()
        all_plans[key] = plan
        _save_daily_plans(all_plans)
    # The lesson CONTENT does not depend on the clock, so a cached plan is
    # re-labelled with THIS student's preferred times on the way out. Change
    # your registration times and the whole timetable moves with you instantly.
    chosen = _parse_daily_times(daily_times) if daily_times else {}
    if chosen:
        # Re-label each day with its own chosen clock (from the per-day dict),
        # falling back to the legacy single `time` only when a day is missing.
        plan = {**plan,
                "preferred_time": list(chosen.values())[0],
                "time_source": "student",
                "preferred_daily_times": dict(chosen),
                "days": [{**d, "time": chosen.get(d["weekday"], _sanitize_time(time, ""))}
                         for d in plan.get("days", [])]}
    else:
        clock = _sanitize_time(time, "")
        if clock:
            plan = {**plan,
                    "preferred_time": clock,
                    "time_source": "student",
                    "days": [{**d, "time": clock} for d in plan.get("days", [])]}
    return plan


@app.get("/api/ai/daily-plan/<career_path>")
def daily_plan_get(career_path):
    """Day-by-day lesson plan for one month of a career path (cached).

    ?time=HH:MM         legacy single daily hour (every day at that time).
    ?daily_times=JSON   per-day dict, e.g.
                         {"Monday":"18:00","Tuesday":"14:00","Wednesday":"","Thursday":"20:00",...}
                         — days left blank / "none" have no class. The timetable,
                         roadmap and AI lesson plan all schedule themselves around
                         exactly the days and hours the student chose.
    """
    month_no = request.args.get("month", type=int) or 1
    track = request.args.get("track", "")
    time = request.args.get("time", "")
    daily_times_raw = request.args.get("daily_times", "")
    daily_times = None
    if daily_times_raw:
        try:
            parsed = json.loads(daily_times_raw)
            if isinstance(parsed, dict):
                daily_times = parsed
        except (ValueError, TypeError):
            # Not valid JSON — fall back to the legacy single time.
            daily_times = None
    if daily_times is None:
        # First-paint calls may not carry the per-day grid yet — use the
        # student's SAVED registration grid (opted-out days get no class).
        daily_times = _student_daily_times(request.args.get("student_id", ""))
    plan = _daily_plan_response(career_path, month_no, track, time, daily_times)
    if plan is None:
        return jsonify({"success": False, "error": f"Unknown career path: {career_path}"}), 404
    return jsonify({"success": True, "plan": plan, "ai_available": ai_bridge.ai_key_ready()})


def _run_daily_plan_job(job_id: str, career_path: str, month_no: int, track: str,
                        course: str, time: str = "", daily_times=None):
    _daily_plan_jobs[job_id]["status"] = "running"
    _daily_plan_jobs[job_id]["step"] = "MiroFish AI is writing your day-by-day lessons"
    _daily_plan_jobs[job_id]["pct"] = 15
    try:
        roadmap = boirsu.CAREER_ROADMAPS.get(career_path)
        months = (roadmap or {}).get("monthly_plan") or []
        node = next((m for m in months if m.get("month") == month_no), months[0] if months else None)
        if not node:
            raise RuntimeError(f"unknown career path or month: {career_path} #{month_no}")
        course_name = course or (roadmap.get("title") if roadmap else "") or career_path
        _daily_plan_jobs[job_id]["pct"] = 15

        def _progress(pct, step):
            _daily_plan_jobs[job_id].update(pct=max(15, min(95, pct)), step=step)

        days = _ai_daily_plan(course_name, node.get("title", ""),
                              list(node.get("topics") or []), track, month_no,
                              time, daily_times, _progress)
        if not days:
            raise RuntimeError("the AI returned an unusable plan — try again, or keep the standard breakdown")
        chosen = _parse_daily_times(daily_times) if daily_times else {}
        plan = {
            "key": _plan_key(career_path, node.get("month"), track, daily_times),
            "career_path": career_path, "course": course_name,
            "month": node.get("month", 1), "month_title": node.get("title", ""),
            "track": track, "duration_mins": 60, "source": "ai",
            "preferred_time": list(chosen.values())[0] if chosen else _sanitize_time(time, "18:00"),
            "preferred_daily_times": dict(chosen) if chosen else None,
            "generated": datetime.now().isoformat(timespec="seconds"),
            "days": days,
        }
        all_plans = _load_daily_plans()
        all_plans[plan["key"]] = plan
        _save_daily_plans(all_plans)
        _daily_plan_jobs[job_id].update(status="done", step="Daily plan ready", pct=100)
        broadcast("daily_plan_updated", {
            "career_path": career_path, "month": plan["month"], "course": course_name,
        })
    except Exception as exc:
        _daily_plan_jobs[job_id].update(status="error", step="Failed",
                                        error=str(exc)[:240])


@app.post("/api/ai/daily-plan/<career_path>/generate")
def daily_plan_generate(career_path):
    """MiroFish AI rewrites the month's daily lessons in the background."""
    if not ai_bridge.ai_key_ready():
        return jsonify({"success": False,
                        "error": "MiroFish AI is not configured — set NVIDIA_API_KEY on the server to unlock AI-written daily lessons."}), 503
    body = request.get_json(silent=True) or {}
    try:
        month_no = int(body.get("month") or 1)
    except (TypeError, ValueError):
        month_no = 1
    track = (body.get("track") or "").strip()
    time = _sanitize_time(body.get("time"), "")
    daily_times = (body.get("daily_times") or body.get("time")
                   or (body.get("preferred_daily_times") or {}))
    if not isinstance(daily_times, dict):
        daily_times = None if not daily_times else {}
    job_id = uuid.uuid4().hex[:12]
    _daily_plan_jobs[job_id] = {"status": "queued", "step": "Queued", "pct": 3, "error": ""}
    threading.Thread(target=_run_daily_plan_job,
                     args=(job_id, career_path, month_no, track,
                           (body.get("course") or "").strip()[:120], time, daily_times),
                     daemon=True).start()
    return jsonify({"success": True, "job_id": job_id})


@app.get("/api/ai/daily-plan/job/<job_id>")
def daily_plan_job(job_id):
    job = _daily_plan_jobs.get(job_id)
    if not job:
        return jsonify({"success": False, "error": "unknown job"}), 404
    return jsonify({"success": True, **job})


# ------------------------------------------------------------------
# AI CLASS â€" launch ai_learning_system_v4 (14).py and stream status
# ------------------------------------------------------------------
_ai_process: "subprocess.Popen | None" = None
_ai_process_lock = threading.Lock()


@app.post("/api/start-ai-class")
def start_ai_class():
    """Start the AI learning system for a topic. Streams progress via SSE."""
    global _ai_process
    body = request.get_json(silent=True) or {}
    topic = body.get("topic", "").strip()
    career_path = body.get("career_path", "").strip()
    month = body.get("month")

    if not topic:
        return jsonify({"success": False, "error": "topic required"}), 400

    with _ai_process_lock:
        if _ai_process and _ai_process.poll() is None:
            return jsonify({"success": False, "error": "AI class already running"}), 409

        # Launch the AI system in background
        ai_script = os.path.join(os.path.dirname(__file__),
                                  "ai_learning_system_v4 (14).py")
        env = os.environ.copy()
        env["AI_LEARNING_TOPIC"] = topic
        env["FAST_MODE"] = "true"  # quicker generation for web UI

        try:
            _ai_process = subprocess.Popen(
                [sys.executable, ai_script],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=os.path.dirname(ai_script),
            )
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

    # Notify all connected clients that AI class started
    broadcast("ai_class_started", {
        "topic": topic,
        "career_path": career_path,
        "month": month,
    })

    # Stream AI output in background
    def tail_ai_output():
        if not _ai_process or not _ai_process.stdout:
            return
        for line in iter(_ai_process.stdout.readline, ""):
            if line.strip():
                broadcast("ai_class_output", {"line": line.rstrip()})
        code = _ai_process.wait()
        broadcast("ai_class_finished", {"exit_code": code})

    threading.Thread(target=tail_ai_output, daemon=True).start()

    return jsonify({"success": True, "status": "AI class started"})


# ==================================================================
# AI LEARNING BRIDGE  (/api/ai/*)
# ------------------------------------------------------------------
# Everything below drives studentdashboard.vue from real data. It goes
# through ai_bridge, which loads "ai_learning_system_v4 (14).py" by path
# and calls only its non-interactive functions -- unlike /api/start-ai-class
# above, which spawns the CLI and therefore blocks on input() forever.
# ==================================================================
import ai_bridge  # noqa: E402


def _bridge_error(exc) -> tuple:
    """AI-side failures are expected (missing keys, network) -> 503, not 500."""
    return jsonify({"success": False, "error": str(exc)[:300]}), 503


@app.get("/api/ai/status")
def ai_status():
    """Which keys are present and whether the AI script loaded at all."""
    return jsonify(ai_bridge.status())


@app.post("/api/ai/course")
def ai_create_course():
    """Start course generation. Returns a job id immediately -- the pipeline
    (web research + ~8 model calls) takes minutes, so it cannot be awaited."""
    body = request.get_json(silent=True) or {}
    topic = (body.get("topic") or "").strip()
    level = (body.get("level") or "beginner").strip()
    if not topic:
        return jsonify({"success": False, "error": "topic required"}), 400
    if len(topic) > 200:
        return jsonify({"success": False, "error": "topic too long"}), 400
    try:
        job_id = ai_bridge.start_course_job(topic, level, on_progress=broadcast)
    except Exception as exc:
        return _bridge_error(exc)
    broadcast("ai_course_started", {"job_id": job_id, "topic": topic})
    return jsonify({"success": True, "job_id": job_id, "topic": topic})


@app.get("/api/ai/job/<job_id>")
def ai_job(job_id):
    """Polling fallback for clients whose EventSource dropped."""
    job = ai_bridge.get_job(job_id)
    if not job:
        return jsonify({"success": False, "error": "unknown job"}), 404
    return jsonify({"success": True, **job})


@app.get("/api/ai/courses")
def ai_courses():
    """Library rows, already shaped like the dashboard's `docs` entries."""
    try:
        return jsonify({"success": True, "courses": ai_bridge.list_courses()})
    except Exception as exc:
        return _bridge_error(exc)


@app.get("/api/ai/course/<course_id>")
def ai_course(course_id):
    course = ai_bridge.get_course(course_id)
    if not course:
        return jsonify({"success": False, "error": "unknown course"}), 404
    # Opening a course warms any quizzes it is still missing (courses built
    # before warming existed, or sections a previous pass failed on). No-ops
    # when they are all cached, and never blocks this response.
    try:
        ai_bridge.warm_quizzes(course_id)
    except Exception:
        pass
    return jsonify({"success": True, "course": course})


@app.get("/api/ai/course/<course_id>/section/<int:section_num>/summary")
def ai_section_summary(course_id, section_num):
    try:
        text = ai_bridge.section_summary(course_id, section_num)
    except Exception as exc:
        return _bridge_error(exc)
    if text is None:
        return jsonify({"success": False, "error": "no summary available"}), 404
    return jsonify({"success": True, "summary": text})


@app.get("/api/ai/course/<course_id>/section/<int:section_num>/resources")
def ai_section_resources(course_id, section_num):
    try:
        data = ai_bridge.section_resources(course_id, section_num)
    except Exception as exc:
        return _bridge_error(exc)
    if data is None:
        return jsonify({"success": False, "error": "unknown section"}), 404
    return jsonify({"success": True, **data})


@app.get("/api/ai/course/<course_id>/section/<int:section_num>/videos")
def ai_section_videos(course_id, section_num):
    """Videos attached at generation time by youtube.enrich_course_with_videos.
    Empty list carries a reason (missing key vs none found) so the panel can
    explain itself the same way Resources does."""
    data = ai_bridge.section_videos(course_id, section_num)
    if data is None:
        return jsonify({"success": False, "error": "unknown section"}), 404
    return jsonify({"success": True, **data})


# /api/videos is the path the classroom frontend (aiClient.getTopicVideos)
# and the student dashboard call; /api/ai/videos is the same lookup's
# original path. One handler, two routes, so every caller works.
@app.get("/api/ai/videos")
@app.get("/api/videos")
def ai_videos():
    """Standalone lookup (youtube.get_boi_course_videos) for any topic."""
    topic = (request.args.get("topic") or "").strip()
    if not topic:
        return jsonify({"success": True, "videos": []})
    level = (request.args.get("level") or "beginner").strip()
    try:
        limit = max(1, min(int(request.args.get("limit") or 3), 10))
    except ValueError:
        limit = 3
    return jsonify({"success": True, "topic": topic,
                    "videos": ai_bridge.course_videos(topic, level, limit)})


@app.get("/api/ai/course/<course_id>/section/<int:section_num>/quiz")
def ai_section_quiz(course_id, section_num):
    """Questions only -- correct answers stay on the server until submit."""
    fresh = str(request.args.get("fresh", "")).lower() in ("1", "true", "yes")
    try:
        quiz = ai_bridge.build_quiz(course_id, section_num, fresh=fresh)
    except Exception as exc:
        return _bridge_error(exc)
    if not quiz:
        return jsonify({"success": False, "error": "could not build a quiz"}), 404
    return jsonify({"success": True, **quiz})


@app.post("/api/ai/quiz/<quiz_id>/submit")
def ai_quiz_submit(quiz_id):
    """Grade the attempt, then let boirsu.record_quiz_score() update the
    student's avg_quiz_score and overall_grade (boirsu.py:1432)."""
    body = request.get_json(silent=True) or {}
    student_id = (body.get("student_id") or "").strip() or None
    try:
        result = ai_bridge.grade_quiz(quiz_id, body.get("answers"), student_id)
    except Exception as exc:
        return _bridge_error(exc)
    if result is None:
        return jsonify({"success": False, "error": "unknown quiz"}), 404
    if result.get("student"):
        result["student"] = _student_payload(result["student"])
        broadcast("quiz_recorded", {
            "student_id": student_id,
            "topic": result.get("topic"),
            "percentage": result.get("percentage"),
            "overall_grade": result["student"].get("overall_grade"),
        })
    return jsonify({"success": True, **result})


@app.post("/api/ai/ask")
def ai_ask():
    """Tutor Q&A, grounded in the section the student is reading."""
    body = request.get_json(silent=True) or {}
    question = (body.get("question") or "").strip()
    if not question:
        return jsonify({"success": False, "error": "question required"}), 400
    section = body.get("section")
    try:
        answer = ai_bridge.ask(question, body.get("course_id"),
                               int(section) if section else None)
    except Exception as exc:
        return _bridge_error(exc)
    if not answer:
        return jsonify({"success": False, "error": "tutor unavailable"}), 503
    return jsonify({"success": True, "answer": answer})


@app.post("/api/ai/classroom/ask")
def ai_classroom_ask():
    """Live-classroom tutor Q&A grounded in the YouTube lesson being watched
    and, optionally, a base64 JPEG snapshot of the student's shared screen."""
    body = request.get_json(silent=True) or {}
    question = (body.get("question") or "").strip()
    if not question:
        return jsonify({"success": False, "error": "question required"}), 400
    try:
        answer = ai_bridge.classroom_ask(
            question,
            lesson=body.get("lesson"),
            history=body.get("history"),
            image_b64=(body.get("image") or "").strip() or None,
        )
    except Exception as exc:
        return _bridge_error(exc)
    if not answer:
        return jsonify({"success": False, "error": "tutor unavailable"}), 503
    return jsonify({"success": True, "answer": answer})


def _parse_quiz_json(text):
    """Best-effort extraction of a quiz JSON array from a model answer."""
    cleaned = (text or "").strip()
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.MULTILINE).strip()
    start, end = cleaned.find("["), cleaned.rfind("]")
    if start == -1 or end <= start:
        return []
    try:
        data = json.loads(cleaned[start:end + 1])
    except (ValueError, TypeError):
        return []
    if not isinstance(data, list):
        return []
    out = []
    for item in data:
        if not isinstance(item, dict):
            continue
        q = str(item.get("q") or item.get("question") or "").strip()
        options = [str(o).strip() for o in (item.get("options") or []) if str(o).strip()]
        if not q or len(options) < 2:
            continue
        try:
            answer = int(item.get("answer"))
        except (TypeError, ValueError):
            answer = 0
        if not (0 <= answer < len(options)):
            answer = 0
        out.append({
            "q": q[:400],
            "options": options[:4],
            "answer": answer,
            "why": str(item.get("why") or item.get("explanation") or "")[:300],
        })
    return out


def _parse_object_json(text, keys):
    """Best-effort extraction of a flat JSON object with the wanted keys from a
    model answer (tolerates markdown fences and stray prose around it)."""
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z0-9_]*\s*|\s*```$", "", cleaned).strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        obj = json.loads(cleaned[start:end + 1])
    except Exception:
        return None
    if not isinstance(obj, dict):
        return None
    out = {k: str(obj.get(k) or "").strip() for k in keys}
    return out if any(out.values()) else None


@app.post("/api/ai/classroom/quiz")
def ai_classroom_quiz():
    """Quiz generator for the classroom: grounded in the lesson video's
    transcript when one just played, or in an explicit `topic` the teacher
    typed (MiroFish AI assist in Teacher Tools). Always returns MCQs in the
    {q, options, answer, why} shape."""
    body = request.get_json(silent=True) or {}
    try:
        count = max(5, min(int(body.get("count") or 12), 15))
    except (TypeError, ValueError):
        count = 12
    topic = (body.get("topic") or "").strip()[:300]
    if topic:
        prompt = (
            f"A teacher is quizzing the class on the topic \"{topic}\" (no lesson "
            f"video is playing). Write a {count}-question multiple-choice quiz "
            f"covering the key ideas of that topic at a classroom level.\n"
            f"Return ONLY a raw JSON array - no prose, no markdown fences. Each "
            f'item must look like: {{"q": "...", "options": ["...","...","...",'
            f'"..."], "answer": <0-3 index of the correct option>, "why": "one '
            f'short sentence explaining the answer"}}.\n'
            f"Exactly {count} items, ordered from easiest to hardest, four options "
            f"each, exactly one correct."
        )
    else:
        prompt = (
            f"The lesson video has JUST FINISHED playing for this student. Write a "
            f"{count}-question multiple-choice quiz strictly from what THAT video "
            f"taught (use its captions/transcript above; fall back to the title/"
            f"topic only if captions are missing).\n"
            f"Return ONLY a raw JSON array - no prose, no markdown fences. Each "
            f'item must look like: {{"q": "...", "options": ["...","...","...",'
            f'"..."], "answer": <0-3 index of the correct option>, "why": "one '
            f'short sentence explaining the answer"}}.\n'
            f"Exactly {count} items, ordered from easiest to hardest, four options "
            f"each, exactly one correct."
        )
    try:
        answer = ai_bridge.classroom_ask(prompt, lesson=body.get("lesson"), max_tokens=3000)
    except Exception as exc:
        return _bridge_error(exc)
    questions = _parse_quiz_json(answer or "")
    if not questions:
        return jsonify({"success": False, "error": "tutor unavailable"}), 503
    return jsonify({"success": True, "questions": questions})


@app.post("/api/ai/classroom/assignment")
def ai_classroom_assignment_draft():
    """Teacher tool: MiroFish AI drafts an assignment (title + instructions)
    from a topic. Nothing is stored or broadcast here — the teacher reviews
    and edits the draft in the popup before sending it to the class."""
    body = request.get_json(silent=True) or {}
    topic = (body.get("topic") or "").strip()[:300]
    if not topic:
        return jsonify({"success": False, "error": "topic required"}), 400
    prompt = (
        f"Draft ONE classroom assignment for the topic \"{topic}\". "
        f"Return ONLY a raw JSON object - no prose, no markdown fences, exactly "
        f"this shape: {{\"title\": \"...\", \"instructions\": \"...\"}}. "
        f"The title is short (under 12 words). The instructions tell students "
        f"exactly what to do and turn in, in 2-4 clear sentences a student can "
        f"follow without help."
    )
    try:
        answer = ai_bridge.classroom_ask(prompt, lesson=None, max_tokens=600)
    except Exception as exc:
        return _bridge_error(exc)
    draft = _parse_object_json(answer or "", ("title", "instructions"))
    if not draft:
        return jsonify({"success": False, "error": "tutor unavailable"}), 503
    return jsonify({"success": True, "title": draft.get("title", ""),
                    "instructions": draft.get("instructions", "")})


@app.post("/api/ai/classroom/timetable")
def ai_classroom_timetable_draft():
    """Teacher tool: MiroFish AI drafts the weekly class timetable with the
    SAME engine that lays out student schedules — build_student_timetable()
    from ai_learning_system_v4 (14).py, track-aware class days and times.
    Date-based sessions are grouped into one clean row per weekday for the
    teacher to review and edit before publishing. Nothing is stored here."""
    body = request.get_json(silent=True) or {}
    course = (body.get("course") or "").strip()[:120] or "Class"
    track = (body.get("track") or "").strip()[:60] or "Weekday · evenings"
    try:
        duration = int(body.get("duration_months") or 3)
    except (TypeError, ValueError):
        duration = 3
    try:
        minutes = int(body.get("class_minutes") or 60)
    except (TypeError, ValueError):
        minutes = 60
    start_date = (body.get("start_date") or "").strip() or None
    try:
        mod = ai_bridge.ai_module()
        sessions = mod.build_student_timetable(
            course_name=course, duration_months=duration, track=track,
            class_minutes=minutes, start_date=start_date)
    except Exception as exc:
        return _bridge_error(exc)
    # Weekly grid: the track's class days/time (the engine's OWN rules for
    # picking days and clocks) with the engine's module topics as subjects,
    # so the draft always covers every class day of the week no matter how
    # the engine's date-walker clustered its date-stamped sessions.
    t_lower = track.lower()
    days = (["Saturday", "Sunday"] if "weekend" in t_lower
            else ["Monday", "Wednesday", "Friday"] if "daytime" in t_lower
            else ["Tuesday", "Thursday", "Saturday"])
    clock = ("18:30" if "evening" in t_lower
             else "10:00" if "daytime" in t_lower else "17:30")
    topics, seen = [], set()
    for s in sessions or []:
        if isinstance(s, dict):
            topic = str(s.get("topic") or "").strip()
            if topic and topic not in seen:
                seen.add(topic)
                topics.append(topic)
    if not topics:
        topics = [f"{course} — Module 1"]
    weekly = [{"day": d, "time": clock, "subject": topics[i % len(topics)][:120]}
              for i, d in enumerate(days)]
    return jsonify({"success": True,
                    "title": f"{course} — weekly class schedule",
                    "sessions": weekly})


# ---------------- post-class W3Schools textbooks (dashboard library) ----------------

_V4_SCRIPT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "ai_learning_system_v4 (14).py")
_v4_module_cache = None
_textbook_jobs = {}  # job_id -> {"status": "running|done|error", "row": {...}|None, "error": ""}


def _load_v4_learning_system():
    """Import the v4 learning script by file path (its name has spaces)."""
    global _v4_module_cache
    if _v4_module_cache is not None:
        return _v4_module_cache
    import importlib.util
    spec = importlib.util.spec_from_file_location("boi_ai_learning_v4", _V4_SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    _v4_module_cache = mod
    return mod


@app.get("/api/textbooks")
def textbooks_list():
    """Library rows for the dashboard, newest first. Filters: ?course= &career_path=

    ?student_id= (optional) adds a per-student `purchased` flag to every priced
    row and strips the raw buyer list (`purchased_by`) from the response, so
    the dashboard can show Buy-vs-Read without leaking other students' ids.
    """
    course = request.args.get("course", "")
    career = request.args.get("career_path", "")
    student_id = str(request.args.get("student_id") or "").strip()
    try:
        rows = boirsu.get_textbook_library(course=course, career_path=career)
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)[:160]}), 500
    out = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        row = dict(row)
        buyers = row.pop("purchased_by", None) or []
        row.pop("purchases", None)          # per-buyer receipts are server-side only
        if student_id:
            row["purchased"] = student_id in buyers
        elif row.get("price", 0):
            row["purchased"] = False
        out.append(row)
    return jsonify({"success": True, "textbooks": out})


@app.get("/api/textbooks/<tb_id>")
def textbook_get(tb_id):
    tb = boirsu.get_class_textbook(tb_id)
    if not tb:
        return jsonify({"success": False, "error": "unknown textbook"}), 404
    return jsonify({"success": True, "textbook": tb})


# ---------------- per-course roadmap library (real reading material) ----------------

# ---- Devsphere Library: AI-written month textbooks ONLY ----
def _library_topic_rows(career_path: str) -> list:
    """Library rows for a course: one row per AI-written month textbook that
    ACTUALLY exists on disk. Nothing is pre-written or fabricated here - a
    month without a book is simply absent, because every book is written by
    textbook_ai (AI_BOOK_PROMPT) and filed right after that month's class
    ends, or the teacher uploads a PDF which lands in the library instantly."""
    key = _resolve_career_path(career_path)
    roadmap = boirsu.CAREER_ROADMAPS.get(key)
    if not roadmap:
        return []
    rows = []
    for plan in roadmap.get("monthly_plan", []):
        month = plan.get("month") or (len(rows) + 1)
        fname = f"textbook_{key}_month{month}.pdf"
        fpath = boirsu.TEXTBOOKS_DIR / fname
        # Only AI-written books are listed: textbook_ai stamps a ".ai" marker
        # beside every file it writes. A month PDF without that marker is a
        # leftover of the removed pre-written engine and must NEVER appear.
        if not fpath.exists() or not fpath.with_suffix(".ai").exists():
            continue
        try:
            st = fpath.stat()
            size_kb = max(1, st.st_size // 1024)
            updated = datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d")
        except Exception:
            size_kb, updated = 1, datetime.now().strftime("%Y-%m-%d")
        title = plan.get("title") or f"Month {month}"
        rows.append({
            # String id so it can never collide with AI-course or
            # post-class-textbook ids in the library's merge-by-id logic.
            "id": f"tb-{key}-m{month}",
            "topic_no": len(rows) + 1,
            "month": month,
            "title": f"Month {month} Textbook — {title}",
            "tag": "AI TextBook",
            "pages": max(1, round(size_kb / 2.5)),
            "size": f"{size_kb} KB",
            "updated": updated,
            "hue": "#3ce6c3",
            "big": False,
            "kind": "topic-textbook",
            "download": "/api/library/pdf/" + career_path + "/" + str(month),
        })
    return rows


@app.get("/api/library/<career_path>")
def library_shelf(career_path):
    try:
        rows = _library_topic_rows(career_path)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 404
    # An EMPTY library is not an error: the month's AI textbook simply has not
    # been written yet (it is written right after that class ends) and the
    # teacher has not uploaded a PDF. The dashboard shows its "wait until
    # after class" empty state for exactly this response.
    return jsonify({"success": True, "docs": rows, "textbooks": rows, "library": rows})


@app.get("/api/library/pdf/<career_path>/<int:month_no>")
def library_topic_pdf(career_path, month_no):
    """Serve one AI-written month textbook.

    This route serves REAL books only. When the month's book has not been
    written yet - it is written automatically right after that class ends -
    the student is told to wait until after class (or use the teacher's
    upload). No pre-written template is ever served in its place.
    """
    key = _resolve_career_path(career_path)
    if key not in boirsu.CAREER_ROADMAPS:
        return jsonify({"success": False, "error": "Unknown career path"}), 404
    inline = request.args.get("inline") == "1"
    fpath = boirsu.TEXTBOOKS_DIR / f"textbook_{key}_month{month_no}.pdf"
    # Serve only AI-stamped books (.ai marker = written by textbook_ai). A bare
    # PDF without the marker is pre-written leftovers and is treated the same
    # as a missing book: the student waits until after class.
    if not fpath.exists() or not fpath.with_suffix(".ai").exists():
        return jsonify({
            "success": False,
            "error": ("This month's textbook has not been written yet. It is "
                      "written automatically right after the class ends - "
                      "please wait until after class. If your teacher uploads "
                      "a PDF it appears in the Library instantly."),
        }), 404
    from flask import send_file as _send_file
    return _send_file(str(fpath), mimetype="application/pdf",
                      as_attachment=not inline,
                      download_name=fpath.name)

def _ensure_month_ai_textbook(course):
    """After a class ends, make sure the month's AI textbook exists.

    Written ONLY by textbook_ai (AI_BOOK_PROMPT) - never pre-written. Months
    that already carry a .ai marker are left untouched; the FIRST month without
    a real AI-written book is written now, so the library fills up one month
    per class, exactly as the school wants it. When the AI engine cannot write
    (no key / model down) this quietly does nothing - the student keeps seeing
    the "wait until after class" state until a later class or teacher upload.
    """
    key = _resolve_career_path(str(course or ""))
    if not key:
        return
    try:
        plans = (boirsu.CAREER_ROADMAPS.get(key) or {}).get("monthly_plan") or []
        for idx, plan in enumerate(plans, 1):
            month = plan.get("month") or idx
            base = boirsu.TEXTBOOKS_DIR / f"textbook_{key}_month{month}.pdf"
            if base.exists() and base.with_suffix(".ai").exists():
                continue        # this month already has its AI-written book
            boirsu.generate_textbook_pdf(key, month)
            break               # one book per class; the next class writes the next month
    except Exception as exc:
        print(f"[textbook-job] month AI textbook ensure skipped: {str(exc)[:120]}")


def _run_textbook_job(job_id, payload):
    """Background half of /api/textbooks/generate.

    Runs the post-class pipeline from ai_learning_system_v4 (14).py:
    video transcript -> merged W3Schools/document-designer prompt ->
    boirsu.save_class_textbook(). The saved row lands in the library index
    immediately, so the book appears on the dashboard whether or not the
    teacher uploads a PDF of their own. This function is what fires when a
    classroom YouTube video ENDS (Classroom.vue -> generateClassTextbook).
    """
    job = _textbook_jobs.setdefault(
        job_id, {"status": "running", "row": None, "error": ""})
    job["status"] = "running"
    try:
        v4 = _load_v4_learning_system()
        video = payload.get("video") or {}
        row = v4.build_class_textbook(
            course=payload.get("course") or "",
            topic=payload.get("topic") or "",
            video_url=video.get("url") or "",
            video_title=video.get("title") or "",
            video_id=video.get("video_id") or "",
            class_number=payload.get("class_number"),
        )
        if not row:
            raise RuntimeError("textbook pipeline returned no library row")
        job.update({"status": "done", "row": row, "error": ""})
        print(f"[textbook-job] {job_id} done -> {str(row.get('title', ''))[:60]}")
        # Live update for open dashboards; the shelf also reloads on mount,
        # so a missed SSE event only delays the card until refresh.
        try:
            broadcast("classroom_textbook", {"room": "", **row})
        except Exception:
            pass
        # The class has ended: if this course's month textbook has not been
        # written yet, write it NOW with the AI engine - never pre-written.
        _ensure_month_ai_textbook(payload.get("course"))
    except Exception as exc:
        job.update({"status": "error", "row": None, "error": str(exc)[:200]})
        print(f"[textbook-job] {job_id} failed: {str(exc)[:160]}")


@app.post("/api/textbooks/generate")
def textbooks_generate():
    """Kick off post-class textbook generation for one video; returns a job id."""
    body = request.get_json(silent=True) or {}
    course = (body.get("course") or "").strip()
    topic = (body.get("topic") or "").strip()
    video = body.get("video") or {}
    if not (course or topic or video):
        return jsonify({"success": False, "error": "course/topic/video required"}), 400
    job_id = uuid.uuid4().hex[:12]
    _textbook_jobs[job_id] = {"status": "queued", "row": None, "error": ""}
    thread = threading.Thread(
        target=_run_textbook_job, args=(job_id, {"course": course, "topic": topic,
                                                 "video": video,
                                                 "class_number": body.get("class_number")}),
        daemon=True)
    thread.start()
    return jsonify({"success": True, "job_id": job_id})


@app.get("/api/textbooks/job/<job_id>")
def textbooks_job(job_id):
    job = _textbook_jobs.get(job_id)
    if not job:
        return jsonify({"success": False, "error": "unknown job"}), 404
    return jsonify({"success": True, **job})


@app.post("/api/student/google-check")
def student_google_check():
    """
    After a Google account is OAuth-verified on the registration gate, the
    frontend asks whether that email already belongs to a registered student.
    Registered -> return the dashboard payload so they can hop straight in;
    otherwise tell the form to prefill the verified email and carry on.
    """
    body = request.get_json(silent=True) or {}
    email = str(body.get("email") or "").strip().lower()
    if not email:
        return jsonify({"success": False, "error": "email required"}), 400
    try:
        students = boirsu.load_students()
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)[:160]}), 500
    student = next((s for s in students.values()
                    if str(s.get("email", "")).strip().lower() == email), None)
    if not student:
        return jsonify({"success": True, "registered": False})
    public = {k: student.get(k) for k in (
        "student_id", "name", "email", "phone", "career_path", "course_name",
        "experience_level", "payment_status", "overall_grade", "avg_quiz_score")}
    public.update({f"access_{k}": v for k, v in boirsu.get_access_state(student).items()
                   if k != "currency"})
    return jsonify({"success": True, "registered": True, "student": public,
                    "has_password": bool(student.get("password_hash"))})


# ---------------- student login (email + password) ----------------

@app.post("/api/student/login")
def student_login():
    """Email+password sign-in. Returns the dashboard payload on success."""
    body = request.get_json(silent=True) or {}
    email = str(body.get("email") or "").strip()
    password = str(body.get("password") or "")
    if not email or not password:
        return jsonify({"success": False, "error": "email and password required"}), 400
    try:
        student = boirsu.verify_student_login(email, password)
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)[:160]}), 500
    if not student:
        return jsonify({"success": False,
                        "error": "Wrong email or password - no matching student account."}), 401
    public = {k: student.get(k) for k in (
        "student_id", "name", "email", "phone", "career_path", "course_name",
        "experience_level", "payment_status", "overall_grade", "avg_quiz_score")}
    return jsonify({"success": True, "student": public})


@app.post("/api/student/set-password")
def student_set_password():
    """Attach a login password to an enrolled student (registration step)."""
    body = request.get_json(silent=True) or {}
    student_id = str(body.get("student_id") or "").strip()
    password = str(body.get("password") or "")
    if not student_id or not password:
        return jsonify({"success": False, "error": "student_id and password required"}), 400
    try:
        result = boirsu.set_student_password(student_id, password)
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)[:160]}), 500
    status = 200 if result.get("ok") else 400
    return jsonify({"success": bool(result.get("ok")), **result}), status


# ---------------- Paystack payment verification ----------------

@app.post("/api/paystack/verify")
def paystack_verify():
    """
    Server-side truth check: verify a Paystack reference with the SECRET key.

    body.months > 0  -> this is a MONTHLY SCHOOL-FEE payment: the student's
    access_paid_through window is extended by that many months (the dashboard
    lock reads exactly this). kind is a free label ('monthly-fees',
    'registration', ...). Re-verifying the same reference never double-extends.
    """
    body = request.get_json(silent=True) or {}
    student_id = str(body.get("student_id") or "").strip()
    reference = str(body.get("reference") or "").strip()
    if not reference:
        return jsonify({"success": False, "error": "reference required"}), 400
    try:
        months = max(0, int(body.get("months") or 0))
    except (TypeError, ValueError):
        months = 0
    kind = str(body.get("kind") or "").strip()[:40]
    result = boirsu.verify_paystack_payment(student_id, reference, months=months, kind=kind)
    http_status = 200 if result.get("verified") else 402
    return jsonify({"success": bool(result.get("verified")), **result}), http_status


@app.post("/api/paystack/verify-textbook")
def paystack_verify_textbook():
    """
    Server-side truth check for a PRICES LIBRARY-PDF purchase (admin/partner
    commerce, kind 'textbook').

    body: {student_id, reference, textbook_id}. Verifies the reference with
    the Paystack SECRET key, checks the amount covers the book's price, then
    records the buyer on the textbook row (`purchased_by`) so
    /api/textbooks/pdf/<id> unlocks for this student — and only this student.
    """
    body = request.get_json(silent=True) or {}
    student_id = str(body.get("student_id") or "").strip()
    reference = str(body.get("reference") or "").strip()
    textbook_id = str(body.get("textbook_id") or "").strip()
    if not reference or not textbook_id:
        return jsonify({"success": False,
                        "error": "reference and textbook_id required"}), 400
    result = boirsu.verify_paystack_book_purchase(student_id, reference, textbook_id)
    http_status = 200 if result.get("verified") else 402
    return jsonify({"success": bool(result.get("verified")), **result}), http_status


@app.get("/api/ai/speak")

@app.get("/api/ai/speak")
def ai_speak():
    """
    Deepgram Aura-2 narration as MP3 bytes for an <audio> element -- the audio
    mode for a generated lesson. The AI script's speak_text() cannot be reused
    directly: it writes a temp file and plays it through mpg123 on the server.
    """
    if not ai_bridge.deepgram_ready():
        return jsonify({"success": False,
                        "error": "DEEPGRAM_API_KEY not set",
                        "hint": "add it to backend/.env and restart"}), 503

    course_id = (request.args.get("course") or "").strip()
    section_num = request.args.get("section")
    text = (request.args.get("text") or "").strip()
    try:
        if course_id and section_num:
            audio = ai_bridge.section_audio(course_id, int(section_num))
            if audio is None:
                return jsonify({"success": False, "error": "unknown section"}), 404
        elif text:
            audio = ai_bridge.synthesize(text[:20000])
        else:
            return jsonify({"success": False,
                            "error": "course+section or text required"}), 400
    except Exception as exc:
        return _bridge_error(exc)

    return Response(audio, mimetype="audio/mpeg", headers={
        "Content-Length": str(len(audio)),
        "Accept-Ranges": "none",
        "Cache-Control": "public, max-age=86400",
    })


# ==================================================================
# LIVE CLASSROOM  --  presence + cohort chat per course (20-30 seats)
# ------------------------------------------------------------------
# In-memory rooms keyed by the normalized course topic. A student joins
# the room for the course they are learning -- the course/display name are
# resolved against boirsu student records when a student_id is supplied --
# appears in everyone's roster through the SSE hub, shares one group chat,
# and follows one synced lesson video. Closed tabs stop pinging and are
# swept after CLASSROOM_STALE_SECS, so the seat count self-heals. 20-30
# concurrent seats is trivial for one Flask thread-per-request process.
# ==================================================================

CLASSROOM_STALE_SECS = 45
CLASSROOM_MAX_MESSAGES = 200
_classroom_rooms: dict = {}
_classroom_lock = threading.Lock()


def _classroom_room_key(course: str) -> str:
    return re.sub(r"\s+", " ", (course or "").strip()).lower() or "general"


def _classroom_get(room: str) -> dict:
    with _classroom_lock:
        return _classroom_rooms.setdefault(
            room, {"participants": {}, "messages": [], "lesson": None,
                   # Cohort chat starts OPEN so students can talk to each other
                   # (and to the teacher) the moment they join. A teacher can
                   # still close it from the top bar -- see
                   # POST /api/classroom/chat-permission.
                   "chat_open": True, "assignments": [],
                   # Go-Live state, shared by the room so students switch to the
                   # live teacher video automatically (no refresh):
                   #   {active, teacher_id, teacher_name, since}
                   "live": None}
        )


def _classroom_sweep(st: dict, now: float) -> bool:
    """Drop participants whose last ping is older than the stale window."""
    gone = [pid for pid, p in st["participants"].items()
            if now - p.get("last_seen", 0) > CLASSROOM_STALE_SECS]
    for pid in gone:
        st["participants"].pop(pid, None)
    return bool(gone)


def _classroom_roster_payload(room: str, st: dict) -> dict:
    parts = sorted(st["participants"].values(), key=lambda p: p.get("joined_at", 0))
    return {
        "room": room,
        "participants": [
            {"id": p["id"], "name": p["name"], "hue": p.get("hue", 210),
             "raised": bool(p.get("raised")), "sharing": bool(p.get("sharing"))}
             | {"role": p.get("role", "student"),
                # cam/mic let every peer draw the right participant tile
                # (video on/off, muted) without waiting for a track to arrive.
                "cam": bool(p.get("cam")), "mic": bool(p.get("mic")),
                "voice_requested": bool(p.get("voice_requested")),
                "voice_approved": bool(p.get("voice_approved"))}
            for p in parts
        ],
        "count": len(parts),
    }


def _classroom_broadcast_roster(room: str, st: dict) -> None:
    broadcast("classroom_roster", _classroom_roster_payload(room, st))


def _classroom_append(st: dict, msg: dict) -> None:
    st["messages"].append(msg)
    del st["messages"][:-CLASSROOM_MAX_MESSAGES]


def _classroom_system_msg(room: str, st: dict, text: str) -> None:
    msg = {"id": uuid.uuid4().hex[:12], "pid": "", "name": "", "hue": 0,
           "kind": "system", "text": text,
           "ts": datetime.now().isoformat(timespec="seconds")}
    _classroom_append(st, msg)
    broadcast("classroom_chat", {"room": room, **msg})


def _classroom_resolve_identity(body: dict) -> tuple:
    """
    boirsu is the source of truth: a known student_id pins the display name
    and -- when the client did not send one -- the course they enrolled in.
    That is how the classroom knows what to teach (and search YouTube for)
    before anything else happens.
    """
    name = (body.get("name") or "").strip()
    course = (body.get("course") or "").strip()
    sid = (body.get("student_id") or "").strip()
    if sid:
        try:
            rec = (boirsu.load_students() or {}).get(sid)
        except Exception:
            rec = None
        if rec:
            name = name or (rec.get("name") or "").strip()
            course = course or (rec.get("career_path") or "").strip()
    return name, course


@app.get("/api/classroom/state")
def classroom_state():
    """Full room snapshot -- first load and SSE reconnects land here."""
    course = request.args.get("course") or ""
    room = _classroom_room_key(course)
    st = _classroom_get(room)
    with _classroom_lock:
        _classroom_sweep(st, time.time())
        roster = _classroom_roster_payload(room, st)
        msgs = list(st["messages"])[-100:]
        lesson = dict(st["lesson"]) if st["lesson"] else None
        chat_open = bool(st.get("chat_open"))
        live = dict(st["live"]) if st.get("live") else None
    return jsonify({"success": True, "room": room, "course": course.strip(),
                    **roster, "messages": msgs, "lesson": lesson,
                    "chat_open": chat_open, "live": live})


@app.post("/api/classroom/join")
def classroom_join():
    body = request.get_json(silent=True) or {}
    name, course = _classroom_resolve_identity(body)
    if not course:
        return jsonify({"success": False, "error": "course required"}), 400
    if not name:
        name = "Guest-" + uuid.uuid4().hex[:4]
    room = _classroom_room_key(course)
    st = _classroom_get(room)
    now = time.time()
    pid = uuid.uuid4().hex[:8]
    hue = int(body.get("hue") or 0) % 360 or sum(map(ord, name)) % 360
    with _classroom_lock:
        _classroom_sweep(st, now)
        st["participants"][pid] = {
            "id": pid, "name": name[:40], "hue": hue, "raised": False,
            "sharing": False, "role": "teacher" if body.get("role") == "teacher" else "student",
            "cam": False, "mic": False,
            "voice_requested": False, "voice_approved": False,
            "joined_at": now, "last_seen": now,
        }
        roster = _classroom_roster_payload(room, st)
        msgs = list(st["messages"])[-100:]
        lesson = dict(st["lesson"]) if st["lesson"] else None
        chat_open = bool(st.get("chat_open"))
        live = dict(st["live"]) if st.get("live") else None
    _classroom_broadcast_roster(room, st)
    _classroom_system_msg(room, st, f"{name} joined the class")
    return jsonify({"success": True, "you": {"id": pid, "name": name, "hue": hue},
                    "room": room, "course": course.strip(),
                    **roster, "messages": msgs, "lesson": lesson,
                    "chat_open": chat_open, "live": live})


@app.post("/api/classroom/ping")
def classroom_ping():
    """Heartbeat + presence flags. Ghosts are swept opportunistically here."""
    body = request.get_json(silent=True) or {}
    course = (body.get("course") or "").strip()
    pid = (body.get("pid") or "").strip()
    if not course or not pid:
        return jsonify({"success": False, "error": "course and pid required"}), 400
    room = _classroom_room_key(course)
    st = _classroom_get(room)
    now = time.time()
    with _classroom_lock:
        _classroom_sweep(st, now)
        p = st["participants"].get(pid)
        if not p:
            return jsonify({"success": False, "error": "rejoin required",
                            "count": len(st["participants"])}), 404
        p["last_seen"] = now
        changed = False
        for flag in ("raised", "sharing", "cam", "mic"):
            if flag in body and bool(body[flag]) != bool(p.get(flag)):
                p[flag] = bool(body[flag])
                changed = True
        count = len(st["participants"])
    if changed:
        _classroom_broadcast_roster(room, st)
    return jsonify({"success": True, "count": count})


@app.post("/api/classroom/say")
def classroom_say():
    """One cohort chat message -> stored in the room ring buffer + SSE fan-out."""
    body = request.get_json(silent=True) or {}
    course = (body.get("course") or "").strip()
    pid = (body.get("pid") or "").strip()
    text = (body.get("text") or "").strip()
    if not course or not pid or not text:
        return jsonify({"success": False, "error": "course, pid and text required"}), 400
    room = _classroom_room_key(course)
    st = _classroom_get(room)
    now = time.time()
    with _classroom_lock:
        _classroom_sweep(st, now)
        p = st["participants"].get(pid)
        if not p:
            return jsonify({"success": False, "error": "rejoin required"}), 404
        if p.get("role") != "teacher" and not st.get("chat_open", False):
            return jsonify({"success": False, "error": "class chat is closed by the teacher"}), 403
        p["last_seen"] = now
    msg = {"id": uuid.uuid4().hex[:12], "pid": pid, "name": p["name"],
           "hue": p.get("hue", 210), "kind": "chat", "text": text[:1000],
           "ts": datetime.now().isoformat(timespec="seconds")}
    _classroom_append(st, msg)
    broadcast("classroom_chat", {"room": room, **msg})
    return jsonify({"success": True, "id": msg["id"]})


@app.post("/api/classroom/voice-request")
def classroom_voice_request():
    """Let a student request microphone permission from the teacher."""
    body = request.get_json(silent=True) or {}
    course = (body.get("course") or "").strip()
    pid = (body.get("pid") or "").strip()
    requested = bool(body.get("requested", True))
    room = _classroom_room_key(course)
    st = _classroom_get(room)
    with _classroom_lock:
        participant = st["participants"].get(pid)
        if not course or not participant:
            return jsonify({"success": False, "error": "course and participant required"}), 404
        if participant.get("role") == "teacher":
            return jsonify({"success": False, "error": "teachers do not need approval"}), 400
        participant["voice_requested"] = requested
        participant["last_seen"] = time.time()
    _classroom_broadcast_roster(room, st)
    return jsonify({"success": True, "voice_requested": requested})


@app.post("/api/classroom/voice-permission")
def classroom_voice_permission():
    """Teacher-only approval or rejection of one student's microphone."""
    body = request.get_json(silent=True) or {}
    course = (body.get("course") or "").strip()
    teacher_pid = (body.get("teacher_pid") or "").strip()
    student_pid = (body.get("student_pid") or "").strip()
    approved = bool(body.get("approved"))
    room = _classroom_room_key(course)
    st = _classroom_get(room)
    with _classroom_lock:
        teacher = st["participants"].get(teacher_pid)
        student = st["participants"].get(student_pid)
        if not teacher or teacher.get("role") != "teacher":
            return jsonify({"success": False, "error": "teacher permission required"}), 403
        if not student or student.get("role") == "teacher":
            return jsonify({"success": False, "error": "student not found"}), 404
        student["voice_requested"] = False
        student["voice_approved"] = approved
    _classroom_broadcast_roster(room, st)
    return jsonify({"success": True, "student_pid": student_pid,
                    "voice_approved": approved})


@app.post("/api/classroom/chat-permission")
def classroom_chat_permission():
    """Teacher-only switch for student text chat in a room."""
    body = request.get_json(silent=True) or {}
    course = (body.get("course") or "").strip()
    pid = (body.get("pid") or "").strip()
    open_chat = bool(body.get("open"))
    if not course or not pid:
        return jsonify({"success": False, "error": "course and pid required"}), 400
    room = _classroom_room_key(course)
    st = _classroom_get(room)
    with _classroom_lock:
        teacher = st["participants"].get(pid)
        if not teacher:
            return jsonify({"success": False, "error": "rejoin required"}), 404
        if teacher.get("role") != "teacher":
            return jsonify({"success": False, "error": "teacher permission required"}), 403
        st["chat_open"] = open_chat
    broadcast("classroom_chat_permission", {"room": room, "chat_open": open_chat})
    return jsonify({"success": True, "chat_open": open_chat})


@app.post("/api/classroom/live")
def classroom_live():
    """Teacher-only Go-Live switch for a room.

    Going live broadcasts `classroom_live` over the SSE hub so every student in
    the cohort switches to the live teacher-video stage instantly, and the state
    is kept on the room so anyone who joins later lands on the live session too.
    Ending the session clears it and drops everyone back to the lesson view.
    """
    body = request.get_json(silent=True) or {}
    course = (body.get("course") or "").strip()
    pid = (body.get("pid") or "").strip()
    active = bool(body.get("active"))
    if not course or not pid:
        return jsonify({"success": False, "error": "course and pid required"}), 400
    room = _classroom_room_key(course)
    st = _classroom_get(room)
    with _classroom_lock:
        _classroom_sweep(st, time.time())
        teacher = st["participants"].get(pid)
        if not teacher:
            return jsonify({"success": False, "error": "rejoin required"}), 404
        if teacher.get("role") != "teacher":
            return jsonify({"success": False, "error": "teacher permission required"}), 403
        if active:
            st["live"] = {"active": True, "teacher_id": pid,
                          "teacher_name": teacher.get("name", "Teacher"),
                          "since": int(time.time())}
        else:
            st["live"] = None
        live = dict(st["live"]) if st["live"] else None
    broadcast("classroom_live", {"room": room, "live": live, "active": active})
    _classroom_system_msg(
        room, st,
        ("🎥 " + (live or {}).get("teacher_name", "The teacher") +
         " is LIVE — the live class is starting now.") if active
        else "🔴 The teacher ended the live class."
    )
    return jsonify({"success": True, "live": live})


@app.post("/api/classroom/leave")
def classroom_leave():
    body = request.get_json(silent=True) or {}
    course = (body.get("course") or "").strip()
    pid = (body.get("pid") or "").strip()
    if not course or not pid:
        return jsonify({"success": False, "error": "course and pid required"}), 400
    room = _classroom_room_key(course)
    st = _classroom_get(room)
    with _classroom_lock:
        p = st["participants"].pop(pid, None)
        if not p:
            return jsonify({"success": True, "count": len(st["participants"])})
        name = p["name"]
        # A live teacher leaving (closed tab / signed out) must not leave the
        # class stuck on a dead live session — clear it for everyone.
        went_off_air = bool(st.get("live")) and st["live"].get("teacher_id") == pid
        if went_off_air:
            st["live"] = None
    _classroom_broadcast_roster(room, st)
    if went_off_air:
        broadcast("classroom_live", {"room": room, "live": None, "active": False})
    _classroom_system_msg(room, st, f"{name} left the class")
    return jsonify({"success": True})


@app.post("/api/classroom/signal")
def classroom_signal():
    """Relay WebRTC negotiation data to one participant in a classroom.

    Media never passes through Flask; this endpoint only carries SDP and ICE
    setup messages over the existing classroom SSE channel.
    """
    body = request.get_json(silent=True) or {}
    course = (body.get("course") or "").strip()
    sender = (body.get("sender") or "").strip()
    target = (body.get("target") or "").strip()
    kind = (body.get("kind") or "").strip()
    payload = body.get("payload")
    if not course or not sender or not target or kind not in {"offer", "answer", "ice", "screen-state"}:
        return jsonify({"success": False, "error": "course, sender, target and valid kind required"}), 400
    room = _classroom_room_key(course)
    st = _classroom_get(room)
    with _classroom_lock:
        _classroom_sweep(st, time.time())
        if sender not in st["participants"] or target not in st["participants"]:
            return jsonify({"success": False, "error": "participant not found"}), 404
    broadcast("classroom_signal", {"room": room, "sender": sender, "target": target,
                                    "kind": kind, "payload": payload})
    return jsonify({"success": True})


@app.post("/api/classroom/lesson")
def classroom_lesson_set():
    """Sync the lesson video across the whole cohort -- everyone watches
    the same YouTube lesson (whoever picks first sets it for the room)."""
    body = request.get_json(silent=True) or {}
    course = (body.get("course") or "").strip()
    pid = (body.get("pid") or "").strip()
    video = body.get("video") or {}
    if not course or not isinstance(video, dict) or not (
            video.get("url") or video.get("embed_url") or video.get("watch_url")):
        return jsonify({"success": False,
                        "error": "course and a video url required"}), 400
    room = _classroom_room_key(course)
    st = _classroom_get(room)
    setter = ""
    with _classroom_lock:
        p = st["participants"].get(pid)
        if p:
            p["last_seen"] = time.time()
            setter = p["name"]
        entry = {"video": {
            "title": str(video.get("title") or "")[:200],
            "url": str(video.get("url") or video.get("watch_url") or "")[:500],
            "embed_url": str(video.get("embed_url") or "")[:500],
            "thumbnail": str(video.get("thumbnail") or "")[:500],
        }, "set_by": setter,
           "ts": datetime.now().isoformat(timespec="seconds")}
        st["lesson"] = entry
    broadcast("classroom_lesson", {"room": room, **entry})
    return jsonify({"success": True, **entry})


# ==================================================================
# TEACHER TOOLS  --  PDF textbooks, assignments (classroom -> dashboard)
# ------------------------------------------------------------------
# Teacher-only actions taken inside /classroom/teacher. Uploaded PDFs land in
# the shared textbook library (/api/textbooks) that studentdashboard.vue reads,
# and assignments broadcast on SSE so the students' dashboards update live.
# ==================================================================

@app.post("/api/classroom/textbook")
def classroom_textbook_upload():
    """Teacher uploads a PDF textbook for the class (base64 in the JSON body).

    The file is stored next to the AI-generated class textbooks and registered
    in the same library index, so the student dashboard's Library shows it
    immediately (GET /api/textbooks). Also broadcasts classroom_textbook.
    """
    body = request.get_json(silent=True) or {}
    course = (body.get("course") or "").strip()
    pid = (body.get("pid") or "").strip()
    title = (body.get("title") or "").strip()[:180]
    file_name = str(body.get("file_name") or "textbook.pdf")[:200]
    file_data = body.get("file_data") or ""
    if not course or not pid or not title or not file_data:
        return jsonify({"success": False,
                        "error": "course, pid, title and file_data required"}), 400
    room = _classroom_room_key(course)
    st = _classroom_get(room)
    with _classroom_lock:
        teacher = st["participants"].get(pid)
        if not teacher:
            return jsonify({"success": False, "error": "rejoin required"}), 404
        if teacher.get("role") != "teacher":
            return jsonify({"success": False, "error": "teacher permission required"}), 403

    try:
        raw = base64.b64decode(re.sub(r"\s+", "", file_data))
    except Exception as exc:
        return jsonify({"success": False,
                        "error": "could not decode file: %s" % str(exc)[:120]}), 400
    if raw[:4] != b"%PDF":
        return jsonify({"success": False, "error": "Only PDF files are supported."}), 400

    tb_id = "pdf_" + uuid.uuid4().hex[:12]
    try:
        with open(os.path.join(str(boirsu.TEXTBOOKS_DIR), f"{tb_id}.pdf"), "wb") as fh:
            fh.write(raw)
    except Exception as exc:
        return jsonify({"success": False,
                        "error": "could not save file: %s" % str(exc)[:120]}), 503

    pages = max(1, int(len(raw) / 50000) + 1)
    size_mb = len(raw) / (1024.0 * 1024.0)
    row = {
        "id": tb_id, "kind": "pdf-textbook", "title": title,
        "tag": "PDF TextBook", "pages": pages,
        "size": f"{max(size_mb, 0.1):.1f} MB",
        "updated": datetime.now().strftime("%d %b %Y"),
        "hue": "teal", "big": "PDF", "ai": False,
        "course": course, "pdf_id": tb_id, "file_name": file_name,
        # Admin/partner commerce fields — price in Naira (0 = free) and the
        # read-only lock (students can read the PDF but cannot download it).
        # Managed later via POST /api/textbooks/settings/<tb_id>.
        "price": 0, "read_only": False,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    index = boirsu._json_file_load(boirsu._textbooks_index_path()) or []
    if not isinstance(index, list):
        index = []
    index = [r for r in index if isinstance(r, dict) and r.get("id") != tb_id]
    index.insert(0, row)
    boirsu._json_file_save(boirsu._textbooks_index_path(), index)

    broadcast("classroom_textbook", {"room": room, **row})
    return jsonify({"success": True, "textbook": row})


@app.get("/api/textbooks/pdf/<pdf_id>")
def textbook_pdf(pdf_id):
    """Serve a teacher-uploaded PDF textbook.

    Default: ?inline=1 opens it in the browser viewer, otherwise it downloads.
    When the admin/partner locked the book as READ-ONLY, the file is ALWAYS
    served inline (viewer only, never as an attachment download) and the
    X-Textbook-Read-Only header marks it for the front end.
    """
    if not pdf_id or not pdf_id.startswith("pdf_"):
        return jsonify({"success": False, "error": "unknown file"}), 404
    path = os.path.join(str(boirsu.TEXTBOOKS_DIR), f"{os.path.basename(pdf_id)}.pdf")
    if not os.path.exists(path):
        return jsonify({"success": False, "error": "file not found"}), 404
    row = _textbook_index_row(pdf_id)
    inline = request.args.get("inline") == "1"
    file_label = (row or {}).get("file_name") or (pdf_id + ".pdf")

    # Admin/partner commerce: a PRICED book is only served to students who
    # bought it (their student_id must appear in the row's purchased_by list,
    # written by POST /api/paystack/verify-textbook). Everyone else gets 402
    # so the dashboard shows the Buy flow instead of the file.
    if row and max(0, int(row.get("price") or 0)) > 0:
        student_id = str(request.args.get("student_id") or "").strip()
        buyers = row.get("purchased_by") or []
        if not student_id or student_id not in buyers:
            return jsonify({"success": False,
                            "error": "payment required for this textbook",
                            "price": max(0, int(row.get("price") or 0)),
                            "textbook_id": pdf_id}), 402

    if row and row.get("read_only"):
        resp = send_file(path, mimetype="application/pdf", as_attachment=False,
                         download_name=file_label)
        resp.headers["X-Textbook-Read-Only"] = "1"
        return resp
    return send_file(path, mimetype="application/pdf", as_attachment=not inline,
                     download_name=file_label)


def _textbook_index_row(tb_id):
    """One row of the shared textbook library index, or None when unknown."""
    try:
        index = boirsu._json_file_load(boirsu._textbooks_index_path()) or []
    except Exception:
        return None
    if not isinstance(index, list):
        return None
    return next((r for r in index if isinstance(r, dict) and r.get("id") == tb_id), None)


@app.post("/api/textbooks/settings/<tb_id>")
def textbook_settings(tb_id):
    """Admin/partner pricing + access control for a library PDF textbook.

    Body: {"role": "admin"|"partner", "price": <int naira, 0 = free>,
           "read_only": <bool>}. Only the supplied fields change, so either
    can be updated alone. Students see both fields through GET /api/textbooks;
    read-only books are served inline-only by /api/textbooks/pdf/<id>.
    """
    body = request.get_json(silent=True) or {}
    role = str(body.get("role") or "").strip().lower()
    if role not in ("admin", "partner"):
        return jsonify({"success": False,
                        "error": "admin or partner permission required"}), 403
    index = boirsu._json_file_load(boirsu._textbooks_index_path()) or []
    if not isinstance(index, list):
        index = []
    row = next((r for r in index if isinstance(r, dict) and r.get("id") == tb_id), None)
    if row is None:
        return jsonify({"success": False, "error": "unknown textbook"}), 404

    changed = []
    if "price" in body:
        try:
            price = int(float(body.get("price") or 0))
        except (TypeError, ValueError):
            return jsonify({"success": False, "error": "price must be a number"}), 400
        row["price"] = max(0, price)
        changed.append("price")
    if "read_only" in body:
        row["read_only"] = bool(body.get("read_only"))
        changed.append("read_only")
    if not changed:
        return jsonify({"success": False, "error": "nothing to update"}), 400
    row["price_set_by"] = role
    row["price_set_at"] = datetime.now().isoformat(timespec="seconds")

    index = [r for r in index if not (isinstance(r, dict) and r.get("id") == tb_id)]
    index.insert(0, row)
    boirsu._json_file_save(boirsu._textbooks_index_path(), index)

    # Live dashboards pick the change up through the same SSE event a new
    # upload uses — the full row (now carrying price/read_only) is re-merged.
    if row.get("course"):
        try:
            broadcast("classroom_textbook",
                      {"room": _classroom_room_key(str(row.get("course"))), **row})
        except Exception:
            pass
    return jsonify({"success": True, "textbook": row})


@app.post("/api/classroom/assignment")
def classroom_assignment_new():
    """Teacher gives an assignment to the class. Stored per room and broadcast
    on SSE so every student's dashboard (studentdashboard.vue) picks it up."""
    body = request.get_json(silent=True) or {}
    course = (body.get("course") or "").strip()
    pid = (body.get("pid") or "").strip()
    title = (body.get("title") or "").strip()
    if not course or not pid or not title:
        return jsonify({"success": False,
                        "error": "course, pid and title required"}), 400
    room = _classroom_room_key(course)
    st = _classroom_get(room)
    with _classroom_lock:
        teacher = st["participants"].get(pid)
        if not teacher:
            return jsonify({"success": False, "error": "rejoin required"}), 404
        if teacher.get("role") != "teacher":
            return jsonify({"success": False, "error": "teacher permission required"}), 403
        assignment = {
            "id": "asg_" + uuid.uuid4().hex[:12],
            "course": course,
            "title": title[:180],
            "instructions": (body.get("instructions") or "").strip()[:2000],
            "due": (body.get("due") or "").strip()[:20],
            "teacher": teacher.get("name") or "Teacher",
            "ts": datetime.now().isoformat(timespec="seconds"),
            "status": "Pending",
        }
        st.setdefault("assignments", []).insert(0, assignment)
    broadcast("classroom_assignment", {"room": room, **assignment})
    return jsonify({"success": True, "assignment": assignment})


@app.get("/api/classroom/assignments")
def classroom_assignments_list():
    """Assignments given so far for a course — students' dashboards read this
    on load so assignments survive page reloads."""
    course = request.args.get("course", "")
    room = _classroom_room_key(course)
    st = _classroom_get(room)
    return jsonify({"success": True, "assignments": st.get("assignments") or []})


@app.post("/api/classroom/quiz")
def classroom_quiz_launch():
    """Teacher launches the quiz they set (their own questions, or a MiroFish
    AI draft they reviewed). The full question set travels on the
    classroom_quiz SSE event so every student's screen opens the SAME quiz at
    the same moment — class chat pauses while it runs. Deliberately NOT
    persisted: a live quiz is a live moment, not something to replay on reload."""
    body = request.get_json(silent=True) or {}
    course = (body.get("course") or "").strip()
    pid = (body.get("pid") or "").strip()
    title = (body.get("title") or "").strip()[:120] or "Live Quiz"
    raw_questions = body.get("questions")
    if not course or not pid or not isinstance(raw_questions, list) or not raw_questions:
        return jsonify({"success": False,
                        "error": "course, pid and at least one question required"}), 400
    room = _classroom_room_key(course)
    st = _classroom_get(room)
    with _classroom_lock:
        teacher = st["participants"].get(pid)
        if not teacher:
            return jsonify({"success": False, "error": "rejoin required"}), 404
        if teacher.get("role") != "teacher":
            return jsonify({"success": False, "error": "teacher permission required"}), 403
    questions = []
    for q in raw_questions[:30]:
        if not isinstance(q, dict) or not q.get("q"):
            continue
        opts = [str(o).strip()[:200] for o in (q.get("options") or []) if str(o).strip()]
        if len(opts) < 2:
            continue
        try:
            ans = int(q.get("answer", 0))
        except (TypeError, ValueError):
            ans = 0
        if ans < 0 or ans >= len(opts):
            ans = 0
        questions.append({"q": str(q["q"]).strip()[:400], "options": opts,
                          "answer": ans, "why": str(q.get("why") or "")[:300]})
    if not questions:
        return jsonify({"success": False, "error": "no valid questions"}), 400
    broadcast("classroom_quiz", {"room": room, "from": pid,
                                 "title": title, "questions": questions})
    return jsonify({"success": True, "count": len(questions)})


@app.post("/api/classroom/timetable")
def classroom_timetable_publish():
    """Teacher publishes the weekly class timetable (their own rows, or a
    MiroFish AI draft they reviewed). Persisted per course via boirsu so it
    survives reloads, and broadcast on classroom_timetable so every student
    dashboard picks it up instantly."""
    body = request.get_json(silent=True) or {}
    course = (body.get("course") or "").strip()
    pid = (body.get("pid") or "").strip()
    title = (body.get("title") or "").strip()[:120] or "Weekly class schedule"
    raw = body.get("sessions")
    if not course or not pid or not isinstance(raw, list) or not raw:
        return jsonify({"success": False,
                        "error": "course, pid and at least one session required"}), 400
    room = _classroom_room_key(course)
    st = _classroom_get(room)
    with _classroom_lock:
        teacher = st["participants"].get(pid)
        if not teacher:
            return jsonify({"success": False, "error": "rejoin required"}), 404
        if teacher.get("role") != "teacher":
            return jsonify({"success": False, "error": "teacher permission required"}), 403
    sessions = []
    for s in raw[:35]:
        if not isinstance(s, dict):
            continue
        day = str(s.get("day") or "").strip()[:16]
        when = str(s.get("time") or "").strip()[:8]
        subject = str(s.get("subject") or "").strip()[:120]
        if day and when and subject:
            sessions.append({"day": day, "time": when, "subject": subject})
    if not sessions:
        return jsonify({"success": False, "error": "no valid sessions"}), 400
    row = boirsu.save_class_timetable(course, title, sessions,
                                      teacher=str(teacher.get("name") or "Teacher"))
    if not row:
        return jsonify({"success": False, "error": "could not save the timetable"}), 500
    broadcast("classroom_timetable", {"room": room, **row})
    return jsonify({"success": True, "timetable": row})


@app.get("/api/classroom/timetable")
def classroom_timetable_get():
    """The teacher's published weekly timetable for a course, if any."""
    course = request.args.get("course", "")
    return jsonify({"success": True, "timetable": boirsu.load_class_timetable(course)})


# ==================================================================
# STUDENT RECORDS  --  attendance, grades, assignments
# ------------------------------------------------------------------
# boirsu.py already owns all of this; these endpoints only reshape it
# for the dashboard. No grading or attendance logic is duplicated here.
# ==================================================================

# The dashboard's CGPA dial is drawn as `student.cgpa / 4` and labelled
# "CGPA / 4.00", so a 4-point scale it is. boirsu stores letters and
# percentages only -- never a GPA -- so this mapping is ours. One place
# to change if the school moves to a 5-point scale.
CGPA_SCALE = 4.0
GRADE_POINTS = {"A": 4.0, "B": 3.0, "C": 2.0, "D": 1.0, "F": 0.0}


def _letter_for(percentage) -> str:
    """Same thresholds boirsu.record_quiz_score uses (boirsu.py:1456)."""
    try:
        pct = float(percentage or 0)
    except (TypeError, ValueError):
        pct = 0.0
    if pct >= 90:
        return "A"
    if pct >= 80:
        return "B"
    if pct >= 70:
        return "C"
    if pct >= 60:
        return "D"
    return "F"


def _short_code(name: str, index: int) -> str:
    words = [w for w in re.split(r"[^A-Za-z0-9]+", name or "") if w]
    # Initials for a multi-word topic ("Cell Biology Basics" -> CBB); for a
    # single word take its first three letters, so "Photosynthesis" reads
    # PHO 100 rather than a lone P 100 in the Grades table.
    letters = "".join(w[0] for w in words)[:3] if len(words) > 1 else (words[0][:3] if words else "")
    return f"{(letters or 'AI').upper()} {100 + index}"


_sponsor_org_cache = {}
_SPONSOR_ORG_TTL = 60.0  # seconds — lets a partner rename show up quickly


def _sponsor_org_for(sponsor_id):
    """org_name of the partner owning this sponsor ID (admin-registered).

    Students who register with a partner's sponsor ID get that partner's name
    as their portal brand; the default brand stays "devsphere academy".
    Cached in-process with a short TTL so reads stay cheap.
    """
    sid = (sponsor_id or "").strip().upper()
    if not sid:
        return None
    import time as _time
    cached = _sponsor_org_cache.get(sid)
    if cached and (_time.monotonic() - cached[0]) < _SPONSOR_ORG_TTL:
        return cached[1]
    org = None
    try:
        rows = (_pgdb.pg.table("partners")
                .select("org_name")
                .eq("sponsor_id", sid)
                .execute().data) or []
        if rows and rows[0].get("org_name"):
            org = str(rows[0]["org_name"]).strip() or None
    except Exception:
        org = None   # partners table unreachable -> keep the default brand
    _sponsor_org_cache[sid] = (_time.monotonic(), org)
    return org


def _student_payload(student: dict) -> dict:
    """
    Reshape a boirsu student record for studentdashboard.vue: real grades from
    quiz_records, real attendance from attendance_records.
    """
    if not student:
        return None

    quiz_records = student.get("quiz_records") or []

    # One table row per topic quizzed, averaged over attempts.
    by_topic = {}
    for record in quiz_records:
        topic = (record.get("topic") or "General").strip() or "General"
        bucket = by_topic.setdefault(topic, {"pcts": []})
        bucket["pcts"].append(float(record.get("percentage") or 0))

    rows, points = [], []
    for index, (topic, bucket) in enumerate(by_topic.items()):
        avg = round(sum(bucket["pcts"]) / len(bucket["pcts"]))
        letter = _letter_for(avg)
        points.append(GRADE_POINTS.get(letter, 0.0))
        # Same [code, name, units, score, grade] tuple the Grades table reads;
        # "units" carries the attempt count for real data.
        rows.append([_short_code(topic, index), topic, len(bucket["pcts"]), avg, letter])

    cgpa = round(sum(points) / len(points), 2) if points else 0.0
    attendance_rate = student.get("attendance_rate")
    if attendance_rate is None:
        total = student.get("total_classes") or 0
        attendance_rate = round((student.get("classes_attended", 0) / total) * 100) if total else 0

    sponsor_id = (student.get("sponsor_id") or "").strip().upper()
    sponsor_org = _sponsor_org_for(sponsor_id) if sponsor_id else None

    return {
        "student_id": student.get("student_id"),
        "name": student.get("name"),
        "email": student.get("email"),
        "sponsor_id": sponsor_id or None,
        # Partner branding: org_name of the partner whose sponsor ID the
        # student registered with (None -> the portal keeps "devsphere academy").
        "sponsor_org": sponsor_org,
        "phone": student.get("phone"),
        "career_path": student.get("career_path"),
        "course_name": student.get("course_name") or student.get("career_path"),
        "experience_level": student.get("experience_level"),
        "track": student.get("track") or student.get("class_type"),
        # Daily class hour the student picked at registration (WAT, "HH:MM")
        "preferred_time": student.get("preferred_time") or "18:00",
        # Per-day class times the student chose at registration
        # ( {"Monday":"18:00","Tuesday":"14:00","Wednesday":"","Saturday":"09:00",...} ).
        # Days left blank / "none" have no class.
        "preferred_daily_times": student.get("preferred_daily_times") or (student.get("preferred_time") or "18:00"),
        "class_type": student.get("class_type"),
        "current_month": student.get("current_month"),
        "intake_month": student.get("intake_month"),
        "payment_status": student.get("payment_status") or "pending",
        # Monthly school-fee access window (drives the dashboard lock).
        # get_access_state computes everything from the server record; we surface
        # the per-course monthly_fee both ways so every consumer reads the same
        # value (studentdashboard.vue reads `monthly_fee`, roadmap reads
        # `access_monthly_fee`).
        **{f"access_{k}": v for k, v in boirsu.get_access_state(student).items()
           if k != "currency"},
        "monthly_fee": boirsu.get_access_state(student).get("monthly_fee") or 50000,
        "location": student.get("location"),
        "country": student.get("country"),
        "gender": student.get("gender"),
        "dob": student.get("dob"),
        "occupation": student.get("occupation"),
        "qualification": student.get("qualification"),
        "field_study": student.get("field_study"),
        "institution": student.get("institution"),
        "goals": student.get("goals") or [],
        "overall_grade": student.get("overall_grade") or "N/A",
        "avg_quiz_score": student.get("avg_quiz_score") or 0,
        "cgpa": cgpa,
        "cgpa_scale": CGPA_SCALE,
        "attendance_rate": attendance_rate,
        "classes_attended": student.get("classes_attended") or 0,
        "classes_missed": student.get("classes_missed") or 0,
        "total_classes": student.get("total_classes") or 0,
        "assignments_submitted": student.get("assignments_submitted") or 0,
        "quizzes_taken": len(quiz_records),
        "quiz_records": quiz_records,
        "attendance_records": student.get("attendance_records") or [],
        "assignment_records": student.get("assignment_records") or [],
        "courses": rows,
    }


@app.get("/api/students")
def list_students():
    """Roster, so the dashboard can pick an identity without a login screen."""
    try:
        students = boirsu.load_students()
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)[:200]}), 503
    out = [{
        "student_id": sid,
        "name": s.get("name"),
        "career_path": s.get("career_path"),
        "overall_grade": s.get("overall_grade") or "N/A",
    } for sid, s in students.items()]
    out.sort(key=lambda s: s["student_id"])
    return jsonify({"success": True, "students": out})


@app.get("/api/student/<student_id>")
def get_student_record(student_id):
    try:
        student = boirsu.get_student(student_id)
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)[:200]}), 503
    if not student:
        return jsonify({"success": False, "error": "unknown student"}), 404
    # Keep the roadmap in sync even if attendance was marked outside this
    # server (CLI, teacher tool): recompute on every read, cheap and idempotent.
    _auto_advance_roadmap(student, student.get("career_path") or "frontend-developer")
    return jsonify({"success": True, "student": _student_payload(student)})


@app.post("/api/student/enroll")
def enroll():
    body = request.get_json(silent=True) or {}
    name = (body.get("name") or "").strip()
    if not name:
        return jsonify({"success": False, "error": "name required"}), 400
    try:
        extra_fields = {
            "location": (body.get("location") or "").strip(),
            "country": (body.get("country") or "").strip(),
            "gender": (body.get("gender") or "").strip(),
            "dob": (body.get("dob") or "").strip(),
            "occupation": (body.get("occupation") or "").strip(),
            "qualification": (body.get("qualification") or "").strip(),
            "field_study": (body.get("field_study") or body.get("fieldStudy") or "").strip(),
            "institution": (body.get("institution") or "").strip(),
            "research": (body.get("research") or "").strip(),
            "sponsor_id": (body.get("sponsor_id") or "").strip().upper(),
        }
        daily_times_raw = body.get("preferred_daily_times")
        if not isinstance(daily_times_raw, dict):
            daily_times_raw = (body.get("daily_times") or
                               (body.get("preferred_time") or "18:00"))
        daily_times = daily_times_raw

        preferred_daily_times = daily_times_raw if isinstance(daily_times_raw, dict) else None
        student = boirsu.enroll_student(
            name,
            (body.get("phone") or "").strip(),
            (body.get("email") or "").strip(),
            (body.get("career_path") or "frontend-developer").strip(),
            (body.get("experience_level") or "beginner").strip(),
            course_name=(body.get("course_name") or body.get("course") or body.get("career_path") or "frontend-developer").strip(),
            track=(body.get("track") or body.get("class_track") or "Weekday · evenings").strip(),
            preferred_time=(body.get("preferred_time") or "").strip(),
            preferred_daily_times=preferred_daily_times,
            goals=body.get("goals") or [],
            duration_months=body.get("duration_months"),
            class_minutes=int(body.get("class_minutes") or 60),
            extra_fields=extra_fields,
        )
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)[:200]}), 503
    broadcast("student_enrolled", {"student_id": student.get("student_id"),
                                   "name": student.get("name")})
    return jsonify({"success": True, "student": _student_payload(student)})


@app.post("/api/attendance")
def post_attendance():
    """
    Mark a class attended via boirsu.mark_attendance (boirsu.py:1396).

    That function appends unconditionally, so joining the same class twice
    would inflate total_classes and skew attendance_rate. De-duplicate here
    rather than editing it, so the CLI keeps behaving as it always has.
    """
    body = request.get_json(silent=True) or {}
    student_id = (body.get("student_id") or "").strip()
    if not student_id:
        return jsonify({"success": False, "error": "student_id required"}), 400
    try:
        class_number = int(body.get("class_number") or 1)
    except (TypeError, ValueError):
        return jsonify({"success": False, "error": "class_number must be a number"}), 400
    attended = body.get("attended", True)

    try:
        student = boirsu.get_student(student_id)
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)[:200]}), 503
    if not student:
        return jsonify({"success": False, "error": "unknown student"}), 404

    today = date.today().isoformat()
    already = any(
        int(r.get("class_number") or 0) == class_number
        and ((r.get("date") or (r.get("joined_at") or "")[:10]) == today)
        for r in (student.get("attendance_records") or [])
    )
    if already:
        return jsonify({"success": True, "duplicate": True,
                        "student": _student_payload(student)})

    try:
        updated = boirsu.mark_attendance(student_id, class_number, bool(attended))
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)[:200]}), 503
    if not updated or isinstance(updated, dict) and updated.get("ok") is False:
        reason = (updated or {}).get("error") if isinstance(updated, dict) else ""
        return jsonify({"success": False,
                        "error": reason or "could not record attendance"}), 500

    payload = _student_payload(updated)
    # Attendance-driven roadmap completion: each attended class turns the
    # next roadmap task green — no student clicking, real time via SSE.
    try:
        _auto_advance_roadmap(updated, student.get("career_path") or "frontend-developer")
    except Exception as exc:
        print(f"[WARN] _auto_advance_roadmap failed: {exc}")
    broadcast("attendance_marked", {"student_id": student_id,
                                     "class_number": class_number,
                                     "attendance_rate": payload.get("attendance_rate")})
    return jsonify({"success": True, "duplicate": False, "student": payload})


@app.post("/api/assignment")
def post_assignment():
    """Record a submission via boirsu.submit_assignment (boirsu.py:1473)."""
    body = request.get_json(silent=True) or {}
    student_id = (body.get("student_id") or "").strip()
    text = (body.get("submission") or "").strip()
    if not student_id or not text:
        return jsonify({"success": False,
                        "error": "student_id and submission required"}), 400
    try:
        number = int(body.get("assignment_number") or 1)
    except (TypeError, ValueError):
        number = 1
    try:
        student = boirsu.submit_assignment(student_id, number, text, body.get("score"))
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)[:200]}), 503
    if not student:
        return jsonify({"success": False, "error": "unknown student"}), 404
    broadcast("assignment_submitted", {"student_id": student_id,
                                        "assignment_number": number})
    return jsonify({"success": True, "student": _student_payload(student)})


# ---------------------------------------------------------------------------
# SCHOOL PORTAL API (PostgreSQL) — replaces direct Supabase browser access
# ---------------------------------------------------------------------------
# The school-portal pages (AdminPage.vue, PartnerPage.vue,
# TeacherClassroomGate.vue) and the registration page used to read/write the
# database straight from the browser through supabase-js. Browsers cannot
# connect to PostgreSQL directly, so those reads/writes now go through this
# whitelisted portal API, which talks to PostgreSQL via pgdb.
#
# Response shapes mirror the old supabase-js results so the page code keeps
# working: { "data": ... } on success, { "error": { "message", "code" } } on
# failure. Error codes are the real PostgreSQL ones (23505 duplicate key,
# 42P01 missing table, ...).
# ---------------------------------------------------------------------------

import pgdb as _pgdb  # noqa: E402

_PORTAL_TABLES = {
    "students", "teachers", "partners", "partner_fees", "course_fees",
    "student_courses", "quiz_records", "attendance_records",
    "assignment_records", "courses", "hub_spaces", "admins",
}

_table_columns_cache = {}


def _portal_table_columns(table):
    """Real column names of a table (information schema, cached)."""
    if table not in _table_columns_cache:
        cols = _pgdb._run(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = %s",
            (table,),
        )
        _table_columns_cache[table] = {c["column_name"] for c in (cols or [])}
    return _table_columns_cache[table]


def _portal_error_response(e):
    code = getattr(e, "code", "") or ""
    return jsonify({"data": None, "error": {"message": str(e), "code": code}})


@app.post("/api/portal/query")
def portal_query():
    """Whitelisted SELECT against PostgreSQL — mirrors the old supabase-js
    .from(table).select(cols).eq(...).order(...).limit(...) calls."""
    return _portal_query()


@app.post("/api/portal/count")
def portal_count():
    """Whitelisted exact COUNT — mirrors .select('*', {count:'exact', head:true})."""
    return _portal_count()


@app.post("/api/portal/insert")
def portal_insert():
    """Whitelisted INSERT — mirrors .from(table).insert(row). Unknown columns
    are filtered out (with the same tolerance the old save path had)."""
    return _portal_insert()


@app.post("/api/portal/update")
def portal_update():
    """Whitelisted UPDATE — mirrors .from(table).update(row).eq(key, value)."""
    body = request.get_json(silent=True) or {}
    table = (body.get("table") or "").strip()
    if table not in _PORTAL_TABLES:
        return jsonify({"data": None, "error": {"message": f"Table '{table}' is not whitelisted.", "code": "42501"}})
    try:
        row = body.get("row") or {}
        row = {k: v for k, v in row.items() if k in _portal_table_columns(table)}
        query = _pgdb.pg.table(table).update(row)
        for key, value in (body.get("eq") or {}).items():
            query.eq(key, value)
        result = query.execute()
        return jsonify({"data": result.data, "error": None})
    except _pgdb.PgError as e:
        return _portal_error_response(e)
    except Exception as e:
        return _portal_error_response(e)


@app.post("/api/portal/upsert")
def portal_upsert():
    """Whitelisted UPSERT — mirrors .from(table).upsert(row, {onConflict}).
    ON CONFLICT (cols) DO UPDATE SET the non-conflict columns."""
    body = request.get_json(silent=True) or {}
    table = (body.get("table") or "").strip()
    if table not in _PORTAL_TABLES:
        return jsonify({"data": None, "error": {"message": f"Table '{table}' is not whitelisted.", "code": "42501"}})
    try:
        rows = body.get("row")
        rows = rows if isinstance(rows, list) else [rows or {}]
        on_conflict = body.get("onConflict") or "id"
        filtered = []
        for row in rows:
            filtered.append({k: v for k, v in (row or {}).items() if k in _portal_table_columns(table)})
        result = _pgdb.pg.table(table).upsert(filtered, onConflict=on_conflict).execute()
        return jsonify({"data": result.data, "error": None})
    except _pgdb.PgError as e:
        return _portal_error_response(e)
    except Exception as e:
        return _portal_error_response(e)


@app.post("/api/portal/stats")
def portal_stats():
    """Aggregated dashboard analytics computed in SQL (no full-table scans).
    Returns { learning: {...}, registration: {...}, cohortCourses: [...] }."""
    return _portal_stats()


_LEARNING_SQL = """
SELECT
  (SELECT COUNT(*) FROM student_courses)                                        AS enrollments,
  (SELECT COALESCE(ROUND(AVG(progress)), 0) FROM student_courses)               AS avg_progress,
  (SELECT COUNT(*) FROM student_courses WHERE completed_at IS NOT NULL)         AS completed,
  (SELECT COUNT(*) FROM attendance_records)                                     AS attendance_total,
  (SELECT COUNT(*) FROM attendance_records WHERE attended)                      AS attendance_attended,
  (SELECT COUNT(*) FROM quiz_records)                                           AS quizzes,
  (SELECT COALESCE(ROUND(AVG(percentage)), 0) FROM quiz_records)                AS avg_quiz,
  (SELECT COUNT(*) FROM quiz_records WHERE percentage < 50)                     AS band0,
  (SELECT COUNT(*) FROM quiz_records WHERE percentage >= 50 AND percentage < 70) AS band1,
  (SELECT COUNT(*) FROM quiz_records WHERE percentage >= 70 AND percentage < 90) AS band2,
  (SELECT COUNT(*) FROM quiz_records WHERE percentage >= 90)                    AS band3,
  (SELECT COUNT(*) FROM assignment_records WHERE submitted_on IS NOT NULL)      AS submitted,
  (SELECT COUNT(*) FROM assignment_records
     WHERE graded_on IS NOT NULL OR score IS NOT NULL)                          AS graded
"""

_REGISTRATION_SQL = """
SELECT
  COUNT(*)                                                        AS total,
  COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '30 days') AS last30,
  COUNT(*) FILTER (WHERE lower(payment_status) = 'paid')          AS paid,
  COUNT(*) FILTER (WHERE lower(payment_status) <> 'paid')         AS unpaid,
  COUNT(DISTINCT country)                                         AS countries
FROM students
"""

_TALLY_SQL = {
    "courses":   ("COALESCE(NULLIF(course_name, ''), NULLIF(career_path, ''))", "courses"),
    "locations": ("COALESCE(NULLIF(location, ''), NULLIF(country, ''))", "locations"),
    "gender":    ("NULLIF(gender, '')", "gender"),
    "tracks":    ("NULLIF(track, '')", "tracks"),
}

_COHORTS_SQL = """
SELECT DISTINCT k FROM (
  SELECT NULLIF(TRIM(course_name), '')   AS k FROM students
  UNION
  SELECT NULLIF(TRIM(career_path), '')   AS k FROM students
) t WHERE k IS NOT NULL ORDER BY k LIMIT 12
"""


def _portal_stats():
    """Aggregated analytics for the admin dashboard — every count/average is
    computed INSIDE PostgreSQL (GROUP BY / COUNT / AVG over indexed columns),
    so the dashboard no longer downloads whole tables to count in JavaScript.
    One call replaces the four full-table scans loadLearning used to do, and
    stays cheap no matter how many thousands of records exist."""
    try:
        _pgdb.initialise()
        learning = _pgdb._run(_LEARNING_SQL, fetch="one") or {}
        registration = _pgdb._run(_REGISTRATION_SQL, fetch="one") or {}
        for key, (expr, out) in _TALLY_SQL.items():
            rows = _pgdb._run(
                f"SELECT {expr} AS k, COUNT(*)::int AS n FROM students "
                f"WHERE {expr} IS NOT NULL GROUP BY 1 ORDER BY n DESC, k LIMIT 5"
            )
            registration[out] = [[r["k"], r["n"]] for r in (rows or [])]
        cohorts = _pgdb._run(_COHORTS_SQL, fetch="all")
        registration["cohortCourses"] = [r["k"] for r in (cohorts or [])]
        # band0..band3 stay in the payload — the dashboard builds its labelled
        # quizBands array client-side from these counts.
        attendance_total = learning.get("attendance_total") or 0
        attended = learning.get("attendance_attended") or 0
        learning["attendanceRate"] = round(attended * 100 / attendance_total) if attendance_total else 0
        learning.pop("attendance_total", None)
        learning.pop("attendance_attended", None)
        # Envelope required by the portal contract (see the header comment
        # above) and by pgdb.js's pgStats(). Returning learning/registration
        # at the top level made the browser's pgPost() read `data` as null, so
        # every admin stat card silently showed 0 even though the rows were in
        # PostgreSQL — a student could register and never appear.
        return jsonify({"data": {"learning": learning, "registration": registration}, "error": None})
    except _pgdb.PgError as e:
        return _portal_error_response(e)
    except Exception as e:
        return _portal_error_response(e)


_TABLE_NAME_RE = __import__("re").compile(r"^[a-z_][a-z0-9_]*$")
_FIELD_RE = __import__("re").compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_SELECT_RE = __import__("re").compile(r"^[A-Za-z0-9_,\s*]+$")


def _apply_query_params(query, body, table):
    for key, value in (body.get("eq") or {}).items():
        if not _FIELD_RE.match(str(key)):
            raise _pgdb.PgError(f"Invalid filter column: {key!r}")
        query.eq(key, value)
    for key, values in (body.get("in") or {}).items():
        if not _FIELD_RE.match(str(key)):
            raise _pgdb.PgError(f"Invalid filter column: {key!r}")
        if not isinstance(values, list) or len(values) > 5000:
            raise _pgdb.PgError("Invalid 'in' filter: pass a list of at most 5000 values")
        query.in_(key, values)
    order = body.get("order")
    if order:
        if not _FIELD_RE.match(str(order)):
            raise _pgdb.PgError(f"Invalid order column: {order!r}")
        query.order(order, ascending=body.get("ascending", True))
    # Row caps: every list read is bounded so one page can never drag the
    # whole table across the network. Analytics counts/averages should use
    # /api/portal/stats (computed in SQL) instead of full scans.
    limit = body.get("limit")
    limit = 5000 if limit is None else min(int(limit), 50000)
    query.limit(limit)
    if body.get("single"):
        query.maybeSingle()
    return query


def _portal_query():
    body = request.get_json(silent=True) or {}
    table = (body.get("table") or "").strip()
    if table not in _PORTAL_TABLES:
        return jsonify({"data": None, "error": {"message": f"Table '{table}' is not whitelisted.", "code": "42501"}})
    try:
        select = body.get("select") or "*"
        if not _SELECT_RE.match(str(select)):
            raise _pgdb.PgError(f"Invalid select column list: {select!r}")
        query = _pgdb.pg.table(table).select(select)
        _apply_query_params(query, body, table)
        result = query.execute()
        return jsonify({"data": result.data, "count": result.count, "error": None})
    except _pgdb.PgError as e:
        return _portal_error_response(e)
    except Exception as e:
        return _portal_error_response(e)


def _portal_count():
    body = request.get_json(silent=True) or {}
    table = (body.get("table") or "").strip()
    if table not in _PORTAL_TABLES:
        return jsonify({"count": None, "error": {"message": f"Table '{table}' is not whitelisted.", "code": "42501"}})
    try:
        query = _pgdb.pg.table(table).select("*", count="exact")
        for key, value in (body.get("eq") or {}).items():
            query.eq(key, value)
        result = query.execute()
        return jsonify({"count": result.count, "error": None})
    except _pgdb.PgError as e:
        return _portal_error_response(e)
    except Exception as e:
        return _portal_error_response(e)


def _portal_insert():
    body = request.get_json(silent=True) or {}
    table = (body.get("table") or "").strip()
    if table not in _PORTAL_TABLES:
        return jsonify({"data": None, "error": {"message": f"Table '{table}' is not whitelisted.", "code": "42501"}})
    try:
        row = body.get("row") or {}
        row = {k: v for k, v in row.items() if k in _portal_table_columns(table)}
        result = _pgdb.pg.table(table).insert(row).execute()
        return jsonify({"data": result.data, "error": None})
    except _pgdb.PgError as e:
        return _portal_error_response(e)
    except Exception as e:
        return _portal_error_response(e)


if __name__ == "__main__":
    print("BOI RSU Realtime API starting on http://localhost:5055")
    print("  Endpoints:")
    print("   - GET  /api/stream              (SSE live updates)")
    print("   - GET  /api/careers             (list all career paths)")
    print("   - GET  /api/roadmap/<career>    (month-by-month topics)")
    print("   - GET  /api/progress/<career>   (saved completion state)")
    print("   - POST /api/progress/<career>   (mark task done/undone)")
    print("   - POST /api/start-ai-class      (launch AI learning system)")
    print("   -")
    print("   - GET  /api/ai/status           (bridge + API key diagnostics)")
    print("   - POST /api/ai/course           (generate a course -> job_id)")
    print("   - GET  /api/ai/job/<job_id>     (generation progress)")
    print("   - GET  /api/ai/courses          (library rows)")
    print("   - GET  /api/ai/course/<id>      (full course + sections)")
    print("   - GET  /api/ai/course/<id>/section/<n>/quiz     (no answers)")
    print("   - POST /api/ai/quiz/<qid>/submit               (grade -> student)")
    print("   - GET  /api/ai/course/<id>/section/<n>/summary")
    print("   - GET  /api/ai/course/<id>/section/<n>/resources")
    print("   - GET  /api/ai/course/<id>/section/<n>/videos")
    print("   - GET  /api/ai/speak            (Deepgram MP3 for the browser)")
    print("   - POST /api/ai/ask              (tutor Q&A)")
    print("   - GET  /api/students            (roster)")
    print("   - GET  /api/student/<id>        (dashboard payload)")
    print("   - POST /api/student/enroll      (create a student)")
    print("   - POST /api/attendance          (mark a class attended)")
    print("   - POST /api/assignment          (submit an assignment)")
    print("   - POST /api/classroom/textbook  (teacher uploads a PDF textbook)")
    print("   - GET  /api/textbooks/pdf/<id>   (download a teacher PDF)")
    print("   - POST /api/classroom/assignment (teacher gives an assignment)")
    print("   - GET  /api/classroom/assignments (list assignments for a course)")
    print("   - POST /api/classroom/live      (teacher go-live / end-live for the room)")
    print("   - GET  /health")
    app.run(host="0.0.0.0", port=5055, threaded=True, debug=False)




