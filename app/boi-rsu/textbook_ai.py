# -*- coding: utf-8 -*-
"""textbook_ai.py - AI-WRITTEN monthly textbooks, laid out to spec.

WHY THIS EXISTS
---------------
`boirsu.generate_textbook_pdf_legacy()` prints fixed f-strings onto pages. That
is why every chapter of a legacy book reads the same, why the quizzes repeat,
and why a Graphic Design book ends up telling students to "write clean,
well-organised code". There is no model in that path at all, so no prompt could
ever improve it.

This module is the missing engine: it asks the tutor model chain to actually
WRITE the month, using AI_BOOK_PROMPT below, then renders the result to A4
honouring the document-designer layout rules:

  * A4, 25 mm (2.5 cm) margins on every side
  * body 11.5 pt at 1.4 line spacing; headings 24 / 16 / 13 pt
  * cover page (title, subtitle, author-or-date, nothing else)
  * table of contents carrying the REAL page numbers
  * every chapter starts on a new page
  * code in a shaded Courier box, wrapped so it never crosses the margin
  * bullets + numbered lists instead of slabs of text
  * a heading is never left alone at the foot of a page
  * page numbers in the footer, chapter name in the header (never on the cover)

`boirsu.generate_textbook_pdf_legacy()` calls build_ai_textbook() FIRST and
keeps its own template path as the fallback, so book generation never dies when
the model is unreachable. Turn the AI path off with BOIRSU_AI_TEXTBOOK=0.
"""

import os
import re
import json

try:
    from fpdf import FPDF
except Exception:                      # pragma: no cover - text fallback then
    FPDF = None

# A4 in millimetres.
PAGE_W, PAGE_H = 210.0, 297.0
MARGIN = 25.0                          # 2.5 cm, as the layout rules demand
USABLE_W = PAGE_W - (MARGIN * 2)

BODY_PT = 11.5                         # 11-12 pt body text
BODY_LEAD = 5.9                        # 11.5 pt * 1.4 line spacing ~= 5.7 mm
H1_PT, H2_PT, H3_PT = 24, 16, 13       # chapter / section / sub-heading
CODE_PT, CODE_LEAD = 9.0, 4.6

INK = (24, 32, 44)                     # one main colour + grey, throughout
ACCENT = (16, 122, 108)
GREY = (110, 116, 124)
RULE = (206, 212, 218)
CODE_BG = (244, 246, 248)
BOX_BG = (250, 248, 240)

CONTENT_MAX_TOKENS = int(os.environ.get("BOIRSU_AI_TEXTBOOK_TOKENS", "4000"))
CHAPTER_TARGET = max(6, int(os.environ.get("BOIRSU_AI_CHAPTERS", "6")))
# ---------------------------------------------------------------------------
# THE AUTHOR PROMPT. This is the document-designer brief; the __TOKENS__ are
# filled in per book by _fill_prompt(). The layout clauses are enforced by the
# renderer below, not by the model (a model cannot set margins or page breaks).
# ---------------------------------------------------------------------------
AI_BOOK_PROMPT = '''You are an expert technical writer and PDF document designer. Write and produce a complete, professional document on the topic below.

TOPIC: __TOPIC__
AUDIENCE: __AUDIENCE__
COURSE: __COURSE__  (Month __MONTH__: __MONTH_TITLE__)
TONE: Clear, friendly, and practical, in the style of W3Schools (short chapters, many small examples) and freeCodeCamp handbooks (explained step by step).

LENGTH REQUIREMENTS (very important)
- The document must contain AT LEAST 3,000 words of real content. Do not count headings, the table of contents, or code as part of the 3,000.
- Do not summarize or rush. Explain every idea in depth with reasons, not just definitions.
- Write section by section. Each main chapter must be at least 350 words.
- Before finishing, count your words. If you are under 3,000, keep adding useful explanations, examples and exercises until you pass it.

REQUIRED STRUCTURE
1. Cover page: title, subtitle, and author or date. Nothing else on this page.
2. Table of contents with chapter names and page numbers, on its own page.
3. Introduction: what the topic is, why it matters, what the reader will learn.
4. At least 6 main chapters, ordered from basic to advanced. Each chapter must have:
   - A short overview at the start
   - Detailed explanations in short paragraphs (3 to 5 sentences each)
   - At least 2 practical examples or code samples with a line-by-line explanation
   - A "Common Mistakes" box
   - A "Key Points" summary at the end
5. A practice section with at least 10 exercises, followed by an answers section.
6. Conclusion and suggested next steps.
7. A short glossary of important terms.

LAYOUT AND FORMATTING RULES (nothing may overlap or be cramped)
- Page size A4 with margins of at least 2.5 cm on every side.
- Body text 11 to 12 pt in a readable font, with line spacing of at least 1.4.
- Headings clearly larger than body text: Chapter title 24 pt, Section heading 16 pt, Sub-heading 13 pt.
- Leave clear space before and after every heading, paragraph, list, table, image and code block. Never place elements directly on top of or touching each other.
- Start every chapter on a new page.
- Put code in a separate shaded box with a monospace font. Wrap long lines or shrink them so they never run past the box or the page edge.
- Keep tables inside the margins with padding in every cell.
- Do not let a heading sit alone at the bottom of a page. Move it to the next page with its content.
- Use a consistent color scheme (one main color plus grey) throughout.
- Add page numbers in the footer and the chapter title in the header on every page except the cover.
- Use real bullet lists and numbered lists, not long blocks of text.

QUALITY CHECK BEFORE OUTPUT
Confirm each of the following, and fix anything that fails:
1. The document has more than 3,000 words.
2. Every section in the required structure is present.
3. No text, code, or table overlaps, is cut off, or crosses a margin.
4. The table of contents matches the real page numbers.
5. There are no repeated paragraphs and no filler text.

Now write and produce the full document. Do not ask questions, and do not give a summary or outline. Output the finished document.

---
GROUND THE BOOK IN THIS REAL TIMETABLE (the cohort is actually being taught
these topics this month - name them, use them, and keep the order):
__TIMETABLE__
Month project the chapters must build towards: __PROJECT__

RETURN FORMAT: you cannot return a PDF file, so the renderer turns your writing
into A4 pages instead. Reply with RAW JSON ONLY - no markdown, no fences, no
commentary - in exactly the shape asked for in each step below. The renderer
applies every layout rule above (margins, font sizes, spacing, page numbers,
chapter-per-page, shaded code boxes, header and footer), so spend ALL of your
effort on the writing itself.
'''
# Appended per step, so the author prompt above stays exactly as written.
PLAN_CONTRACT = '''
STEP 1 - THE BOOK PLAN. Return JSON:
{
  "title": "Textbook: <book title>",
  "subtitle": "<one line saying who the book is for>",
  "audience": "<e.g. complete beginners with no experience>",
  "introduction": "<what the topic is, why it matters, what the reader will learn - at least 180 words>",
  "chapters": [
    {"chapter": "<chapter title>", "overview": "<what this chapter covers, 2-3 sentences>"}
  ],
  "glossary": [{"term": "<term>", "definition": "<short definition>"}]
}
Give at least __CHAPTERS__ chapters in order from basic to advanced, mapping onto
the timetable topics above. At least 8 glossary terms.
'''

