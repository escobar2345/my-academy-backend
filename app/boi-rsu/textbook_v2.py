# -*- coding: utf-8 -*-
"""textbook_v2.py - dense, timetable-driven monthly textbooks.

Replaces the legacy generator (thin filler chapters, one shared quiz bank and a
page break per topic, which produced three near-identical books full of white
space). This engine:

  * mirrors the TIMETABLE - four week chapters using the same chunking rule as
    the timetable (per_week = len(tasks) // 4 + 1, with week 4 cycling), listing
    the student's REAL class days and the topics taught that week;
  * writes real content from topic_library (detailed lessons, key terms,
    common mistakes, practice work) and falls back to month-varied, task-driven
    content for courses without a knowledge-base entry;
  * keeps the questions unique per month (topic-disjoint knowledge-base sets);
  * packs the page - no page break per topic, tight leading, and only the cover
    and the end-of-month exam start a new page.
"""

from datetime import datetime

try:
    from fpdf import FPDF
except Exception:          # pragma: no cover - the caller falls back to .txt
    FPDF = None

import topic_library as _tl

_WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday",
             "Friday", "Saturday", "Sunday"]

_RULE = (225, 232, 240)
_INK = (24, 32, 44)
_ACCENT = (16, 122, 108)


def make_pdf():
    """A4 pdf with the latin-1 shim every cell/multi_cell passes through.

    Core (Helvetica) fonts cannot encode em dashes or curly quotes, which used
    to kill generation mid-book with FPDFUnicodeEncodingException.
    """
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=14)
    pdf.set_margins(16, 14, 16)

    def _safe(s):
        return (s.encode("latin-1", "replace").decode("latin-1")
                if isinstance(s, str) else s)

    # fpdf2's multi_cell defaults to new_x=RIGHT, which leaves the cursor at the
    # right margin so the NEXT multi_cell/cell has no width to work with
    # ("Not enough horizontal space to render a single character"). Force the
    # left margin + next line, which is what every dense layout here expects.
    try:
        from fpdf.enums import XPos, YPos
    except Exception:                      # pragma: no cover
        XPos, YPos = None, None

    raw_cell, raw_multi = pdf.cell, pdf.multi_cell

    def safe_cell(*a, **k):
        a = tuple(_safe(x) for x in a)
        k = {kk: _safe(vv) for kk, vv in k.items()}
        return raw_cell(*a, **k)

    def safe_multi(*a, **k):
        a = tuple(_safe(x) for x in a)
        k = {kk: _safe(vv) for kk, vv in k.items()}
        if XPos is not None:
            k.setdefault("new_x", XPos.LMARGIN)
            k.setdefault("new_y", YPos.NEXT)
        return raw_multi(*a, **k)

    pdf.cell, pdf.multi_cell = safe_cell, safe_multi
    return pdf


def cover(pdf, course_title, month_no, month_title, class_days, brand):
    """Compact cover: a band, the facts, and the class days - no empty page."""
    pdf.add_page()
    pdf.set_fill_color(12, 34, 56)
    pdf.rect(0, 0, 210, 62, "F")
    pdf.set_text_color(255, 255, 255)
    pdf.set_xy(16, 14)
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(0, 5, brand.upper(), ln=True)
    pdf.set_font("Helvetica", "B", 20)
    pdf.multi_cell(0, 9, course_title, align="L")
    pdf.set_text_color(*_INK)
    pdf.ln(6)
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 7, "Month %d - %s" % (int(month_no), month_title), ln=True)
    pdf.ln(1)
    pdf.set_draw_color(*_RULE)
    pdf.line(16, pdf.get_y(), 194, pdf.get_y())
    pdf.ln(3)
    pdf.set_font("Helvetica", "", 9)
    days = ", ".join(class_days) if class_days else "daily"
    pdf.multi_cell(0, 5, "Class days: " + days)
    pdf.multi_cell(0, 5, "Generated: " + datetime.now().strftime("%d %b %Y")
                   + "  |  Four-week teaching plan with lessons, key terms, "
                     "practice work and a month-end exam.")
    pdf.ln(4)


def space_needed(pdf, mm):
    """Page-break guard that only breaks when the room is genuinely gone, so no
    section is orphaned but pages stay full."""
    if pdf.get_y() + mm > 283:
        pdf.add_page()


