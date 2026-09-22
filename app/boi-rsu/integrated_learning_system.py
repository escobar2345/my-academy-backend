#!/usr/bin/env python3
"""
INTEGRATED LEARNING SYSTEM
═══════════════════════════════════════════════════════════════════════════════
Combines ai_learning_system_v4, lesson1.py, and lesson2.py into ONE unified system.

THREE POWERHOUSES WORKING TOGETHER:
  1. Deep Research Engine (Apify + Nemotron-3-Super)
  2. PDF Generation (Both FPDF & ReportLab/FLUX.1-dev)
  3. Curriculum Management (Google Gemini + Realistic Timelines)

FEATURES:
  • Research any topic → Generate complete courses
  • Multiple PDF formats (simple FPDF, illustrated with FLUX.1-dev)
  • Deepgram text-to-speech for 90-minute live classes
  • Interactive UI with contextual menus
  • Learning resources auto-discovery
  • Realistic curriculum timelines (Udemy-style)
"""

import os, sys, re, time, json, tempfile, subprocess, argparse, base64, hashlib, io
from urllib.parse import urlparse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Dict

# ═══════════════════════════════════════════════════════════════════════════════
# DEPENDENCIES AUTO-INSTALL
# ═══════════════════════════════════════════════════════════════════════════════

def install_package(pkg):
    subprocess.check_call([sys.executable, "-m", "pip", "install", pkg,
                           "--break-system-packages", "-q"])

DEPENDENCIES = [
    ("apify_client", "apify-client"),
    ("openai", "openai"),
    ("requests", "requests"),
    ("colorama", "colorama"),
    ("reportlab", "reportlab"),
    ("PIL", "pillow"),
    ("fpdf", "fpdf2"),
    ("google", "google-generativeai"),
]

for imp, pkg in DEPENDENCIES:
    try:
        __import__(imp)
    except ImportError:
        print(f"  Installing {pkg}...")
        install_package(pkg)

from apify_client import ApifyClient
from openai import OpenAI
import requests
from colorama import Fore, Style, init
init(autoreset=True)

try:
    from google import genai
except:
    pass

try:
    from roadmap_helper import fetch_roadmap
except:
    try:
        from roadmap import fetch_roadmap
    except:
        fetch_roadmap = None

try:
    from youtube import enrich_course_with_videos
except:
    enrich_course_with_videos = None

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
from fpdf import FPDF

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION & ENVIRONMENT
# ═══════════════════════════════════════════════════════════════════════════════