CHAPTER_CONTRACT = '''
STEP 2 - ONE CHAPTER, WRITTEN IN FULL. Return JSON:
{
  "chapter": "<the chapter title>",
  "overview": "<short chapter overview>",
  "sections": [
    {
      "heading": "<section sub-heading>",
      "body": "<the teaching text. Several short paragraphs of 3 to 5 sentences each, separated by a blank line. Explain the idea in depth with reasons, not just definitions.>",
      "examples": [
        {"lang": "<python|javascript|html|css|code|worked-example>",
         "code": "<the example. For non-code subjects put the worked steps or the composed text here>",
         "explanation": "<line-by-line explanation of what each part does and why>"}
      ],
      "common_mistakes": ["<mistake 1>", "<mistake 2>", "<mistake 3>"],
      "key_points": ["<point 1>", "<point 2>", "<point 3>"],
      "table": {"headers": ["<h1>", "<h2>"], "rows": [["<cell>", "<cell>"]]}
    }
  ]
}
Rules: at least 4 sections; EVERY section needs the full "body" write-up and at
least 2 examples each with its own line-by-line explanation; every section needs
common_mistakes, key_points and a table. This chapter alone must exceed 350
words of real explanation. No repetition, no filler.
'''

TAIL_CONTRACT = '''
STEP 3 - PRACTICE, ANSWERS, CONCLUSION, NEXT STEPS. Return JSON:
{
  "practice": [{"number": 1, "prompt": "<hands-on exercise>"}],
  "answers": [{"number": 1, "answer": "<worked answer>"}],
  "conclusion": "<wrap-up of the whole book, at least 120 words>",
  "next_steps": ["<what to study or build next>"]
}
At least 10 exercises, each with a matching numbered answer. Nothing may repeat
the end-of-chapter material.
'''

# Used only when the model returns fewer chapters than the brief demands, so the
# book always reaches the 6-chapter / 3,000-word shape the prompt asks for.
CHAPTER_ORDER = ["Essentials", "Going Deeper", "Applied Practice",
                 "Tools and Workflow", "Professional Delivery",
                 "Advanced Systems"]
# ===========================================================================
# TALKING TO THE MODEL
# ===========================================================================

def _fill_prompt(topics, project, course, month_no, month_title, audience=""):
    """Stamp the live month into the author prompt's __TOKENS__."""
    timetable = "\n".join("- " + str(t) for t in (topics or []) if t) or \
                "- (the month's timetable topics)"
    return (AI_BOOK_PROMPT
            .replace("__TOPIC__", course or month_title or "this month's course")
            .replace("__AUDIENCE__", audience or "complete beginners with no experience")
            .replace("__COURSE__", str(course or ""))
            .replace("__MONTH__", str(month_no))
            .replace("__MONTH_TITLE__", str(month_title or ""))
            .replace("__TIMETABLE__", timetable)
            .replace("__PROJECT__", str(project or "the month project")))