def week_bar(pdf, week_no, class_days, topics):
    """Thin filled band introducing a week - the timetable's four weeks."""
    space_needed(pdf, 16)
    y = pdf.get_y()
    pdf.set_fill_color(240, 246, 250)
    pdf.rect(16, y, 178, 7, "F")
    pdf.set_xy(18, y + 1)
    pdf.set_text_color(*_ACCENT)
    pdf.set_font("Helvetica", "B", 11.5)
    label = "WEEK %d" % week_no
    if class_days:
        label += "  -  " + ", ".join(class_days)
    pdf.cell(0, 5, label, ln=True)
    pdf.set_text_color(*_INK)
    pdf.ln(1)
    if topics:
        pdf.set_font("Helvetica", "I", 8.5)
        pdf.multi_cell(0, 4.2, "This week covers: " + " | ".join(topics))
        pdf.ln(1)


def topic_block(pdf, topic, body, week_tasks):
    """One topic: lessons, key terms, mistakes and practice - continuous flow."""
    space_needed(pdf, 22)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(*_ACCENT)
    pdf.multi_cell(0, 5.4, topic)
    pdf.set_text_color(*_INK)
    if body.get("summary"):
        pdf.set_font("Helvetica", "I", 8.6)
        pdf.multi_cell(0, 4.3, body["summary"])
    pdf.ln(0.8)

    # Class-day tasks from the timetable for this topic (if any are known).
    if week_tasks:
        pdf.set_font("Helvetica", "B", 8.8)
        pdf.cell(0, 4.6, "Scheduled in class", ln=True)
        pdf.set_font("Helvetica", "", 8.8)
        for t in week_tasks[:4]:
            pdf.cell(4)
            pdf.multi_cell(0, 4.3, "- " + t)
        pdf.ln(0.8)

    pdf.set_font("Helvetica", "B", 9.2)
    pdf.cell(0, 4.8, "Lesson notes", ln=True)
    pdf.set_font("Helvetica", "", 8.8)
    for i, item in enumerate(body.get("lessons", []), 1):
        title, text = item if isinstance(item, (tuple, list)) else (str(item), "")
        space_needed(pdf, 14)
        pdf.set_font("Helvetica", "B", 8.8)
        pdf.multi_cell(0, 4.4, "%d.%d %s" % (_WEEK_SEQ[0], i, title))
        pdf.set_font("Helvetica", "", 8.8)
        pdf.multi_cell(0, 4.3, text)
        pdf.ln(0.6)

    terms = body.get("terms") or []
    if terms:
        space_needed(pdf, 12)
        pdf.set_font("Helvetica", "B", 9.2)
        pdf.cell(0, 4.8, "Key terms", ln=True)
        for item in terms:
            space_needed(pdf, 8)
            if isinstance(item, (tuple, list)) and len(item) >= 2:
                pdf.set_font("Helvetica", "B", 8.6)
                pdf.cell(44, 4.2, str(item[0]))
                pdf.set_font("Helvetica", "", 8.6)
                pdf.multi_cell(0, 4.2, str(item[1]))
            else:                      # plain-string entry
                pdf.set_font("Helvetica", "", 8.6)
                pdf.multi_cell(0, 4.2, "- " + str(item))
        pdf.ln(0.6)

    mistakes = body.get("mistakes") or []
    if mistakes:
        space_needed(pdf, 12)
        pdf.set_font("Helvetica", "B", 9.2)
        pdf.cell(0, 4.8, "Common mistakes", ln=True)
        pdf.set_font("Helvetica", "", 8.6)
        for item in mistakes:
            space_needed(pdf, 8)
            if isinstance(item, (tuple, list)) and len(item) >= 2:
                pdf.multi_cell(0, 4.2, "- %s: %s" % (item[0], item[1]))
            else:                      # plain-string entry
                pdf.multi_cell(0, 4.2, "- " + str(item))
        pdf.ln(0.6)

    practice = body.get("practice") or []
    if practice:
        space_needed(pdf, 12)
        pdf.set_font("Helvetica", "B", 9.2)
        pdf.cell(0, 4.8, "Practice this week", ln=True)
        pdf.set_font("Helvetica", "", 8.6)
        for i, item in enumerate(practice, 1):
            space_needed(pdf, 8)
            pdf.multi_cell(0, 4.2, "%d. %s" % (i, item))
    pdf.ln(1.4)


