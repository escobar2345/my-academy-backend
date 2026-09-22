#!/usr/bin/env python3
"""
flashcard_generator.py

Turns a large block of text into 1-10 good-looking, detailed flashcard
images using NVIDIA NIM's hosted FLUX.1-dev endpoint for the artwork,
plus crisp text overlays for the title/body (since diffusion models
can't reliably render text).

Pipeline
--------
1. SPLIT   : the input text is broken into 1-10 flashcard "concepts"
             (title + short concept description + supporting detail).
             This uses an NVIDIA NIM-hosted LLM (chat completions,
             OpenAI-compatible) so the split is meaning-aware, not just
             a naive paragraph chop. If that call fails for any reason
             (no key, network, etc.) a rule-based paragraph/sentence
             splitter is used instead, so the script always works.

2. DESIGN  : every concept is dropped into a fixed STYLE_TEMPLATE (this
             is the "system prompt" for FLUX -- it's what keeps every
             card visually consistent). FLUX.1-dev is only asked to
             generate a background illustration/icon, never long text.

3. RENDER  : NVIDIA NIM's hosted FLUX.1-dev endpoint
             (https://ai.api.nvidia.com/v1/genai/black-forest-labs/flux.1-dev)
             generates the background art for each card.

4. COMPOSE : the real title/detail text is overlaid on top of the
             generated art with Pillow, laid out like a flashcard
             (title banner + illustration area + detail strip),
             so the text is always crisp and correctly spelled.

Requirements
------------
    pip install requests pillow

Setup
-----
    export NVIDIA_API_KEY="nvapi-...."      # https://build.nvidia.com

Usage
-----
    python flashcard_generator.py --text "paste your long text here"
    python flashcard_generator.py --file notes.txt
    python flashcard_generator.py --file notes.txt --max-cards 6 --out ./cards
"""

import argparse
import base64
import json
import os
import re
import sys
import textwrap
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# --------------------------------------------------------------------------
# CONFIG
# --------------------------------------------------------------------------

NVIDIA_API_KEY = os.environ.get("NVIDIA_API_KEY", "")

FLUX_URL = "https://ai.api.nvidia.com/v1/genai/black-forest-labs/flux.1-dev"
# Any NVIDIA NIM-hosted chat model works here; this one is small/fast/cheap.
# Swap for anything else listed at https://build.nvidia.com if you prefer.
LLM_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
LLM_MODEL = "meta/llama-3.1-70b-instruct"

IMAGE_SIZE = 1024          # FLUX.1-dev NIM only supports square 1024x1024 reliably
CARD_W, CARD_H = 1024, 768  # final flashcard canvas (4:3-ish)

FONT_DIR_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu",
    "/usr/share/fonts/truetype/DejaVuSans",
    "C:/Windows/Fonts",  # Windows fallback
]

# --------------------------------------------------------------------------
# STYLE TEMPLATE  ("system prompt" for FLUX.1-dev design consistency)
# --------------------------------------------------------------------------
# This is deliberately text-light: FLUX is unreliable at rendering words,
# so we only ask it for a clean background illustration/icon. The real
# title/detail text is drawn separately with Pillow in compose_flashcard().

STYLE_TEMPLATE = (
    "A clean, modern educational flashcard background illustration, "
    "flat vector illustration style, minimalist design, soft pastel color "
    "palette, high contrast, centered simple icon or scene representing: "
    "{concept}. Professional edtech aesthetic, plenty of negative space "
    "at the top and bottom for text overlays, subtle soft shadow, "
    "rounded shapes, no text, no letters, no numbers, no words anywhere "
    "in the image, no watermark, no signature, crisp vector lines, "
    "high resolution, studio lighting, sharp focus, 1:1 aspect ratio."
)

NEGATIVE_HINT = (
    "blurry, low quality, cluttered, distorted, extra limbs, "
    "watermark, text, letters, words, signature"
)

# --------------------------------------------------------------------------
# STEP 1: SPLIT TEXT INTO FLASHCARD CONCEPTS
# --------------------------------------------------------------------------

def estimate_card_count(text: str, max_cards: int = 10) -> int:
    """Scale card count with text length: ~1 card per 120 words, clamped 1-10."""
    word_count = len(text.split())
    n = max(1, round(word_count / 120))
    return min(n, max_cards)