def _extract_json(text):
    """Best-effort JSON out of a model answer (fences, prose, trailing notes).

    Scans string-aware balanced spans instead of first-{ to last-}, so chatty
    answers like 'Here is the JSON: {"ok": true}. Hope that helps.' still parse,
    and braces inside string values (code samples) never break the depth count.
    """
    cleaned = re.sub(r"```(?:json)?|```", "", (text or "")).strip()
    # Reasoning models sometimes leak <think>...</think> into content; drop it
    # (and any unclosed <think> tail) before scanning for balanced JSON.
    cleaned = re.sub(r"<think>.*?</think>", "", cleaned, flags=re.S | re.I).strip()
    cleaned = re.sub(r"<think>.*", "", cleaned, flags=re.S | re.I).strip()
    if not cleaned:
        return None
    for opener, closer in (("{", "}"), ("[", "]")):
        starts = [i for i, ch in enumerate(cleaned) if ch == opener][:8]
        for start in starts:
            depth, in_str, esc = 0, False, False
            for i in range(start, len(cleaned)):
                ch = cleaned[i]
                if in_str:
                    if esc:
                        esc = False
                    elif ch == "\\":
                        esc = True
                    elif ch == '"':
                        in_str = False
                elif ch == '"':
                    in_str = True
                elif ch == opener:
                    depth += 1
                elif ch == closer:
                    depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(cleaned[start:i + 1])
                        except Exception:
                            break
    return None


def _ask(messages, max_tokens=None):
    """One completion from the tutor model chain, or '' when no AI is reachable.

    Reuses ai_bridge so this books share the classroom's key handling, model
    chain and dead-model memory - and so boirsu.py never has to import the AI
    stack at module level (ai_bridge imports boirsu; that would be circular).
    """
    try:
        import ai_bridge
        completion = ai_bridge._chat_with_fallback(
            "text", messages, max_tokens or CONTENT_MAX_TOKENS)
        return (completion.choices[0].message.content or "")
    except Exception as exc:                       # no key, network, retired model
        print("[textbook_ai] AI unavailable (%s)" % str(exc)[:140])
        return ""


def _ask_json(messages, max_tokens=None):
    """Ask for JSON and retry once with a stricter nudge when it will not parse."""
    raw = _ask(messages, max_tokens)
    data = _extract_json(raw)
    if isinstance(data, dict):
        return data
    retry = list(messages) + [
        {"role": "assistant", "content": (raw or "")[:600]},
        {"role": "user", "content": "That was not valid JSON. Reply with RAW JSON "
                                    "ONLY - no markdown, no fences, no commentary."},
    ]
    return _extract_json(_ask(retry, max_tokens)) or {}


def ai_available():
    """True when a client can actually be built (key present), else False."""
    try:
        import ai_bridge
        return ai_bridge.client() is not None
    except Exception:
        return False
# ===========================================================================
# LAYOUT ENGINE - every clause of the layout rules, enforced in code
# ===========================================================================

class _BookPDF(FPDF):
    """A4 book page: 2.5 cm margins, running header/footer, latin-1-safe writes.

    Helvetica and Courier only encode latin-1, and model prose loves curly
    quotes and em dashes. Every string is routed through _safe() so a book can
    never die half-written with FPDFUnicodeEncodingException.
    """

    def __init__(self):
        super().__init__(format="A4")
        self.set_margins(MARGIN, MARGIN, MARGIN)
        self.set_auto_page_break(auto=True, margin=MARGIN)
        self.show_chrome = False        # the cover carries no header/footer
        self.chapter_title = ""
        self._raw_cell = FPDF.cell
        self._raw_multi_cell = FPDF.multi_cell

    @staticmethod
    def _safe(value):
        if isinstance(value, str):
            return value.encode("latin-1", "replace").decode("latin-1")
        return value

    def cell(self, *args, **kwargs):
        args = tuple(self._safe(a) for a in args)
        kwargs = {k: self._safe(v) for k, v in kwargs.items()}
        return self._raw_cell(self, *args, **kwargs)

    def multi_cell(self, *args, **kwargs):
        args = tuple(self._safe(a) for a in args)
        kwargs = {k: self._safe(v) for k, v in kwargs.items()}
        return self._raw_multi_cell(self, *args, **kwargs)

    def header(self):
        """Chapter name in the header, on every page except the cover."""
        if not self.show_chrome:
            return
        self.set_font("Helvetica", "I", 9)
        self.set_text_color(*GREY)
        self.set_xy(self.l_margin, 13)
        self.cell(USABLE_W, 5, self.chapter_title, align="R")
        self.set_text_color(*INK)
        self.set_y(self.t_margin)       # body always starts below the margin

    def footer(self):
        """Page number in the footer, on every page except the cover."""
        if not self.show_chrome:
            return
        self.set_y(-16)
        self.set_font("Helvetica", "", 9)
        self.set_text_color(*GREY)
        self.cell(USABLE_W, 5, str(self.page_no()), align="C")
        self.set_text_color(*INK)