_WEEK_SEQ = [0]


def contents(pdf, weeks, class_days):
    """One compact contents block - the four weeks and what each one covers."""
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 6, "Contents", ln=True)
    pdf.set_font("Helvetica", "", 9)
    for idx, (topics, days) in enumerate(weeks, 1):
        pdf.set_font("Helvetica", "B", 9)
        line = "Week %d" % idx
        if days:
            line += "  (%s)" % ", ".join(days)
        pdf.cell(0, 5, line, ln=True)
        pdf.set_font("Helvetica", "", 9)
        for topic in topics:
            pdf.cell(6)
            pdf.multi_cell(0, 4.6, "- " + topic)
    pdf.ln(3)


def exam(pdf, month_no, topics, project, brand, used=None):
    """Month-end exam: every topic's own questions, deduped against the earlier
    months of the same course (passed in `used`), then the answer key."""
    used = used if used is not None else set()
    bank = []
    for topic in topics:
        got = 0
        for q in _tl.quiz_for(topic, month_no):
            stem = str(q.get("q", "")).strip().lower()
            if not stem or stem in used:
                continue
            used.add(stem)
            bank.append((topic, q))
            got += 1
        # Every topic contributes at least three questions, topped up with
        # topic-and-month specific ones so nothing repeats later.
        for q in _tl.filler_questions(topic, month_no, 5):
            if got >= 3:
                break
            stem = str(q.get("q", "")).strip().lower()
            if not stem or stem in used:
                continue
            used.add(stem)
            bank.append((topic, q))
            got += 1
    if not bank:
        return 0
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(*_ACCENT)
    pdf.cell(0, 6, "Month %d examination" % month_no, ln=True)
    pdf.set_text_color(*_INK)
    pdf.set_font("Helvetica", "I", 8.4)
    pdf.multi_cell(0, 4.2, "Answer all questions. Each topic contributes its own "
                           "questions, so every month is assessed on its own material.")
    pdf.ln(1.5)
    keys = []
    for i, (topic, q) in enumerate(bank, 1):
        space_needed(pdf, 20)
        pdf.set_font("Helvetica", "B", 8.8)
        pdf.multi_cell(0, 4.4, "%d. %s" % (i, q.get("q", "")))
        pdf.set_font("Helvetica", "", 8.6)
        for j, opt in enumerate(q.get("options", []), 0):
            pdf.cell(5)
            pdf.multi_cell(0, 4.1, "%s. %s" % ("ABCD"[j], opt))
        keys.append("%d-%s" % (i, "ABCD"[int(q.get("answer", 0))]))
        pdf.ln(1.2)
    if project:
        space_needed(pdf, 20)
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(0, 5.4, "Month project", ln=True)
        pdf.set_font("Helvetica", "", 8.8)
        pdf.multi_cell(0, 4.3, project)
    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(0, 4.8, "Answer key", ln=True)
    pdf.set_font("Helvetica", "", 8.6)
    pdf.multi_cell(0, 4.2, "   ".join(keys))
    return len(bank)


