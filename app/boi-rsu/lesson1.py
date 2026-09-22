#!/usr/bin/env python3
"""
generate_lesson_pdf.py
=======================

Turns a plain-text lesson note into a polished, illustrated PDF, using
NVIDIA's hosted FLUX.1-dev NIM endpoint to generate the images.

--------------------------------------------------------------------
QUICK START
--------------------------------------------------------------------
1. Get an API key from https://build.nvidia.com (free tier available).
   export NVIDIA_API_KEY="nvapi-xxxxxxxxxxxxxxxxxxxxx"

2. Install dependencies:
   pip install requests reportlab pillow --break-system-packages

3. Write your lesson note as lessons/<ClassName>/lesson.md (see the
   sample file created next to this script for the exact format).

4. (Optional) Drop reference images you like the look of into
   lessons/<ClassName>/references/  -- these are NOT sent to the model
   (the public NIM endpoint only accepts NVIDIA's own preset images for
   image-conditioning), but the script mentions them so you remember to
   describe that visual style in your [IMAGE: ...] prompts. If you want
   true image-to-image / style-matching, run FLUX.1-dev's canny/depth
   NIM container locally and swap in the request body -- see the
   `FluxClient.generate` docstring for where that plugs in.

5. Run:
   python3 generate_lesson_pdf.py --lessons-dir lessons --output-dir output

Each class folder becomes one nicely designed PDF in output/.

--------------------------------------------------------------------
LESSON NOTE FORMAT  (lessons/<ClassName>/lesson.md)
--------------------------------------------------------------------
Class: Biology - SS2
Teacher: Mr. Adeyemi
Date: 2026-07-04

# Photosynthesis: How Plants Make Their Own Food

## Introduction
Plain paragraphs of your detailed note go here. Write as much as you want.

[IMAGE: labelled scientific diagram of a plant cell showing chloroplasts,
clean textbook style, bright educational colors]

## The Light Reactions
More detailed notes...

[IMAGE: sunlight hitting a green leaf, cross-section view showing light
being absorbed, educational illustration style]

--------------------------------------------------------------------
Any line starting with "[IMAGE: ...]" becomes an illustration generated
by FLUX.1-dev and placed right at that point in the PDF. Everything else
is treated as your lesson text and is reproduced exactly as written --
this script does NOT rewrite or summarize your notes.
"""

import argparse
import base64
import hashlib
import io
import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import requests
from PIL import Image
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image as RLImage,
    PageBreak, Table, TableStyle, KeepTogether, HRFlowable
)

NVIDIA_API_URL = "https://ai.api.nvidia.com/v1/genai/black-forest-labs/flux.1-dev"

# A short suffix appended to every prompt so illustrations stay consistent
# and look "textbook-clean" rather than photorealistic/cluttered.
DEFAULT_STYLE_SUFFIX = (
    ", clean modern educational illustration, flat design, soft lighting, "
    "vibrant but tasteful color palette, high detail, no text or labels "
    "unless requested, safe for classroom use"
)

ACCENT_COLOR = colors.HexColor("#2454A0")   # deep school-blue
ACCENT_LIGHT = colors.HexColor("#EAF1FB")
TEXT_COLOR = colors.HexColor("#1C1C1C")


# ---------------------------------------------------------------------------
# FLUX.1-dev client (NVIDIA NIM cloud API)
# ---------------------------------------------------------------------------