def _ensure(pdf, needed):
    """Leave room for the next block; start a page rather than crowd or overlap."""
    if pdf.get_y() + needed > PAGE_H - MARGIN:
        pdf.add_page()


def _wrap(pdf, text, width, size, style="", family="Helvetica"):
    """Word-wrap with the PDF's own metrics, so nothing crosses the margin."""
    pdf.set_font(family, style, size)
    lines, current = [], ""
    for word in str(text or "").replace("\r", "").split():
        trial = (current + " " + word).strip()
        if not current or pdf.get_string_width(trial) <= width:
            current = trial
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [""]


def _paragraphs(text):
    """Model prose arrives in blocks; split it into real paragraphs."""
    parts = re.split(r"\n\s*\n", str(text or "").replace("\r", ""))
    return [re.sub(r"\s+", " ", p).strip() for p in parts if p.strip()]


def _as_list(value):
    """Models sometimes send "line\\nline" where a list was asked for."""
    if isinstance(value, str):
        return [ln.strip(" -\t*") for ln in value.splitlines() if ln.strip(" -\t*")]
    if isinstance(value, (list, tuple)):
        return list(value)
    return []


def _coerce_sections(got):
    """Accept the contracted chapter shape, one bare section, or a bare list.

    Models occasionally drop the {"chapter", "overview", "sections"} envelope
    and return the section object (or a list of them) directly; recover it.
    """
    def usable(s):
        return isinstance(s, dict) and (str(s.get("body") or "").strip()
                                        or str(s.get("heading") or "").strip())

    if isinstance(got, dict):
        raw = got.get("sections")
        if isinstance(raw, list):
            return [s for s in raw if usable(s)]
        if usable(got):
            return [got]
        return []
    if isinstance(got, list):
        return [s for s in got if usable(s)]
    return []


def _section_body(s):
    """The teaching text, whatever key the model put it under."""
    for key in ("body", "text", "content", "paragraphs", "prose", "explanation"):
        v = s.get(key)
        if isinstance(v, str) and len(v.split()) >= 20:
            return v
        if isinstance(v, list):                      # paragraph list
            joined = "\n\n".join(str(p) for p in v if str(p or "").strip())
            if len(joined.split()) >= 20:
                return joined
    return ""


def _write_para(pdf, text, size=BODY_PT, lead=BODY_LEAD, style="", indent=0.0):
    """Body copy: 11.5 pt, 1.4 spacing, clear space after every paragraph."""
    width = USABLE_W - indent
    pdf.set_text_color(*INK)
    for para in _paragraphs(text):
        lines = _wrap(pdf, para, width, size, style)
        for line in lines:
            _ensure(pdf, lead)
            pdf.set_font("Helvetica", style, size)
            pdf.set_x(MARGIN + indent)
            pdf.cell(width, lead, line, ln=True)
        pdf.ln(lead * 0.55)             # never let blocks touch each other


def _heading(pdf, text, size, before=4.0, after=2.0, rule=False):
    """A heading that is never left stranded at the foot of a page."""
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    if not text:
        return
    line_h = size * 0.52
    lines = _wrap(pdf, text, USABLE_W, size, "B")
    # Keep the heading together with at least two lines of what follows it.
    _ensure(pdf, before + len(lines) * line_h + after + BODY_LEAD * 2)
    pdf.ln(before)
    pdf.set_text_color(*ACCENT)
    pdf.set_font("Helvetica", "B", size)
    for line in lines:
        pdf.cell(USABLE_W, line_h, line, ln=True)
    if rule:
        pdf.set_draw_color(*RULE)
        pdf.line(MARGIN, pdf.get_y() + 1.2, PAGE_W - MARGIN, pdf.get_y() + 1.2)
        pdf.ln(2.0)
    pdf.ln(after)
    pdf.set_text_color(*INK)

def _bullets(pdf, items, numbered=False, size=BODY_PT, lead=BODY_LEAD):
    """Real bullet / numbered lists - never a slab of text, per the rules."""
    items = [str(i).strip() for i in _as_list(items) if str(i or "").strip()]
    if not items:
        return
    marker_w = 6.0
    width = USABLE_W - marker_w
    pdf.set_text_color(*INK)
    for n, item in enumerate(items, 1):
        marker = ("%d." % n) if numbered else "-"
        lines = _wrap(pdf, item, width, size)
        _ensure(pdf, lead * len(lines))
        pdf.set_font("Helvetica", "", size)
        pdf.set_x(MARGIN)
        pdf.cell(marker_w, lead, marker)
        pdf.set_x(MARGIN + marker_w)
        for i, line in enumerate(lines):
            if i:
                pdf.set_x(MARGIN + marker_w)
            pdf.cell(width, lead, line, ln=True)
    pdf.ln(lead * 0.5)