def build_topic(career_path, month_number, topic, out_path, class_days=None,
                tasks=None, week_no=None, month_title="", course_title="",
                brand="devsphere academy", used=None):
    """Write ONE topic's PDF - the reading material for a single class topic as
    it appears on the student's timetable (with its week and class days).

    Returns (path, pages, questions) or None.
    """
    if FPDF is None:
        return None
    topic = (topic or "").strip()
    if not topic:
        return None
    tasks = [t for t in (tasks or []) if t]
    class_days = [d for d in (class_days or []) if d]
    used = used if used is not None else set()

    pdf = make_pdf()
    cover(pdf, topic, month_number,
          (month_title or "") + ("  -  Week %d" % week_no if week_no else ""),
          class_days, brand)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 5.4, "Timetable slot", ln=True)
    pdf.set_font("Helvetica", "", 8.8)
    pdf.multi_cell(0, 4.3, "Week %s  |  Classes on %s  |  Course: %s"
                   % (week_no or "-", ", ".join(class_days) or "daily",
                      course_title or career_path.replace("-", " ").title()))
    if tasks:
        for t in tasks[:4]:
            pdf.cell(4)
            pdf.multi_cell(0, 4.3, "- " + t)
    pdf.ln(1)

    body = _tl.lookup(topic) or _tl.generic_chapters(
        topic, career_path, month_number, tasks)
    _WEEK_SEQ[0] = week_no or 1
    topic_block(pdf, topic, body, tasks if False else [])

    # This topic's own questions, deduped against its neighbours in the month.
    bank = []
    for q in _tl.quiz_for(topic, month_number):
        stem = str(q.get("q", "")).strip().lower()
        if not stem or stem in used:
            continue
        used.add(stem)
        bank.append((topic, q))
        if len(bank) >= 5:
            break
    if not bank:
        for q in _tl.filler_questions(topic, month_number, 5):
            bank.append((topic, q))
    if bank:
        space_needed(pdf, 30)
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_text_color(*_ACCENT)
        pdf.cell(0, 6, "Topic check - %s" % topic, ln=True)
        pdf.set_text_color(*_INK)
        pdf.set_font("Helvetica", "I", 8.4)
        pdf.multi_cell(0, 4.2, "Answer all questions, then mark yourself with the "
                               "key at the bottom before your next class.")
        pdf.ln(1.5)
        keys = []
        for i, (_, q) in enumerate(bank, 1):
            space_needed(pdf, 18)
            pdf.set_font("Helvetica", "B", 8.8)
            pdf.multi_cell(0, 4.4, "%d. %s" % (i, q.get("q", "")))
            pdf.set_font("Helvetica", "", 8.6)
            for j, opt in enumerate(q.get("options", []), 0):
                pdf.cell(5)
                pdf.multi_cell(0, 4.1, "%s. %s" % ("ABCD"[j], opt))
            keys.append("%d-%s" % (i, "ABCD"[int(q.get("answer", 0))]))
            pdf.ln(1.2)
        pdf.ln(1)
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(0, 4.8, "Answer key", ln=True)
        pdf.set_font("Helvetica", "", 8.6)
        pdf.multi_cell(0, 4.2, "   ".join(keys))

    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        pdf.output(str(out_path))
    except Exception as exc:            # pragma: no cover
        print("[WARN] topic book write failed:", exc)
        return None
    return (out_path, 0, len(bank))


def build(career_path, month_number, out_path, class_days=None, tasks=None,
          course_title="", month_title="", topics=None, project="",
          brand="devsphere academy", prior_topics=None):
    """Write one month's textbook PDF. Returns (path, pages, questions) or None."""
    if FPDF is None:
        return None
    topics = [t for t in (topics or []) if t]
    if not topics:
        return None
    tasks = [t for t in (tasks or []) if t]
    class_days = [d for d in (class_days or []) if d]

    # Questions already used by the EARLIER months of this course, so the three
    # books never repeat each other's questions.
    used = set()
    for m_idx, prior in enumerate(prior_topics or [], 1):
        for topic in prior or []:
            for q in _tl.quiz_for(topic, m_idx):
                stem = str(q.get("q", "")).strip().lower()
                if stem:
                    used.add(stem)

    pdf = make_pdf()
    cover(pdf, course_title or career_path.replace("-", " ").title(),
          month_number, month_title or "Coursework", class_days, brand)

    # Split the month's topics into the SAME four weeks the timetable uses.
    topic_chunks = _tl.week_split(len(topics), 4)
    task_chunks = _tl.week_split(len(tasks), 4) if tasks else [[]] * 4

    weeks = []
    for chunk in topic_chunks:
        weeks.append([topics[i] for i in chunk])
    contents(pdf, list(zip(weeks, [class_days] * 4)), class_days)

    for w, names in enumerate(weeks, 1):
        _WEEK_SEQ[0] = w
        week_task_names = [tasks[i] for i in task_chunks[w - 1]]
        week_bar(pdf, w, class_days, names)
        for n, topic in enumerate(names):
            # Give each topic its share of the week's timetable tasks.
            mine = [t for i, t in enumerate(week_task_names) if i % len(names) == n] \
                if names else week_task_names
            body = _tl.lookup(topic) or _tl.generic_chapters(
                topic, career_path, month_number, mine or week_task_names)
            topic_block(pdf, topic, body, mine)

    questions = exam(pdf, month_number, topics, project, brand, used=used)
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        pdf.output(str(out_path))
    except Exception as exc:            # pragma: no cover
        print("[WARN] textbook_v2 write failed:", exc)
        return None
    return (out_path, getattr(pdf, "pages_count", 0) or 0, questions)