def llm_split(text: str, n_cards: int) -> list:
    """Ask an NVIDIA NIM-hosted LLM to split text into n_cards flashcards."""
    if not NVIDIA_API_KEY:
        raise RuntimeError("NVIDIA_API_KEY not set")

    system_prompt = (
        "You are a study-flashcard designer. Given source text, split it "
        "into the most important, distinct concepts. Return ONLY valid "
        "JSON — no markdown fences, no commentary — as a list of objects "
        "each with keys: 'title' (2-4 words), 'concept' (3-8 word visual "
        "description an illustrator could draw, no text/labels), and "
        "'detail' (one short sentence, max 18 words, factual and exam-ready)."
    )
    user_prompt = (
        f"Split the following text into exactly {n_cards} flashcards.\n\n"
        f"TEXT:\n{text}\n\n"
        f'Return JSON like: [{{"title": "...", "concept": "...", "detail": "..."}}, ...]'
    )

    resp = requests.post(
        LLM_URL,
        headers={
            "Authorization": f"Bearer {NVIDIA_API_KEY}",
            "Accept": "application/json",
        },
        json={
            "model": LLM_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.4,
            "max_tokens": 1200,
        },
        timeout=60,
    )
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"].strip()

    # Strip accidental markdown fences
    content = re.sub(r"^```json|^```|```$", "", content, flags=re.MULTILINE).strip()
    cards = json.loads(content)

    cleaned = []
    for c in cards[:n_cards]:
        cleaned.append({
            "title": str(c.get("title", "")).strip()[:40] or "Key Concept",
            "concept": str(c.get("concept", "")).strip()[:120] or "an abstract idea",
            "detail": str(c.get("detail", "")).strip()[:160],
        })
    if not cleaned:
        raise RuntimeError("LLM returned no usable cards")
    return cleaned