def _callout(pdf, title, items, fill):
    """A filled box (Common Mistakes / Key Points), padded, inside the margins."""
    items = [str(i).strip() for i in _as_list(items) if str(i or "").strip()]
    if not items:
        return
    inner = USABLE_W - 14.0                       # 7 mm padding on each side
    body = []
    for n, item in enumerate(items, 1):
        body.extend(_wrap(pdf, "%d. %s" % (n, item), inner, BODY_PT))
    height = 4.0 + 5.5 + len(body) * BODY_LEAD + 4.0
    if height > PAGE_H - 2 * MARGIN - 6:
        # Absurdly tall box: render as heading + list instead of overflowing.
        _heading(pdf, title, H3_PT, 3, 1)
        _bullets(pdf, items, numbered=True)
        return
    _ensure(pdf, height)
    top = pdf.get_y()
    pdf.set_fill_color(*fill)
    pdf.set_draw_color(*RULE)
    pdf.rect(MARGIN, top, USABLE_W, height, "DF")
    pdf.set_xy(MARGIN + 7.0, top + 4.0)
    pdf.set_font("Helvetica", "B", BODY_PT)
    pdf.set_text_color(*ACCENT)
    pdf.cell(inner, 5.5, title, ln=True)
    pdf.set_font("Helvetica", "", BODY_PT)
    pdf.set_text_color(*INK)
    for line in body:
        pdf.set_x(MARGIN + 7.0)
        pdf.cell(inner, BODY_LEAD, line, ln=True)
    pdf.set_y(top + height)
    pdf.ln(3.0)


def _code_box(pdf, code, lang=""):
    """Shaded monospace box; long lines are wrapped, never clipped or cramped."""
    text = str(code or "").replace("\r", "").rstrip()
    if not text:
        return
    inner = USABLE_W - 14.0
    lines = []
    for raw in text.split("\n"):
        if not raw.strip():
            lines.append("")
            continue
        lines.extend(_wrap(pdf, raw, inner, CODE_PT, family="Courier") or [""])
    height = 4.0 + len(lines) * CODE_LEAD + 4.0
    if height > PAGE_H - 2 * MARGIN - 6:
        # Listing taller than a page: let it flow, indented, rather than overlap.
        _ensure(pdf, CODE_LEAD * 3)
        for line in lines:
            _ensure(pdf, CODE_LEAD)
            pdf.set_font("Courier", "", CODE_PT)
            pdf.set_text_color(*INK)
            pdf.set_x(MARGIN)
            pdf.cell(USABLE_W, CODE_LEAD, "  " + line, ln=True)
        pdf.ln(2.0)
        return
    _ensure(pdf, height)
    top = pdf.get_y()
    pdf.set_fill_color(*CODE_BG)
    pdf.set_draw_color(*RULE)
    pdf.rect(MARGIN, top, USABLE_W, height, "DF")
    pdf.set_xy(MARGIN + 7.0, top + 4.0)
    pdf.set_font("Courier", "", CODE_PT)
    pdf.set_text_color(*INK)
    for line in lines:
        pdf.cell(inner, CODE_LEAD, line, ln=True)
    pdf.set_y(top + height)
    pdf.ln(2.0)

def _table(pdf, table):
    """Bordered table inside the margins, with padding in every cell."""
    if not isinstance(table, dict):
        return
    headers = [str(h) for h in (table.get("headers") or [])]
    rows = [list(r) for r in (table.get("rows") or [])
            if isinstance(r, (list, tuple))]
    if not headers and not rows:
        return
    cols = max([len(headers)] + [len(r) for r in rows] + [1])
    if cols < 1:
        return
    col_w = USABLE_W / float(cols)
    pad, lead = 1.6, 4.6
    text_w = col_w - pad * 2

    def cell_lines(value, bold=False):
        return _wrap(pdf, value, text_w, 9.5, "B" if bold else "")

    all_rows = ([headers] if headers else []) + rows
    heights = []
    for r in all_rows:
        n = 1
        for c in range(cols):
            n = max(n, len(cell_lines(r[c] if c < len(r) else "",
                                        bool(headers) and r is headers)))
        heights.append(n * lead + pad * 2)
    if sum(heights) > PAGE_H - 2 * MARGIN - 10:
        return          # absurd table: skip rather than overflow the page
    _ensure(pdf, sum(heights) + 4)

    pdf.set_draw_color(*RULE)
    y = pdf.get_y()
    for ri, r in enumerate(all_rows):
        is_header = bool(headers) and ri == 0
        h = heights[ri]
        if is_header:
            pdf.set_fill_color(*CODE_BG)
            pdf.rect(MARGIN, y, USABLE_W, h, "DF")
        else:
            pdf.rect(MARGIN, y, USABLE_W, h, "D")
        for c in range(1, cols):                    # column separators
            pdf.line(MARGIN + c * col_w, y, MARGIN + c * col_w, y + h)
        for c in range(cols):
            value = r[c] if c < len(r) else ""
            pdf.set_xy(MARGIN + c * col_w + pad, y + pad)
            pdf.set_font("Helvetica", "B" if is_header else "", 9.5)
            pdf.set_text_color(*INK)
            for line in cell_lines(value, is_header):
                pdf.cell(text_w, lead, line, ln=True)
        y += h
    pdf.set_y(y)
    pdf.ln(3.0)