class FluxClient:
    def __init__(self, api_key: str, cache_dir: Path, steps: int = 40,
                 cfg_scale: float = 4.0, width: int = 1024, height: int = 1024):
        if not api_key:
            raise RuntimeError(
                "No NVIDIA API key found. Set it with:\n"
                "  export NVIDIA_API_KEY='nvapi-...'\n"
                "Get a free key at https://build.nvidia.com"
            )
        self.api_key = api_key
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.steps = steps
        self.cfg_scale = cfg_scale
        self.width = width
        self.height = height

    def _cache_path(self, prompt: str, seed: int) -> Path:
        key = hashlib.sha256(f"{prompt}|{seed}|{self.width}x{self.height}".encode()).hexdigest()[:24]
        return self.cache_dir / f"{key}.png"

    def generate(self, prompt: str, seed: int = 0, retries: int = 4) -> Path:
        """
        Generate one image from a text prompt and return the local file path.
        Results are cached on disk keyed by prompt+seed+size, so re-running
        the script on the same lesson note won't re-spend API calls.

        NOTE on image-conditioning: the public trial endpoint's "image" field
        (mode="canny"/"depth") only accepts NVIDIA's own preset example
        images (image data:image/png;example_id,{0..3}), not arbitrary
        uploads. To truly condition generation on YOUR reference photos,
        self-host the NIM container (docker run ... nvcr.io/nim/
        black-forest-labs/flux.1-dev) and point NVIDIA_API_URL at your
        local http://localhost:8000/v1/infer instead -- that local server
        accepts real uploaded images for canny/depth guidance.
        """
        cache_file = self._cache_path(prompt, seed)
        if cache_file.exists():
            print(f"  [cache hit] {prompt[:60]}...")
            return cache_file

        payload = {
            "prompt": prompt[:1000],
            "mode": "base",
            "width": self.width,
            "height": self.height,
            "cfg_scale": self.cfg_scale,
            "steps": self.steps,
            "seed": seed,
            "samples": 1,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        last_err = None
        for attempt in range(1, retries + 1):
            try:
                print(f"  [generating] {prompt[:60]}... (attempt {attempt})")
                resp = requests.post(NVIDIA_API_URL, headers=headers, json=payload, timeout=120)
                if resp.status_code == 422:
                    raise RuntimeError(f"Validation error from NVIDIA API: {resp.text}")
                if resp.status_code in (429, 500, 502, 503, 504):
                    raise RuntimeError(f"Transient error {resp.status_code}: {resp.text[:200]}")
                resp.raise_for_status()
                b64 = self._extract_b64(resp.json())
                img_bytes = base64.b64decode(b64)
                Image.open(io.BytesIO(img_bytes)).convert("RGB").save(cache_file, "PNG")
                return cache_file
            except Exception as e:
                last_err = e
                wait = min(2 ** attempt, 20)
                print(f"    -> {e}\n    retrying in {wait}s...")
                time.sleep(wait)

        raise RuntimeError(f"Failed to generate image after {retries} attempts: {last_err}")

    @staticmethod
    def _extract_b64(data: dict) -> str:
        """Handle a few possible response shapes defensively."""
        if isinstance(data, dict):
            if "image" in data and isinstance(data["image"], str):
                return data["image"].split(",")[-1]
            if "images" in data and data["images"]:
                first = data["images"][0]
                return first if isinstance(first, str) else first.get("base64") or first.get("b64_json")
            if "artifacts" in data and data["artifacts"]:
                return data["artifacts"][0]["base64"]
            if "data" in data and data["data"]:
                first = data["data"][0]
                return first.get("b64_json") or first.get("base64")
        raise RuntimeError(f"Could not find image data in response: {str(data)[:300]}")


# ---------------------------------------------------------------------------
# Lesson note parsing
# ---------------------------------------------------------------------------

@dataclass
class LessonBlock:
    kind: str          # 'heading2' | 'heading3' | 'para' | 'image' | 'callout'
    text: str = ""


@dataclass
class Lesson:
    class_name: str = ""
    teacher: str = ""
    date: str = ""
    title: str = "Lesson Note"
    blocks: list = field(default_factory=list)
    reference_images: list = field(default_factory=list)


IMAGE_RE = re.compile(r"^\[IMAGE:\s*(.+?)\]\s*$", re.IGNORECASE)
META_RE = re.compile(r"^(Class|Teacher|Date)\s*:\s*(.+)$", re.IGNORECASE)
CALLOUT_RE = re.compile(r"^(Key Concept|Quick Tip|Mini Quiz|Challenge|Exercise|Example|Output|Explanation|Common Errors)\s*[:\-]\s*(.+)$", re.IGNORECASE)


def parse_lesson_file(path: Path) -> Lesson:
    lesson = Lesson()
    raw = path.read_text(encoding="utf-8")
    lines = raw.splitlines()

    para_buf = []

    def flush_para():
        if para_buf:
            text = " ".join(l.strip() for l in para_buf if l.strip())
            if text:
                lesson.blocks.append(LessonBlock("para", text))
            para_buf.clear()

    i = 0
    # optional multi-line [IMAGE: ...] support: join continuation lines
    # until the closing ']'
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        meta_match = META_RE.match(stripped)
        if meta_match and not lesson.blocks:
            key, val = meta_match.group(1).lower(), meta_match.group(2).strip()
            if key == "class":
                lesson.class_name = val
            elif key == "teacher":
                lesson.teacher = val
            elif key == "date":
                lesson.date = val
            i += 1
            continue

        if stripped.startswith("# "):
            flush_para()
            lesson.title = stripped[2:].strip()
            i += 1
            continue

        if stripped.startswith("## "):
            flush_para()
            lesson.blocks.append(LessonBlock("heading2", stripped[3:].strip()))
            i += 1
            continue

        if stripped.startswith("### "):
            flush_para()
            lesson.blocks.append(LessonBlock("heading3", stripped[4:].strip()))
            i += 1
            continue

        if stripped.startswith("[IMAGE:") or stripped.startswith("[image:"):
            flush_para()
            buf = stripped
            while not buf.rstrip().endswith("]") and i + 1 < len(lines):
                i += 1
                buf += " " + lines[i].strip()
            m = IMAGE_RE.match(buf)
            if m:
                lesson.blocks.append(LessonBlock("image", m.group(1).strip()))
            i += 1
            continue

        if CALLOUT_RE.match(stripped):
            flush_para()
            label, value = CALLOUT_RE.match(stripped).groups()
            lesson.blocks.append(LessonBlock("callout", f"{label}: {value.strip()}"))
            i += 1
            continue

        if stripped == "":
            flush_para()
            i += 1
            continue

        para_buf.append(line)
        i += 1

    flush_para()
    return lesson


def find_reference_images(class_dir: Path) -> list:
    ref_dir = class_dir / "references"
    if not ref_dir.is_dir():
        return []
    exts = {".png", ".jpg", ".jpeg", ".webp"}
    return sorted(p for p in ref_dir.iterdir() if p.suffix.lower() in exts)


# ---------------------------------------------------------------------------
# PDF building
# ---------------------------------------------------------------------------

def build_styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="LessonTitle", fontName="Helvetica-Bold", fontSize=26,
        leading=32, textColor=colors.white, alignment=TA_CENTER, spaceAfter=8, spaceBefore=6,
    ))
    styles.add(ParagraphStyle(
        name="LessonSubtitle", fontName="Helvetica", fontSize=12,
        leading=16, textColor=colors.white, alignment=TA_CENTER, spaceAfter=3,
    ))
    styles.add(ParagraphStyle(
        name="SectionHeading", fontName="Helvetica-Bold", fontSize=17,
        leading=22, textColor=ACCENT_COLOR, spaceBefore=20, spaceAfter=10,
    ))
    styles.add(ParagraphStyle(
        name="SubHeading", fontName="Helvetica-Bold", fontSize=13,
        leading=18, textColor=colors.HexColor("#23374D"), spaceBefore=12, spaceAfter=8,
    ))
    styles.add(ParagraphStyle(
        name="BodyTextLesson", fontName="Helvetica", fontSize=11.5,
        leading=17, textColor=TEXT_COLOR, spaceAfter=10, alignment=4,
        firstLineIndent=0.35 * cm,
    ))
    styles.add(ParagraphStyle(
        name="MetaLabel", fontName="Helvetica-Bold", fontSize=10.5,
        leading=13, textColor=ACCENT_COLOR, spaceAfter=2,
    ))
    styles.add(ParagraphStyle(
        name="MetaValue", fontName="Helvetica", fontSize=10.5,
        leading=13, textColor=TEXT_COLOR, spaceAfter=2,
    ))
    styles.add(ParagraphStyle(
        name="ImageCaption", fontName="Helvetica-Oblique", fontSize=9,
        leading=12, textColor=colors.HexColor("#666666"), alignment=TA_CENTER,
        spaceAfter=16, spaceBefore=6,
    ))
    styles.add(ParagraphStyle(
        name="CalloutBox", fontName="Helvetica-Bold", fontSize=11,
        leading=14, textColor=ACCENT_COLOR, alignment=TA_CENTER,
        spaceAfter=8, spaceBefore=8,
    ))
    return styles