def rule_based_split(text: str, n_cards: int) -> list:
    """Fallback: no LLM needed. Splits on paragraphs, then sentences."""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if len(paragraphs) < n_cards:
        # Not enough paragraphs — fall back to sentence-level splitting
        sentences = re.split(r"(?<=[.!?])\s+", text.strip())
        sentences = [s.strip() for s in sentences if s.strip()]
        chunk_size = max(1, len(sentences) // n_cards)
        paragraphs = [
            " ".join(sentences[i:i + chunk_size])
            for i in range(0, len(sentences), chunk_size)
        ][:n_cards]

    cards = []
    for i, para in enumerate(paragraphs[:n_cards], start=1):
        first_sentence = re.split(r"(?<=[.!?])\s+", para)[0]
        words = first_sentence.split()
        title = " ".join(words[:4]).rstrip(".,;:") or f"Concept {i}"
        detail_words = para.split()
        detail = " ".join(detail_words[:24])
        if len(detail_words) > 24:
            detail += "..."
        concept = " ".join(words[:8]) or title
        cards.append({"title": title.title(), "concept": concept, "detail": detail})
    return cards


def split_text_into_cards(text: str, max_cards: int = 10) -> list:
    n_cards = estimate_card_count(text, max_cards)
    try:
        return llm_split(text, n_cards)
    except Exception as e:
        print(f"[info] LLM split unavailable ({e}); using rule-based splitter instead.")
        return rule_based_split(text, n_cards)


# --------------------------------------------------------------------------
# STEP 2/3: GENERATE BACKGROUND ART WITH NVIDIA NIM FLUX.1-dev
# --------------------------------------------------------------------------

def generate_flux_image(concept: str, seed: int = 0) -> Image.Image:
    if not NVIDIA_API_KEY:
        raise RuntimeError(
            "NVIDIA_API_KEY environment variable is not set. "
            "Get a key at https://build.nvidia.com and run:\n"
            "  export NVIDIA_API_KEY='nvapi-...'"
        )

    prompt = STYLE_TEMPLATE.format(concept=concept)

    payload = {
        "prompt": prompt,
        "height": IMAGE_SIZE,
        "width": IMAGE_SIZE,
        "cfg_scale": 5,
        "mode": "base",
        "samples": 1,
        "seed": seed,
        "steps": 40,
    }

    resp = requests.post(
        FLUX_URL,
        headers={
            "Authorization": f"Bearer {NVIDIA_API_KEY}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=120,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"FLUX.1-dev request failed ({resp.status_code}): {resp.text[:500]}")

    data = resp.json()

    # NVIDIA's Visual GenAI NIMs return base64 image data under an
    # 'artifacts' list; be defensive in case the exact key differs.
    b64_image = None
    if "artifacts" in data and data["artifacts"]:
        b64_image = data["artifacts"][0].get("base64")
    elif "image" in data:
        b64_image = data["image"]
    elif "data" in data and data["data"]:
        b64_image = data["data"][0].get("b64_json")

    if not b64_image:
        raise RuntimeError(f"Unexpected FLUX response shape: {json.dumps(data)[:500]}")

    image_bytes = base64.b64decode(b64_image)
    return Image.open(__import__("io").BytesIO(image_bytes)).convert("RGB")


# --------------------------------------------------------------------------
# STEP 4: COMPOSE FINAL FLASHCARD (crisp text overlay)
# --------------------------------------------------------------------------

def find_font(name_bold=True, size=48):
    for d in FONT_DIR_CANDIDATES:
        candidate = os.path.join(
            d, "DejaVuSans-Bold.ttf" if name_bold else "DejaVuSans.ttf"
        )
        if os.path.exists(candidate):
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


def wrap_text(draw, text, font, max_width):
    words = text.split()
    lines, current = [], ""
    for w in words:
        trial = f"{current} {w}".strip()
        if draw.textlength(trial, font=font) <= max_width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = w
    if current:
        lines.append(current)
    return lines


def compose_flashcard(art: Image.Image, title: str, detail: str) -> Image.Image:
    art = art.resize((CARD_W, CARD_W))  # square art on top

    canvas = Image.new("RGB", (CARD_W, CARD_H), "#FDFBF7")
    draw = ImageDraw.Draw(canvas)

    # --- Illustration area (top ~70%) ---
    art_area_h = int(CARD_H * 0.68)
    art_resized = art.resize((CARD_W, art_area_h))
    canvas.paste(art_resized, (0, 0))

    # soft rounded-card mask feel: draw a subtle divider
    draw.rectangle([0, art_area_h, CARD_W, art_area_h + 4], fill="#E8E2D6")

    # --- Title banner (overlaid on top of the art, top strip) ---
    title_font = find_font(name_bold=True, size=56)
    title_bar_h = 110
    overlay = Image.new("RGBA", (CARD_W, title_bar_h), (20, 20, 20, 160))
    canvas.paste(
        Image.alpha_composite(
            canvas.crop((0, 0, CARD_W, title_bar_h)).convert("RGBA"), overlay
        ).convert("RGB"),
        (0, 0),
    )
    draw = ImageDraw.Draw(canvas)
    tw = draw.textlength(title.upper(), font=title_font)
    draw.text(
        ((CARD_W - tw) / 2, (title_bar_h - 56) / 2 - 8),
        title.upper(),
        font=title_font,
        fill="white",
    )

    # --- Detail strip (bottom ~32%) ---
    detail_font = find_font(name_bold=False, size=34)
    detail_area_top = art_area_h + 4
    detail_area = [0, detail_area_top, CARD_W, CARD_H]
    draw.rectangle(detail_area, fill="#FDFBF7")

    lines = wrap_text(draw, detail, detail_font, CARD_W - 120)
    total_text_h = len(lines) * (detail_font.size + 12)
    y = detail_area_top + (CARD_H - detail_area_top - total_text_h) / 2
    for line in lines:
        lw = draw.textlength(line, font=detail_font)
        draw.text(((CARD_W - lw) / 2, y), line, font=detail_font, fill="#2B2B2B")
        y += detail_font.size + 12

    # subtle outer border for a "card" feel
    border = Image.new("RGB", (CARD_W + 16, CARD_H + 16), "#D8D2C4")
    border.paste(canvas, (8, 8))
    return border


# --------------------------------------------------------------------------
# MAIN
# --------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Generate flashcards from text using NVIDIA NIM FLUX.1-dev")
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--text", type=str, help="Raw text to convert into flashcards")
    src.add_argument("--file", type=str, help="Path to a .txt file with the source text")
    parser.add_argument("--max-cards", type=int, default=10, help="Maximum number of flashcards (default 10)")
    parser.add_argument("--out", type=str, default="./flashcards", help="Output directory")
    args = parser.parse_args()

    if args.file:
        text = Path(args.file).read_text(encoding="utf-8")
    else:
        text = args.text

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("[1/3] Splitting text into flashcard concepts...")
    cards = split_text_into_cards(text, max_cards=args.max_cards)
    print(f"      -> {len(cards)} flashcard(s) planned")
    for i, c in enumerate(cards, 1):
        print(f"        {i}. {c['title']}")

    for i, card in enumerate(cards, start=1):
        print(f"[2/3] Generating art for card {i}/{len(cards)}: {card['title']}")
        try:
            art = generate_flux_image(card["concept"], seed=i)
        except Exception as e:
            print(f"      ! FLUX generation failed for card {i}: {e}")
            continue

        print(f"[3/3] Composing flashcard {i}...")
        final = compose_flashcard(art, card["title"], card["detail"])
        out_path = out_dir / f"flashcard_{i:02d}.png"
        final.save(out_path)
        print(f"      -> saved {out_path}")

    print("\nDone. Flashcards saved in:", out_dir.resolve())


if __name__ == "__main__":
    main()