def _toc_row(pdf, label, page):
    """One contents line: name left, page number right, on a single line."""
    pdf.set_font("Helvetica", "", BODY_PT)
    label = re.sub(r"\s+", " ", str(label or "")).strip()
    while pdf.get_string_width(label + "..") > USABLE_W - 12 and len(label) > 6:
        label = label[:-2].rstrip() + "."
    _ensure(pdf, BODY_LEAD)
    pdf.set_text_color(*INK)
    pdf.set_x(MARGIN)
    pdf.cell(USABLE_W - 12, BODY_LEAD, label)
    pdf.set_text_color(*GREY)
    pdf.cell(12, BODY_LEAD, str(page or ""), ln=True, align="R")
    pdf.set_text_color(*INK)


def _back_page(pdf, record, key, name):
    """A back-matter section: fresh page, ruled title, page number recorded."""
    pdf.chapter_title = name
    pdf.add_page()
    if record is not None:
        record.setdefault("back", {})[key] = pdf.page_no()
    _heading(pdf, name, H1_PT, 2, 3, rule=True)

def _render_book(pdf, data, record):
    """Draw the whole book.

    `record` maps every chapter and back-matter section to the page it starts
    on. The book is rendered TWICE: pass 1 fills `record` from a throwaway PDF,
    pass 2 re-renders into the real file while the contents page reads the
    true page numbers out of it.
    """
    chapters = [c for c in (data.get("chapters") or []) if isinstance(c, dict)]

    # ---- cover: title, subtitle, author-or-date - nothing else on the page ----
    pdf.show_chrome = False
    pdf.add_page()
    pdf.set_fill_color(*ACCENT)
    pdf.rect(0, 0, PAGE_W, PAGE_H, "F")
    pdf.set_text_color(255, 255, 255)
    pdf.set_y(92)
    for line in _wrap(pdf, data.get("title") or "Textbook", USABLE_W, 30, "B"):
        pdf.set_x(MARGIN)
        pdf.cell(USABLE_W, 13, line, align="C", ln=True)
    pdf.ln(8)
    for line in _wrap(pdf, data.get("subtitle") or "", USABLE_W, 15):
        pdf.set_x(MARGIN)
        pdf.cell(USABLE_W, 8.5, line, align="C", ln=True)
    pdf.set_y(PAGE_H - 55)
    pdf.set_x(MARGIN)
    pdf.cell(USABLE_W, 7, data.get("author_or_date") or "", align="C", ln=True)
    pdf.set_text_color(*INK)

    # ---- contents: real chapter names + REAL page numbers, own page ----
    pdf.show_chrome = True
    pdf.chapter_title = "Contents"
    pdf.add_page()
    _heading(pdf, "Table of Contents", H1_PT, 4, 4, rule=True)
    rec_ch = (record or {}).get("chapters", [])
    rec_back = (record or {}).get("back", {})
    for i, ch in enumerate(chapters, 1):
        page = rec_ch[i - 1] if i - 1 < len(rec_ch) else 0
        _toc_row(pdf, "Chapter %d - %s" % (i, ch.get("chapter")), page)
    back_rows = []
    if data.get("introduction"):
        back_rows.append(("introduction", "Introduction"))
    if [p for p in (data.get("practice") or []) if isinstance(p, dict)]:
        back_rows.append(("practice", "Practice Exercises"))
    if [a for a in (data.get("answers") or []) if isinstance(a, dict)]:
        back_rows.append(("answers", "Answers"))
    if data.get("conclusion") or data.get("next_steps"):
        back_rows.append(("conclusion", "Conclusion and Next Steps"))
    if [g for g in (data.get("glossary") or []) if isinstance(g, dict)]:
        back_rows.append(("glossary", "Glossary"))
    for key, label in back_rows:
        _toc_row(pdf, label, rec_back.get(key, 0))

    # ---- introduction ----
    if data.get("introduction"):
        _back_page(pdf, record, "introduction", "Introduction")
        _write_para(pdf, data["introduction"])

    # ---- chapters: each on a new page, kicker + 24 pt ruled title ----
    for i, ch in enumerate(chapters, 1):
        title = str(ch.get("chapter") or ("Chapter %d" % i))
        pdf.chapter_title = title          # runs in the header of its pages
        pdf.add_page()
        if record is not None:
            record.setdefault("chapters", [])
            while len(record["chapters"]) < i:
                record["chapters"].append(0)
            record["chapters"][i - 1] = pdf.page_no()
        _heading(pdf, "Chapter %d" % i, H3_PT, 2, 1)
        _heading(pdf, title, H1_PT, 0, 3, rule=True)
        if ch.get("overview"):
            _write_para(pdf, ch["overview"], style="I")
        for s in (ch.get("sections") or []):
            if not isinstance(s, dict):
                continue
            _heading(pdf, s.get("heading") or "In Practice", H2_PT, 6, 2)
            body = _section_body(s)
            if body:
                _write_para(pdf, body)
            for ex in (s.get("examples") or [])[:4]:
                if not isinstance(ex, dict):
                    continue
                _heading(pdf, "Example - %s" % (ex.get("lang") or "walkthrough"),
                         H3_PT, 3, 1)
                _code_box(pdf, ex.get("code"))
                if ex.get("explanation"):
                    _write_para(pdf, "How it works: " + str(ex["explanation"]),
                                size=11)
            _table(pdf, s.get("table"))
            _callout(pdf, "Common Mistakes", s.get("common_mistakes"),
                     (252, 237, 237))
            _callout(pdf, "Key Points", s.get("key_points"), (237, 245, 240))

    # ---- practice, answers, conclusion, glossary ----
    practice = [p for p in (data.get("practice") or []) if isinstance(p, dict)]
    if practice:
        _back_page(pdf, record, "practice", "Practice Exercises")
        _bullets(pdf, [p.get("prompt") or "" for p in practice], numbered=True)
    answers = [a for a in (data.get("answers") or []) if isinstance(a, dict)]
    if answers:
        _back_page(pdf, record, "answers", "Answers")
        _bullets(pdf, [a.get("answer") or "" for a in answers], numbered=True)
    if data.get("conclusion") or data.get("next_steps"):
        _back_page(pdf, record, "conclusion", "Conclusion and Next Steps")
        if data.get("conclusion"):
            _write_para(pdf, data["conclusion"])
        if data.get("next_steps"):
            _heading(pdf, "Suggested Next Steps", H2_PT, 4, 1)
            _bullets(pdf, data["next_steps"])
    glossary = [g for g in (data.get("glossary") or []) if isinstance(g, dict)]
    if glossary:
        _back_page(pdf, record, "glossary", "Glossary")
        _bullets(pdf, ["%s - %s" % (g.get("term") or "", g.get("definition") or "")
                       for g in glossary if g.get("term")])