def header_footer(canvas_obj, doc, class_name: str, page_image_path: str | Path | None = None):
    canvas_obj.saveState()
    canvas_obj.setStrokeColor(ACCENT_COLOR)
    canvas_obj.setLineWidth(0.6)
    canvas_obj.line(2 * cm, 27.3 * cm, A4[0] - 2 * cm, 27.3 * cm)
    canvas_obj.setFont("Helvetica", 8)
    canvas_obj.setFillColor(colors.HexColor("#888888"))
    canvas_obj.drawString(2 * cm, 27.5 * cm, class_name or "Lesson Note")
    canvas_obj.drawRightString(A4[0] - 2 * cm, 1.3 * cm, f"Page {doc.page}")
    canvas_obj.drawString(2 * cm, 1.3 * cm, "Generated with FLUX.1-dev")

    if page_image_path:
        try:
            image_path = str(page_image_path)
            with Image.open(image_path) as img:
                width, height = img.size
            image_width = 4.4 * cm
            image_height = image_width * height / width
            canvas_obj.drawImage(
                image_path,
                2 * cm,
                22.1 * cm,
                width=image_width,
                height=image_height,
                mask="auto",
            )
        except Exception:
            pass

    canvas_obj.restoreState()


def cover_page_flowables(lesson: Lesson, cover_image_path: Path, styles):
    story = []
    story.append(Spacer(1, 0.6 * cm))
    img = RLImage(str(cover_image_path), width=15.5 * cm, height=15.5 * cm, hAlign="CENTER")
    title_block = Table(
        [[Paragraph(lesson.title, styles["LessonTitle"])],
         [Paragraph(
             f"{lesson.class_name or ''}"
             + (f" &nbsp;|&nbsp; {lesson.teacher}" if lesson.teacher else "")
             + (f" &nbsp;|&nbsp; {lesson.date}" if lesson.date else ""),
             styles["LessonSubtitle"])]],
        colWidths=[15.5 * cm],
    )
    title_block.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), ACCENT_COLOR),
        ("TOPPADDING", (0, 0), (-1, -1), 16),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 16),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
    ]))
    story.append(img)
    story.append(Spacer(1, 0.4 * cm))
    story.append(title_block)
    story.append(Spacer(1, 0.8 * cm))
    story.append(HRFlowable(width="100%", color=ACCENT_LIGHT, thickness=2))
    story.append(PageBreak())
    return story