def load_env_file(env_path=None):
    """Load environment variables from .env files."""
    candidates = []
    if env_path:
        candidates.append(env_path)

    script_dir = os.path.dirname(os.path.abspath(__file__))
    backend_dir = os.path.abspath(os.path.join(script_dir, "..", ".."))
    candidates.extend([
        os.path.join(script_dir, ".env.local"),
        os.path.join(backend_dir, ".env.local"),
        os.path.join(backend_dir, ".env"),
        os.path.join(os.getcwd(), ".env.local"),
        os.path.join(os.getcwd(), ".env"),
    ])

    for path in candidates:
        if not path or not os.path.exists(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as fh:
                for raw_line in fh:
                    line = raw_line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if line.startswith("export "):
                        line = line[len("export "):].strip()
                    if "=" not in line:
                        continue
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip()
                    if value and value[0] in {'"', "'"} and value[-1] == value[0]:
                        value = value[1:-1]
                    os.environ.setdefault(key, value)
        except:
            continue
        break

load_env_file()

# API Keys
APIFY_TOKEN = os.environ.get("APIFY_TOKEN", "")
NVIDIA_KEY = os.environ.get("NVIDIA_API_KEY", "")
DEEPGRAM_KEY = os.environ.get("DEEPGRAM_API_KEY", "")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")

# Configuration
FAST_MODE = os.environ.get("FAST_MODE", "true").lower() in {"1", "true", "yes", "on"}
TARGET_SECTIONS = int(os.environ.get("TARGET_SECTIONS", "8" if FAST_MODE else "15"))
WORDS_PER_SECTION = int(os.environ.get("WORDS_PER_SECTION", "500" if FAST_MODE else "840"))
WORDS_PER_MINUTE = 140
DEEPGRAM_VOICE = "aura-2-thalia-en"
NVIDIA_API_URL = "https://ai.api.nvidia.com/v1/genai/black-forest-labs/flux.1-dev"
MODEL_ID = "nvidia/nemotron-3-super-120b-a12b"
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"

# Style settings for illustrated PDFs
ACCENT_COLOR = colors.HexColor("#2454A0")
ACCENT_LIGHT = colors.HexColor("#EAF1FB")
TEXT_COLOR = colors.HexColor("#1C1C1C")
DEFAULT_STYLE_SUFFIX = (
    ", clean modern educational illustration, flat design, soft lighting, "
    "vibrant but tasteful color palette, high detail, no text or labels "
    "unless requested, safe for classroom use"
)

# ═══════════════════════════════════════════════════════════════════════════════
# UI HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def banner():
    print(Fore.CYAN + """
============================================================
    INTEGRATED LEARNING SYSTEM v5
    Deep Research -> AI Course -> Voice Class -> PDF
============================================================
""")

def section(title):
    print(f"\n{Fore.YELLOW}{'='*62}")
    print(f"  {title}")
    print(f"{'='*62}{Style.RESET_ALL}\n")

def ok(msg):   print(f"{Fore.GREEN}  [OK] {msg}{Style.RESET_ALL}")
def err(msg):  print(f"{Fore.RED}  [ERROR] {msg}{Style.RESET_ALL}")
def info(msg): print(f"{Fore.CYAN}  [INFO] {msg}{Style.RESET_ALL}")
def warn(msg): print(f"{Fore.YELLOW}  [WARN] {msg}{Style.RESET_ALL}")

# ═══════════════════════════════════════════════════════════════════════════════
# AI CLIENT SETUP (Nemotron-3-Super & Google Gemini)
# ═══════════════════════════════════════════════════════════════════════════════

def setup_nvidia_ai():
    """Setup NVIDIA Nemotron-3-Super API (OpenAI-compatible)."""
    return OpenAI(base_url=NVIDIA_BASE_URL, api_key=NVIDIA_KEY)

def setup_google_ai():
    """Setup Google Gemini API."""
    if GOOGLE_API_KEY:
        try:
            genai.configure(api_key=GOOGLE_API_KEY)
            return genai.GenerativeModel("gemini-2.5-flash")
        except:
            return None
    return None

def call_nvidia_ai(client, prompt: str, max_tokens: int = 4096) -> str:
    """Call Nemotron-3-Super via NVIDIA API."""
    try:
        response = client.chat.completions.create(
            model=MODEL_ID,
            messages=[
                {"role": "system", "content": "You are an expert university-level tutor delivering live classes. Your explanations are deep, detailed, and complete. Write in a clear, warm, conversational teaching voice suitable for being read aloud. Use smooth transitions between ideas. Avoid bullet points and markdown – write full flowing paragraphs as if speaking to a student."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            top_p=1,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"[Nemotron-3-Super error: {e}]"

def call_google_ai(prompt: str) -> str:
    """Call Google Gemini API."""
    try:
        client = setup_google_ai()
        if not client:
            return ""
        response = client.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"[Gemini error: {e}]"

# ═══════════════════════════════════════════════════════════════════════════════
# DEEPGRAM TEXT-TO-SPEECH
# ═══════════════════════════════════════════════════════════════════════════════

def speak_text(text: str, muted: bool = False) -> bool:
    """Convert text to speech via Deepgram and play it."""
    if not DEEPGRAM_KEY or muted or not text.strip():
        return False

    # Split into ≤3000 char chunks
    chunks = []
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    current = ""
    for sentence in sentences:
        if len(current) + len(sentence) + 1 > 3000:
            if current:
                chunks.append(current.strip())
            current = sentence
        else:
            current = (current + " " + sentence).strip()
    if current:
        chunks.append(current.strip())

    headers = {
        "Authorization": f"Token {DEEPGRAM_KEY}",
        "Content-Type": "application/json",
    }

    played_any = False
    for chunk in chunks:
        try:
            response = requests.post(
                "https://api.deepgram.com/v1/speak",
                params={"model": DEEPGRAM_VOICE},
                headers=headers,
                json={"text": chunk},
                timeout=30,
            )
            if response.status_code != 200:
                warn(f"Deepgram error {response.status_code}")
                continue

            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
                tmp.write(response.content)
                tmp_path = tmp.name

            players = [
                f"mpg123 -q '{tmp_path}'",
                f"ffplay -nodisp -autoexit -loglevel quiet '{tmp_path}'",
            ]
            for cmd in players:
                tool = cmd.split()[0]
                if subprocess.run(f"which {tool}", shell=True, capture_output=True).returncode == 0:
                    subprocess.run(cmd, shell=True)
                    played_any = True
                    break

            try:
                os.unlink(tmp_path)
            except:
                pass

        except Exception as e:
            warn(f"Deepgram TTS failed: {e}")

    return played_any

# ═══════════════════════════════════════════════════════════════════════════════
# DEEP RESEARCH ENGINE (Apify-based)
# ═══════════════════════════════════════════════════════════════════════════════

RESEARCH_SOURCES = [
    ("Official Docs / Fundamentals", "{topic} complete guide tutorial documentation"),
    ("Beginner to Advanced", "{topic} beginner to advanced comprehensive"),
    ("Core Concepts Deep Dive", "{topic} core concepts explained in depth"),
    ("Practical Examples", "{topic} practical examples real world applications"),
    ("Best Practices", "{topic} best practices tips common mistakes"),
]

def _scrape_urls_apify(urls: list[str]) -> list[str]:
    """Use Apify web-scraper to extract full text from URLs."""
    if not urls or not APIFY_TOKEN:
        return []

    apify = ApifyClient(token=APIFY_TOKEN)
    page_function = """
async function pageFunction(context) {
    const { log } = context;
    await context.waitFor(4000);
    ['nav','footer','header','aside','[class*="sidebar"]',
     '[class*="advertisement"]','[class*="cookie"]',
     '[class*="popup"]','[class*="modal"]','script','style'
    ].forEach(sel => {
        document.querySelectorAll(sel).forEach(el => el.remove());
    });
    const els = document.querySelectorAll(
        'article, main, .content, .post, .entry, p, h1, h2, h3, h4, h5, li, pre, blockquote'
    );
    const seen = new Set();
    const blocks = [];
    for (const el of els) {
        const text = (el.innerText || el.textContent || '').trim();
        if (text.length > 40 && !seen.has(text)) {
            seen.add(text);
            blocks.push(text);
        }
    }
    if (blocks.length === 0) {
        const body = (document.body?.innerText || '').substring(0, 15000);
        blocks.push(body);
    }
    const fullText = blocks.join('\\n\\n').substring(0, 15000);
    return { url: window.location.href, title: document.title, text: fullText };
}
"""
    try:
        run = apify.actor("apify/web-scraper").call(
            run_input={
                "startUrls": [{"url": u} for u in urls],
                "pageFunction": page_function,
                "maxRequestsPerCrawl": len(urls),
                "maxConcurrency": 3,
                "waitUntil": ["domcontentloaded"],
                "proxyConfiguration": {"useApifyProxy": True},
            },
            timeout_secs=240,
        )
        if not run:
            return []

        items = list(apify.dataset(run["defaultDatasetId"]).iterate_items())
        result = []
        for item in items:
            text = item.get("text", "").strip()
            title = item.get("title", "").strip()
            url = item.get("url", "")
            if text and len(text) > 100:
                result.append(f"SOURCE: {title}\nURL: {url}\n\n{text}")
        return result
    except Exception as e:
        warn(f"Apify scrape error: {e}")
        return []

def _search_and_get_urls(query: str, n: int = 3) -> list[str]:
    """Use Apify Google Search to find top N URLs."""
    if not APIFY_TOKEN:
        return []

    apify = ApifyClient(token=APIFY_TOKEN)
    try:
        run = apify.actor("apify/google-search-scraper").call(
            run_input={
                "queries": query,
                "maxPagesPerQuery": 1,
                "resultsPerPage": 10,
                "languageCode": "en",
                "countryCode": "us",
            },
            timeout_secs=120,
        )
        if not run:
            return []

        items = list(apify.dataset(run["defaultDatasetId"]).iterate_items())
        urls = []
        skip = ["youtube.com", "youtu.be", "twitter.com", "facebook.com",
                "instagram.com", "tiktok.com", "reddit.com", "quora.com"]

        for item in items:
            for r in item.get("organicResults", []):
                url = r.get("url", "").strip()
                if not url or any(url.lower().endswith(ext) for ext in [".jpg", ".png", ".gif", ".pdf", ".mp4"]):
                    continue
                if any(s in url.lower() for s in skip):
                    continue
                if url not in urls:
                    urls.append(url)
                if len(urls) >= n:
                    break
            if len(urls) >= n:
                break
        return urls
    except Exception as e:
        warn(f"Search error: {e}")
        return []

def deep_research(topic: str, client) -> str:
    """Full deep-research pipeline: search → scrape → synthesize."""
    section("🔬 PHASE 1 – DEEP INTERNET RESEARCH")
    info(f"Researching '{topic}'...")
    info(f"Running {len(RESEARCH_SOURCES)} targeted searches...")

    all_urls = []
    seen_urls = set()

    for label, query_template in RESEARCH_SOURCES[:3 if FAST_MODE else len(RESEARCH_SOURCES)]:
        query = query_template.replace("{topic}", topic)
        info(f"  Searching: {label}...")
        urls = _search_and_get_urls(query, n=2 if FAST_MODE else 3)
        for u in urls:
            clean = u.split("?")[0].rstrip("/")
            if clean not in seen_urls:
                seen_urls.add(clean)
                all_urls.append(u)

    ok(f"Found {len(all_urls)} unique sources")

    section("📖 PHASE 2 – SCRAPING ALL SOURCES")
    info(f"Apify reading {len(all_urls)} web pages...")
    raw_texts = _scrape_urls_apify(all_urls)
    ok(f"Successfully scraped {len(raw_texts)} sources")

    if not raw_texts:
        warn("No content scraped – using AI knowledge base only")
        return f"TOPIC: {topic}\n\nNo external sources. Use your full knowledge base."

    section("🧠 PHASE 3 – SYNTHESIZING MASTER NOTES")
    combined = f"RESEARCH TOPIC: {topic}\n\n" + "\n\n─".join(raw_texts)
    if len(combined) > 60000:
        combined = combined[:60000] + "\n\n[Research truncated]"

    prompt = f"""You have access to extensive research on: {topic}

RESEARCH POOL:
{combined[:10000]}

Now synthesize everything into ONE comprehensive master knowledge document about {topic}.
Include:
1. Core concept definition
2. Historical context and evolution
3. Fundamental principles
4. Real-world applications
5. Career/practical implications
6. Key terminology
7. Common misconceptions
8. Current trends

Write complete, flowing paragraphs. Be thorough. This is the foundation for a complete course.
"""

    master_notes = call_nvidia_ai(client, prompt, max_tokens=4000)
    ok("Master notes synthesized by Nemotron-3-Super")
    return master_notes

# ═══════════════════════════════════════════════════════════════════════════════
# COURSE GENERATION (Nemotron-3-Super)
# ═══════════════════════════════════════════════════════════════════════════════

def generate_course_sections(client, topic: str, master_notes: str) -> list[dict]:
    """Generate structured course sections."""
    section("📚 PHASE 4 – STRUCTURING COURSE OUTLINE")

    prompt = f"""Based on these master notes about {topic}:

{master_notes[:5000]}

Generate a structured course outline with {TARGET_SECTIONS} sections.
Each section should:
- Have a clear title and learning objectives
- Build on previous sections
- Be achievable in ~{WORDS_PER_SECTION} words (~{round(WORDS_PER_SECTION/WORDS_PER_MINUTE)} minutes)
- Include 1 key concept students must understand

Return ONLY valid JSON with this structure:
{{
  "sections": [
    {{
      "title": "Section Title",
      "objectives": ["objective 1", "objective 2"],
      "key_concept": "The ONE thing students must understand",
      "duration_minutes": 5
    }}
  ]
}}
"""

    response = call_nvidia_ai(client, prompt, max_tokens=2000)
    try:
        data = json.loads(response)
        sections = data.get("sections", [])
        ok(f"Generated {len(sections)} course sections")
        return sections
    except:
        warn("Failed to parse sections, using defaults")
        return [{"title": topic, "objectives": ["Learn the basics"], "key_concept": topic, "duration_minutes": 90}]

def generate_section_content(client, topic: str, section: dict, context: str = "") -> str:
    """Generate detailed content for one section."""
    prompt = f"""Write detailed content for this section of a {WORDS_PER_SECTION}-word lesson about {topic}.

Section: {section.get('title', '')}
Key concept: {section.get('key_concept', '')}
Objectives: {', '.join(section.get('objectives', []))}

GUIDELINES:
• Write exactly {WORDS_PER_SECTION} words (approx {round(WORDS_PER_SECTION/WORDS_PER_MINUTE)} min at 140 wpm)
• Explain deeply, with examples
• Use Nigerian context (Jumia, Paystack, Lagos, local references)
• Conversational tone suitable for being read aloud
• Include 1-2 practical examples
• No bullet points – write flowing paragraphs

Context from previous sections: {context[:500] if context else 'First section'}

Write the section content now:
"""

    return call_nvidia_ai(client, prompt, max_tokens=2000)

def generate_full_course(client, topic: str, master_notes: str) -> dict:
    """Generate complete course structure and content."""
    sections = generate_course_sections(client, topic, master_notes)
    
    section("✍️ PHASE 5 – GENERATING DETAILED CONTENT")
    course_content = []
    context = ""

    for i, sec in enumerate(sections, 1):
        info(f"Generating section {i}/{len(sections)}: {sec.get('title', '')}...")
        content = generate_section_content(client, topic, sec, context)
        course_content.append({
            **sec,
            "content": content
        })
        context = content  # Use previous content as context
    
    ok(f"Course generation complete: {len(course_content)} sections")
    return {
        "topic": topic,
        "title": f"Complete {topic} Course",
        "master_notes": master_notes,
        "sections": course_content
    }

# ═══════════════════════════════════════════════════════════════════════════════
# PDF GENERATION - Option 1: Simple FPDF
# ═══════════════════════════════════════════════════════════════════════════════

class SimpleCoursePDF(FPDF):
    """Simple PDF generator using FPDF2."""
    def __init__(self, course_title: str):
        super().__init__()
        self.course_title = course_title
        # Use built-in fonts (no TTF file needed)
        # Custom fonts can be added later if needed

    def header(self):
        self.set_fill_color(10, 50, 100)
        self.rect(0, 0, 210, 20, 'F')
        self.set_text_color(255, 255, 255)
        self.set_font("Helvetica", "B", 11)
        self.set_y(6)
        self.cell(0, 8, "INTEGRATED LEARNING SYSTEM", align="C")
        self.ln(20)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f"Page {self.page_no()}", align="C")

    def add_title(self, title: str):
        self.set_font("Helvetica", "B", 18)
        self.multi_cell(0, 10, title)
        self.ln(10)

    def add_section(self, title: str, content: str):
        self.set_font("Helvetica", "B", 14)
        self.multi_cell(0, 8, title)
        self.ln(5)
        self.set_font("Helvetica", "", 11)
        self.multi_cell(0, 7, content)
        self.ln(10)

def generate_simple_pdf(course: dict, output_path: str):
    """Generate a simple PDF course using FPDF."""
    pdf = SimpleCoursePDF(course["title"])
    pdf.add_page()
    pdf.add_title(course["title"])
    pdf.add_section("Topic", course["topic"])
    
    for i, section in enumerate(course["sections"], 1):
        pdf.add_section(
            f"{i}. {section.get('title', '')}",
            section.get('content', '')[:500] + "..."
        )
    
    pdf.output(output_path)
    return output_path

# ═══════════════════════════════════════════════════════════════════════════════
# PDF GENERATION - Option 2: Illustrated with FLUX.1-dev (ReportLab)
# ═══════════════════════════════════════════════════════════════════════════════

class FluxClient:
    """NVIDIA FLUX.1-dev image generator."""
    def __init__(self, api_key: str, cache_dir: Path, steps: int = 40, cfg_scale: float = 4.0):
        if not api_key:
            raise RuntimeError("No NVIDIA_API_KEY found")
        self.api_key = api_key
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.steps = steps
        self.cfg_scale = cfg_scale

    def _cache_path(self, prompt: str, seed: int) -> Path:
        key = hashlib.sha256(f"{prompt}|{seed}".encode()).hexdigest()[:24]
        return self.cache_dir / f"{key}.png"

    def generate(self, prompt: str, seed: int = 0, retries: int = 3) -> Optional[Path]:
        """Generate image from prompt."""
        cache_file = self._cache_path(prompt, seed)
        if cache_file.exists():
            return cache_file

        payload = {
            "prompt": prompt[:1000],
            "mode": "base",
            "width": 1024,
            "height": 1024,
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

        for attempt in range(1, retries + 1):
            try:
                resp = requests.post(NVIDIA_API_URL, headers=headers, json=payload, timeout=120)
                if resp.status_code != 200:
                    time.sleep(2 ** attempt)
                    continue
                
                data = resp.json()
                if "image" in data:
                    b64 = data["image"].split(",")[-1] if "," in data["image"] else data["image"]
                    img_bytes = base64.b64decode(b64)
                    Image.open(io.BytesIO(img_bytes)).convert("RGB").save(cache_file, "PNG")
                    return cache_file
            except Exception as e:
                warn(f"Image generation attempt {attempt} failed: {e}")
                time.sleep(2 ** attempt)

        return None

def generate_illustrated_pdf(course: dict, output_path: str, flux_client: Optional[FluxClient] = None):
    """Generate illustrated PDF using ReportLab + FLUX.1-dev images."""
    if not flux_client:
        info("Skipping illustrations (no NVIDIA_API_KEY)")
        return generate_simple_pdf(course, output_path)

    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(str(output_path), pagesize=A4, title=course["title"])
    story = []

    # Title page
    story.append(Paragraph(course["title"], styles["Heading1"]))
    story.append(Spacer(1, 0.5 * cm))
    story.append(Paragraph(f"Topic: {course['topic']}", styles["Normal"]))
    story.append(PageBreak())

    # Sections
    for i, section in enumerate(course["sections"], 1):
        story.append(Paragraph(f"{i}. {section.get('title', '')}", styles["Heading2"]))
        story.append(Spacer(1, 0.3 * cm))
        
        # Generate and insert illustration
        if flux_client:
            img_path = flux_client.generate(
                f"Educational illustration for: {section.get('title', '')}" + DEFAULT_STYLE_SUFFIX,
                seed=i
            )
            if img_path:
                story.append(RLImage(str(img_path), width=10 * cm, height=10 * cm))
                story.append(Spacer(1, 0.3 * cm))

        # Add content
        content_text = section.get('content', '')[:1000]
        story.append(Paragraph(content_text, styles["Normal"]))
        story.append(Spacer(1, 0.5 * cm))

    doc.build(story)
    return output_path

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN WORKFLOW
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Integrated Learning System")
    parser.add_argument("topic", nargs="?", help="Topic to create a course about")
    parser.add_argument("--output-dir", default="courses", help="Output directory")
    parser.add_argument("--pdf-style", choices=["simple", "illustrated", "both"], default="both", help="PDF style")
    parser.add_argument("--no-voice", action="store_true", help="Skip text-to-speech")
    parser.add_argument("--cache-dir", default="cache", help="Cache directory for images")
    args = parser.parse_args()

    banner()

    if not args.topic:
        print(f"\n{Fore.CYAN}Usage:{Style.RESET_ALL}")
        print(f"  python integrated_learning_system.py 'Your Topic' --output-dir courses --pdf-style both\n")
        print(f"Examples:")
        print(f"  python integrated_learning_system.py 'Machine Learning Basics'")
        print(f"  python integrated_learning_system.py 'Web Development with React' --pdf-style illustrated")
        return

    section(f"🚀 STARTING: {args.topic}")

    # Initialize clients
    try:
        nvidia_client = setup_nvidia_ai() if NVIDIA_KEY else None
        google_client = setup_google_ai()
    except:
        nvidia_client = None
        google_client = None

    if not nvidia_client and not google_client:
        err("No AI clients available! Set NVIDIA_API_KEY or GOOGLE_API_KEY")
        return

    client = nvidia_client or google_client

    try:
        # Phase 1-3: Deep research & synthesis
        master_notes = deep_research(args.topic, client)

        # Phase 4-5: Course generation
        course = generate_full_course(client, args.topic, master_notes)

        # Phase 6: PDF generation
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        safe_name = re.sub(r"[^A-Za-z0-9_-]+", "_", args.topic.lower())

        if args.pdf_style in ["simple", "both"]:
            simple_pdf = output_dir / f"{safe_name}_simple.pdf"
            generate_simple_pdf(course, str(simple_pdf))
            ok(f"Simple PDF: {simple_pdf}")

        if args.pdf_style in ["illustrated", "both"]:
            if NVIDIA_KEY:
                flux = FluxClient(api_key=NVIDIA_KEY, cache_dir=Path(args.cache_dir))
                illustrated_pdf = output_dir / f"{safe_name}_illustrated.pdf"
                generate_illustrated_pdf(course, str(illustrated_pdf), flux)
                ok(f"Illustrated PDF: {illustrated_pdf}")
            else:
                warn("NVIDIA_API_KEY not set – skipping illustrated PDF")

        # Phase 7: Text-to-speech
        if not args.no_voice and DEEPGRAM_KEY:
            section("🎙️ PHASE 6 – TEXT-TO-SPEECH")
            all_content = "\n\n".join([s.get('content', '') for s in course['sections']])
            if speak_text(all_content):
                ok("Voice narration complete")
            else:
                warn("Text-to-speech playback skipped")

        ok(f"\n✨ COURSE COMPLETE: {args.topic}\n")
        print(f"Output: {output_dir}\n")

    except Exception as e:
        err(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