# ===========================================================================
# ASSEMBLY
# ===========================================================================

def book_word_count(data):
    """Words of real teaching text - headings, contents and code excluded,
    exactly as the brief demands the 3,000-word target be counted."""
    words = len(str(data.get("introduction") or "").split())
    words += len(str(data.get("conclusion") or "").split())
    for ch in (data.get("chapters") or []):
        if not isinstance(ch, dict):
            continue
        words += len(str(ch.get("overview") or "").split())
        for s in (ch.get("sections") or []):
            if not isinstance(s, dict):
                continue
            words += len(_section_body(s).split())
            for ex in (s.get("examples") or []):
                if isinstance(ex, dict):
                    words += len(str(ex.get("explanation") or "").split())
            words += sum(len(str(i).split()) for i in (s.get("common_mistakes") or []))
            words += sum(len(str(i).split()) for i in (s.get("key_points") or []))
    for row in (data.get("practice") or []):
        if isinstance(row, dict):
            words += len(str(row.get("prompt") or "").split())
    for row in (data.get("answers") or []):
        if isinstance(row, dict):
            words += len(str(row.get("answer") or "").split())
    for term in (data.get("glossary") or []):
        if isinstance(term, dict):
            words += len(str(term.get("definition") or "").split())
    return words

def build_ai_textbook(career_path, month_number, filepath,
                      roadmap=None, month_plan=None):
    """Have the tutor model WRITE this month's textbook, then render it to A4.

    Returns the path written, or None when the AI path is off, unavailable, or
    produced too little - in every one of those cases the caller keeps its own
    template pipeline, so book generation never breaks.
    """
    if str(os.environ.get("BOIRSU_AI_TEXTBOOK", "1")).strip().lower() in ("0", "false", "no"):
        return None
    if FPDF is None:
        return None
    try:
        import boirsu
        roadmap = roadmap or boirsu.CAREER_ROADMAPS.get(career_path) or {}
        if month_plan is None:
            plans = roadmap.get("monthly_plan") or []
            if 1 <= month_number <= len(plans):
                month_plan = plans[month_number - 1]
    except Exception as exc:                    # never break generation over this
        print("[textbook_ai] could not read the roadmap (%s)" % str(exc)[:120])
        return None
    roadmap = roadmap or {}
    month_plan = month_plan or {}
    if not month_plan:
        return None

    topics = [str(t) for t in (month_plan.get("topics") or []) if t]
    project = month_plan.get("project") or ""
    course_title = roadmap.get("title") or str(career_path)
    month_title = month_plan.get("title") or ("Month %d" % month_number)

    if not ai_available():
        print("[textbook_ai] no AI client configured - template fallback will run")
        return None

    prompt = _fill_prompt(topics, project, course_title, month_number, month_title)

    # STEP 1 - the book plan (title, intro, chapter list, glossary).
    plan = _ask_json([
        {"role": "system", "content": prompt},
        {"role": "user",
         "content": PLAN_CONTRACT.replace("__CHAPTERS__", str(CHAPTER_TARGET))},
    ])
    chapters = [c for c in (plan.get("chapters") or []) if isinstance(c, dict)][:14]
    if not plan or not chapters:
        print("[textbook_ai] plan step unusable - template fallback will run")
        return None
    # Top up to the required chapter count using the REAL timetable topics,
    # so the book always reaches the 6-chapter shape the brief demands.
    while len(chapters) < CHAPTER_TARGET:
        idx = len(chapters)
        name = topics[idx % len(topics)] if topics else \
            CHAPTER_ORDER[idx % len(CHAPTER_ORDER)]
        chapters.append({"chapter": str(name), "overview": ""})

    # STEP 2 - each chapter written in full, one model call each.
    written = []
    for i, ch in enumerate(chapters, 1):
        name = str(ch.get("chapter") or ("Chapter %d" % i))
        ask = (CHAPTER_CONTRACT
               + "\nThis is chapter %d of %d. Its title is: %s\n"
                 "Its planned overview: %s\nWrite this chapter now."
                 % (i, len(chapters), name, ch.get("overview") or ""))
        got = _ask_json([{"role": "system", "content": prompt},
                         {"role": "user", "content": ask}],
                        max_tokens=CONTENT_MAX_TOKENS)
        sections = _coerce_sections(got)
        if sections and not any(_section_body(s) for s in sections):
            print("[textbook_ai] chapter %d (%s) had no real body text - skipped"
                  % (i, name[:60]))
            sections = []
        if not sections:
            print("[textbook_ai] chapter %d (%s) came back empty - skipped"
                  % (i, name[:60]))
            continue
        written.append({"chapter": got.get("chapter") or name,
                        "overview": got.get("overview") or ch.get("overview") or "",
                        "sections": sections})
    if len(written) < 3:
        print("[textbook_ai] only %d chapters written - template fallback will run"
              % len(written))
        return None

    # STEP 3 - practice, answers, conclusion, next steps.
    tail = _ask_json([{"role": "system", "content": prompt},
                      {"role": "user", "content": TAIL_CONTRACT}],
                     max_tokens=CONTENT_MAX_TOKENS)

    # ---- assemble the book document ----
    from datetime import date
    data = {
        "title": plan.get("title") or ("Textbook: %s - %s" % (course_title, month_title)),
        "subtitle": plan.get("subtitle") or
                    ("%s, Month %d: %s" % (course_title, month_number, month_title)),
        "author_or_date": "DevSphere Academy | %s" % date.today().strftime("%B %Y"),
        "audience": plan.get("audience") or "",
        "introduction": plan.get("introduction") or "",
        "chapters": written,
        "practice": [p for p in (tail.get("practice") or []) if isinstance(p, dict)],
        "answers": [a for a in (tail.get("answers") or []) if isinstance(a, dict)],
        "conclusion": tail.get("conclusion") or "",
        "next_steps": [str(s).strip() for s in _as_list(tail.get("next_steps"))
                       if str(s or "").strip()],
        "glossary": [g for g in (plan.get("glossary") or []) if isinstance(g, dict)],
    }

    # ---- quality gate, straight out of the prompt's own checklist ----
    words = book_word_count(data)
    if words < 1500:
        print("[textbook_ai] only %d words of content - too thin for a textbook; "
              "template fallback will run" % words)
        return None
    if words < 3000:
        print("[textbook_ai] WARNING: %d words, under the 3,000-word target "
              "(accepting: a real attempt beats a template book)" % words)

    # ---- render twice: measure for real contents numbers, then write ----
    try:
        _render_book(_BookPDF(), data, record := {})
        pdf = _BookPDF()
        _render_book(pdf, data, record)
        pdf.output(str(filepath))
    except Exception as exc:
        print("[textbook_ai] render failed (%s) - no book will be filed"
              % str(exc)[:160])
        return None
    # Positive marker that THIS file is an AI-written book (never a pre-written
    # template): the library shelf lists only PDFs carrying it.
    try:
        with open(str(filepath.with_suffix(".ai")), "w", encoding="utf-8") as fh:
            fh.write("textbook_ai|%s|%s" % (career_path, month_number))
    except Exception:
        pass
    print("[textbook_ai] wrote %s - %d chapters, %d pages, %d words, "
          "real TOC page numbers" % (os.path.basename(str(filepath)),
                                     len(written), pdf.page_no(), words))
    return str(filepath)