def lesson_overview_flowables(lesson: Lesson, styles):
    story = []
    story.append(Spacer(1, 0.3 * cm))
    overview_title = Paragraph("Lesson Overview", styles["SubHeading"])
    story.append(overview_title)

    meta_rows = []
    if lesson.title:
        meta_rows.append([Paragraph("Topic", styles["MetaLabel"]), Paragraph(lesson.title, styles["MetaValue"])])
    if lesson.class_name:
        meta_rows.append([Paragraph("Class", styles["MetaLabel"]), Paragraph(lesson.class_name, styles["MetaValue"])])
    if lesson.teacher:
        meta_rows.append([Paragraph("Teacher", styles["MetaLabel"]), Paragraph(lesson.teacher, styles["MetaValue"])])
    if lesson.date:
        meta_rows.append([Paragraph("Date", styles["MetaLabel"]), Paragraph(lesson.date, styles["MetaValue"])])

    if meta_rows:
        table = Table(meta_rows, colWidths=[2.4 * cm, 12.2 * cm], repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFE")),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#DDE7F7")),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(table)
    story.append(Spacer(1, 0.4 * cm))
    return story


def build_pdf(lesson: Lesson, image_paths: dict, output_path: Path, cover_image_path: Path):
    styles = build_styles()
    doc = SimpleDocTemplate(
        str(output_path), pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm, topMargin=2.2 * cm, bottomMargin=2 * cm,
        title=lesson.title, author=lesson.teacher or "Lesson Generator",
    )

    story = []
    story.extend(cover_page_flowables(lesson, cover_image_path, styles))
    story.extend(lesson_overview_flowables(lesson, styles))

    for block in lesson.blocks:
        if block.kind == "heading2":
            story.append(KeepTogether([
                Paragraph(block.text, styles["SectionHeading"]),
                HRFlowable(width="100%", color=ACCENT_LIGHT, thickness=1.4, spaceAfter=6),
            ]))
        elif block.kind == "heading3":
            story.append(Paragraph(block.text, styles["SubHeading"]))
        elif block.kind == "para":
            story.append(Paragraph(block.text, styles["BodyTextLesson"]))
        elif block.kind == "image":
            img_path = image_paths.get(block.text)
            if img_path and img_path.exists():
                with Image.open(img_path) as im:
                    w, h = im.size
                max_w = 13 * cm
                disp_w = max_w
                disp_h = max_w * h / w
                story.append(Spacer(1, 0.35 * cm))
                story.append(RLImage(str(img_path), width=disp_w, height=disp_h, hAlign="CENTER"))
                story.append(Spacer(1, 0.2 * cm))
                story.append(Paragraph(block.text, styles["ImageCaption"]))
        elif block.kind == "callout":
            story.append(Spacer(1, 0.15 * cm))
            story.append(Table(
                [[Paragraph(block.text, styles["CalloutBox"])]],
                colWidths=[13.5 * cm],
            ))
            story.append(Spacer(1, 0.2 * cm))

    doc.build(
        story,
        onFirstPage=lambda c, d: header_footer(c, d, lesson.class_name, cover_image_path),
        onLaterPages=lambda c, d: header_footer(c, d, lesson.class_name, cover_image_path),
    )


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def process_class_dir(class_dir: Path, output_dir: Path, flux: FluxClient, style_suffix: str):
    lesson_file = class_dir / "lesson.md"
    if not lesson_file.exists():
        print(f"[skip] {class_dir.name}: no lesson.md found")
        return

    print(f"\n=== Processing '{class_dir.name}' ===")
    lesson = parse_lesson_file(lesson_file)
    lesson.class_name = lesson.class_name or class_dir.name.replace("_", " ")
    lesson.reference_images = find_reference_images(class_dir)

    if lesson.reference_images:
        print(f"  Found {len(lesson.reference_images)} reference image(s) in "
              f"{class_dir / 'references'} -- use their style/subject in your "
              f"[IMAGE: ...] prompts for consistency (see script docstring).")

    # Generate all inline concept/decorative illustrations
    image_paths = {}
    for block in lesson.blocks:
        if block.kind == "image" and block.text not in image_paths:
            full_prompt = block.text + style_suffix
            image_paths[block.text] = flux.generate(full_prompt, seed=abs(hash(block.text)) % (2**31))

    # Generate a cover illustration from the title + first paragraph for context
    first_para = next((b.text for b in lesson.blocks if b.kind == "para"), "")
    cover_prompt = (
        f"Cover illustration for a lesson titled '{lesson.title}'. "
        f"Context: {first_para[:150]}" + style_suffix
    )
    cover_image_path = flux.generate(cover_prompt, seed=abs(hash(lesson.title)) % (2**31))

    output_dir.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r"[^A-Za-z0-9_-]+", "_", class_dir.name)
    out_pdf = output_dir / f"{safe_name}.pdf"
    build_pdf(lesson, image_paths, out_pdf, cover_image_path)
    print(f"  -> Saved {out_pdf}")


def main():
    parser = argparse.ArgumentParser(description="Generate illustrated lesson-note PDFs using FLUX.1-dev (NVIDIA NIM).")
    parser.add_argument("--lessons-dir", default="lessons", help="Folder containing one subfolder per class")
    parser.add_argument("--output-dir", default="output", help="Where finished PDFs are written")
    parser.add_argument("--cache-dir", default="cache", help="Where generated images are cached")
    parser.add_argument("--steps", type=int, default=40, help="Diffusion steps (5-100, higher = better/slower)")
    parser.add_argument("--cfg-scale", type=float, default=4.0, help="Prompt adherence (<=9)")
    parser.add_argument("--style-suffix", default=DEFAULT_STYLE_SUFFIX, help="Appended to every image prompt")
    parser.add_argument("--api-key", default=os.environ.get("NVIDIA_API_KEY"), help="NVIDIA API key (or set NVIDIA_API_KEY env var)")
    args = parser.parse_args()

    flux = FluxClient(api_key=args.api_key, cache_dir=Path(args.cache_dir), steps=args.steps, cfg_scale=args.cfg_scale)

    lessons_dir = Path(args.lessons_dir)
    if not lessons_dir.is_dir():
        print(f"Lessons directory not found: {lessons_dir}", file=sys.stderr)
        sys.exit(1)

    class_dirs = sorted(p for p in lessons_dir.iterdir() if p.is_dir())
    if not class_dirs:
        print(f"No class subfolders found inside {lessons_dir}", file=sys.stderr)
        sys.exit(1)

    for class_dir in class_dirs:
        try:
            process_class_dir(class_dir, Path(args.output_dir), flux, args.style_suffix)
        except Exception as e:
            print(f"[ERROR] {class_dir.name}: {e}", file=sys.stderr)

    print("\nAll done.")


if __name__ == "__main__":
    main()
