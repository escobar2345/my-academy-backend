#!/usr/bin/env python3
"""
AI-Powered Learning System v4
â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
1. Student types a topic
2. Apify deep-researches the internet (10+ sources, full page text)
3. The AI synthesizes everything into one complete structured course
   sized for exactly 1hr 30min of Deepgram voice narration
4. Class Mode plays each lesson section with the AI explaining
   and Deepgram Aura-2 voice reading it aloud â€” smooth for 90 minutes
"""

import os, sys, re, time, json, tempfile, subprocess
from datetime import date, datetime, timedelta
from urllib.parse import urlparse

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

# â”€â”€ Auto-install dependencies â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def install(pkg):
    subprocess.check_call([sys.executable, "-m", "pip", "install", pkg,
                           "--break-system-packages", "-q"])

DEPS = [
    ("apify_client", "apify-client"),
    ("openai",       "openai"),
    ("requests",     "requests"),
    ("colorama",     "colorama"),
]
for imp, pkg in DEPS:
    try:
        __import__(imp)
    except ImportError:
        print(f"  Installing {pkg}...")
        install(pkg)

from apify_client import ApifyClient
from openai import OpenAI
import requests
from colorama import Fore, Style, init
init(autoreset=True)
try:
    from roadmap_helper import fetch_roadmap
except ModuleNotFoundError:
    from roadmap import fetch_roadmap

try:
    from youtube import enrich_course_with_videos
except Exception:
    enrich_course_with_videos = None

# â”€â”€ Load local environment file â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def load_env_file(env_path=None):
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
        break

load_env_file()

# â”€â”€ API Keys â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
APIFY_TOKEN   = os.environ.get("APIFY_TOKEN",      "")
NVIDIA_KEY    = os.environ.get("NVIDIA_API_KEY",   "")
DEEPGRAM_KEY  = os.environ.get("DEEPGRAM_API_KEY", "")
APIFY_SEARCH_ACTOR = os.environ.get("APIFY_SEARCH_ACTOR", "apify/google-search-scraper")

# â”€â”€ Class timing constants â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Deepgram Aura-2 speaks at ~140 words/minute (natural teaching pace)
# By default we use a lighter, faster generation mode to reduce wait time.
FAST_MODE = os.environ.get("FAST_MODE", "true").lower() in {"1", "true", "yes", "on"}

TARGET_SECTIONS      = int(os.environ.get("TARGET_SECTIONS", "8" if FAST_MODE else "15"))
WORDS_PER_SECTION    = int(os.environ.get("WORDS_PER_SECTION", "500" if FAST_MODE else "840"))
WORDS_PER_MINUTE     = 140      # Deepgram Aura-2 natural speaking pace
TOTAL_CLASS_MINUTES  = int(os.environ.get("TOTAL_CLASS_MINUTES", str(round(TARGET_SECTIONS * WORDS_PER_SECTION / WORDS_PER_MINUTE))))

# â”€â”€ UI Helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def banner():
    print(Fore.CYAN + """
â•”â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•—
â•‘          ðŸŽ“  AI POWERED LEARNING SYSTEM  v4  ðŸŽ“             â•‘
â•‘  Deep Research â†’ Nemotron Course â†’ Deepgram 90min Class     â•‘
â•šâ•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
""")

def section(title):
    print(f"\n{Fore.YELLOW}{'â”€'*62}")
    print(f"  {title}")
    print(f"{'â”€'*62}{Style.RESET_ALL}\n")

def ok(msg):   print(f"{Fore.GREEN}  âœ… {msg}{Style.RESET_ALL}")
def err(msg):  print(f"{Fore.RED}  âŒ {msg}{Style.RESET_ALL}")
def info(msg): print(f"{Fore.CYAN}  â„¹ï¸  {msg}{Style.RESET_ALL}")
def warn(msg): print(f"{Fore.YELLOW}  âš ï¸  {msg}{Style.RESET_ALL}")


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# NEMOTRON-3-SUPER AI SETUP  (NVIDIA API â€” OpenAI-compatible)
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
MODEL_ID        = "nvidia/nemotron-3-super-120b-a12b"
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"

TUTOR_INSTRUCTION = (
    "You are an expert university-level tutor delivering a live spoken class. "
    "Your explanations are deep, detailed, and complete â€” you never skip anything. "
    "Write in a clear, warm, conversational teaching voice suitable for being "
    "read aloud. Use smooth transitions between ideas. Avoid bullet points and "
    "markdown â€” write full flowing paragraphs as if speaking to a student. "
    "Be thorough: a student should finish each section truly understanding the topic."
)

def setup_ai():
    # A hung NVIDIA request used to block a worker for ~30 min (SDK default
    # 600s timeout + 2 retries). Bound every call: one attempt up to
    # NVIDIA_TIMEOUT_SECONDS, at most one SDK retry; callers do their own
    # higher-level retries (e.g. per-week retry in api_server._ai_daily_plan).
    return OpenAI(
        base_url=NVIDIA_BASE_URL,
        api_key=NVIDIA_KEY,
        timeout=float(os.environ.get("NVIDIA_TIMEOUT_SECONDS", "180")),
        max_retries=1,
    )

def ai(client, prompt: str, max_tokens: int = 4096) -> str:
    """Call Nemotron-3-Super via NVIDIA API and return response text.

    Thinking is disabled and the timeout scales with the ask: nemotron burns
    the SAME max_tokens budget on hidden reasoning_content first (books came
    back as empty skeletons), and a 16k-token book needs far more than the
    client's default 180s to stream.
    """
    try:
        response = client.chat.completions.create(
            model=MODEL_ID,
            messages=[
                {"role": "system", "content": TUTOR_INSTRUCTION},
                {"role": "user",   "content": prompt},
            ],
            temperature=0.7,
            top_p=1,
            max_tokens=max_tokens,
            timeout=max(180.0, float(max_tokens) / 25.0),
            extra_body=({"chat_template_kwargs": {"enable_thinking": False}}
                        if "nemotron" in str(MODEL_ID).lower() else None),
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"[Nemotron-3-Super error: {e}]"


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# DEEPGRAM TEXT-TO-SPEECH
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
DEEPGRAM_VOICE = "aura-2-thalia-en"   # warm, clear professional teaching voice

def _ensure_audio_player():
    """Install mpg123 if not present â€” needed to play Deepgram MP3 output."""
    if subprocess.run("which mpg123", shell=True, capture_output=True).returncode == 0:
        return True
    info("Installing mpg123 audio player...")
    subprocess.run(
        "sudo apt-get install -y mpg123 2>/dev/null || apt-get install -y mpg123 2>/dev/null",
        shell=True, capture_output=True
    )
    return subprocess.run("which mpg123", shell=True, capture_output=True).returncode == 0

def speak_text(text: str, muted: bool = False) -> bool:
    """
    Convert text to speech via Deepgram Aura-2 and play it.
    Splits long text into chunks â‰¤ 3000 chars so Deepgram never hits
    its character limit â€” ensuring smooth uninterrupted 90min narration.
    Returns True if audio played successfully.
    """
    if not DEEPGRAM_KEY or muted or not text.strip():
        return False

    # Split text into â‰¤3000 char chunks at sentence boundaries
    chunks = []
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    current   = ""
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
        "Content-Type":  "application/json",
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
                warn(f"Deepgram error {response.status_code}: {response.text[:100]}")
                continue

            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
                tmp.write(response.content)
                tmp_path = tmp.name

            # Play with mpg123 (WSL/Ubuntu compatible)
            players = [
                f"mpg123 -q '{tmp_path}'",
                f"ffplay -nodisp -autoexit -loglevel quiet '{tmp_path}'",
            ]
            for cmd in players:
                tool = cmd.split()[0]
                if subprocess.run(f"which {tool}", shell=True,
                                  capture_output=True).returncode == 0:
                    subprocess.run(cmd, shell=True)
                    played_any = True
                    break

            try: os.unlink(tmp_path)
            except: pass

        except Exception as e:
            warn(f"Deepgram TTS chunk failed: {e}")

    return played_any


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# STEP 1 â€” DEEP INTERNET RESEARCH via Apify
# Scrapes 10+ high-quality sources for maximum raw knowledge on the topic
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
RESEARCH_SOURCES = [
    # (label, google query)  â€” diverse angles to get maximum coverage
    ("Official Docs / Fundamentals",   "{topic} complete guide tutorial documentation"),
    ("Beginner to Advanced",           "{topic} beginner to advanced comprehensive"),
    ("Core Concepts Deep Dive",        "{topic} core concepts explained in depth"),
    ("Practical Examples",             "{topic} practical examples real world applications"),
    ("Common Mistakes & Best Practices","{topic} best practices tips common mistakes"),
]

RESEARCH_QUERY_COUNT = int(os.environ.get("RESEARCH_QUERY_COUNT", "3" if FAST_MODE else "5"))
RESEARCH_RESULTS_PER_QUERY = int(os.environ.get("RESEARCH_RESULTS_PER_QUERY", "2" if FAST_MODE else "3"))
MASTER_NOTES_MAX_TOKENS = int(os.environ.get("MASTER_NOTES_MAX_TOKENS", "3500" if FAST_MODE else "8000"))
SECTION_CONTENT_MAX_TOKENS = int(os.environ.get("SECTION_CONTENT_MAX_TOKENS", "1200" if FAST_MODE else "2000"))
LEARNING_RESOURCE_RESULTS = int(os.environ.get("LEARNING_RESOURCE_RESULTS", "6"))
RESEARCH_SOURCES = RESEARCH_SOURCES[:RESEARCH_QUERY_COUNT]

def _scrape_urls_apify(urls: list[str]) -> list[str]:
    """
    Use Apify web-scraper to extract full text from a list of URLs.
    Returns list of raw text strings (one per URL successfully scraped).
    """
    if not urls:
        return []

    apify = ApifyClient(token=APIFY_TOKEN)

    page_function = """
async function pageFunction(context) {
    const { log } = context;
    await context.waitFor(4000);

    // Remove nav, footer, sidebar, ads â€” keep only main content
    ['nav','footer','header','aside','[class*="sidebar"]',
     '[class*="advertisement"]','[class*="cookie"]',
     '[class*="popup"]','[class*="modal"]','script','style'
    ].forEach(sel => {
        document.querySelectorAll(sel).forEach(el => el.remove());
    });

    // Grab all meaningful text
    const els = document.querySelectorAll(
        'article, main, .content, .post, .entry, ' +
        'p, h1, h2, h3, h4, h5, li, pre, blockquote'
    );

    const seen   = new Set();
    const blocks = [];

    for (const el of els) {
        const text = (el.innerText || el.textContent || '').trim();
        if (text.length > 40 && !seen.has(text)) {
            seen.add(text);
            blocks.push(text);
        }
    }

    // Fallback
    if (blocks.length === 0) {
        const body = (document.body?.innerText || '').substring(0, 15000);
        blocks.push(body);
    }

    const fullText = blocks.join('\\n\\n').substring(0, 15000);
    log.info('Scraped ' + blocks.length + ' blocks, ' + fullText.length + ' chars from ' + window.location.href);
    return { url: window.location.href, title: document.title, text: fullText };
}
"""
    try:
        run = apify.actor("apify/web-scraper").call(
            run_input={
                "startUrls":           [{"url": u} for u in urls],
                "pageFunction":        page_function,
                "maxRequestsPerCrawl": len(urls),
                "maxConcurrency":      3,
                "waitUntil":           ["domcontentloaded"],
                "proxyConfiguration":  {"useApifyProxy": True},
            },
            timeout_secs=240,
        )
        if not run:
            return []

        items  = list(apify.dataset(run["defaultDatasetId"]).iterate_items())
        result = []
        for item in items:
            text  = item.get("text",  "").strip()
            title = item.get("title", "").strip()
            url   = item.get("url",   "")
            if text and len(text) > 100:
                result.append(f"SOURCE: {title}\nURL: {url}\n\n{text}")
        return result

    except Exception as e:
        warn(f"Apify scrape error: {e}")
        return []


def _search_and_get_urls(query: str, n: int = 3) -> list[str]:
    """
    Use Apify Google Search to find the top N URLs for a query.
    Returns clean URL list (no images, no PDFs, no social media noise).
    """
    apify = ApifyClient(token=APIFY_TOKEN)
    try:
        run = apify.actor("apify/google-search-scraper").call(
            run_input={
                "queries":          query,
                "maxPagesPerQuery": 1,
                "resultsPerPage":   10,
                "languageCode":     "en",
                "countryCode":      "us",
            },
            timeout_secs=120,
        )
        if not run:
            return []

        items = list(apify.dataset(run["defaultDatasetId"]).iterate_items())
        urls  = []
        skip  = ["youtube.com", "youtu.be", "twitter.com", "facebook.com",
                 "instagram.com", "tiktok.com", "reddit.com", "quora.com",
                 "slideshare.net", "pinterest.com"]

        for item in items:
            for r in item.get("organicResults", []):
                url = r.get("url", "").strip()
                if not url:
                    continue
                if any(url.lower().endswith(ext)
                       for ext in [".jpg",".png",".gif",".pdf",".mp4"]):
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
        warn(f"Search error for '{query}': {e}")
        return []


# Student learning resource discovery
RESOURCE_SEARCH_TEMPLATES = [
    "{query} official documentation tutorial for students",
    "{query} beginner friendly course exercises examples",
    "{query} interactive practice lesson",
    "{query} free university course notes",
]

RESOURCE_AUTHORITY_DOMAINS = {
    "docs.python.org", "developer.mozilla.org", "learn.microsoft.com",
    "w3schools.com", "freecodecamp.org", "khanacademy.org", "coursera.org",
    "edx.org", "ocw.mit.edu", "cs50.harvard.edu", "roadmap.sh",
}

RESOURCE_LOW_VALUE_DOMAINS = {
    "pinterest.com", "facebook.com", "instagram.com", "tiktok.com",
    "twitter.com", "x.com", "reddit.com", "quora.com",
}


def _domain_from_url(url: str) -> str:
    try:
        host = urlparse(url).netloc.lower()
    except Exception:
        return ""
    return host[4:] if host.startswith("www.") else host


def _resource_score(result: dict, topic: str, section_title: str = "") -> float:
    title = (result.get("title") or "").lower()
    content = (result.get("content") or result.get("snippet") or "").lower()
    url = result.get("url") or ""
    domain = _domain_from_url(url)
    haystack = f"{title} {content} {domain}"
    topic_terms = [w for w in re.findall(r"[a-z0-9+#.-]{3,}", f"{topic} {section_title}".lower())]

    score = 0.0
    for term in dict.fromkeys(topic_terms):
        if term in haystack:
            score += 2.0
    if any(domain == d or domain.endswith("." + d) for d in RESOURCE_AUTHORITY_DOMAINS):
        score += 5.0
    if any(word in haystack for word in ["official", "documentation", "tutorial", "course", "lesson", "guide", "exercise", "practice", "examples"]):
        score += 3.0
    if any(word in haystack for word in ["beginner", "students", "learn", "introduction", "fundamentals"]):
        score += 2.0
    if any(domain == d or domain.endswith("." + d) for d in RESOURCE_LOW_VALUE_DOMAINS):
        score -= 6.0
    if any(bad in haystack for bad in ["meme", "reaction", "shorts", "trailer", "news"]):
        score -= 3.0
    return score


def _tavily_resource_search(query: str, max_results: int = 8) -> list[dict]:
    if not APIFY_TOKEN:
        return []
    try:
        client = ApifyClient(APIFY_TOKEN)
        run = client.actor(APIFY_SEARCH_ACTOR).call(run_input={"queries": query, "maxPagesPerQuery": 1})
        return list(client.dataset(run["defaultDatasetId"]).iterate_items())[:max_results]
    except Exception as e:
        warn(f"Apify resource search failed: {e}")
        return []


def find_learning_resources(topic: str, section_title: str = "", student_level: str = "beginner", limit: int = LEARNING_RESOURCE_RESULTS) -> list[dict]:
    base_query = " ".join(p for p in [topic, section_title, f"for {student_level} students" if student_level else ""] if p).strip()
    seen = set()
    ranked = []

    for template in RESOURCE_SEARCH_TEMPLATES:
        query = template.format(query=base_query)
        info(f"Searching learning resources: {query[:70]}...")
        for item in _tavily_resource_search(query, max_results=max(limit * 2, 8)):
            url = (item.get("url") or "").strip()
            if not url:
                continue
            clean = url.split("?")[0].rstrip("/")
            domain = _domain_from_url(clean)
            if clean in seen or any(domain == d or domain.endswith("." + d) for d in RESOURCE_LOW_VALUE_DOMAINS):
                continue
            seen.add(clean)
            ranked.append({
                "title": (item.get("title") or domain or "Learning resource").strip(),
                "url": url,
                "summary": (item.get("content") or item.get("snippet") or "").strip(),
                "domain": domain,
                "score": _resource_score(item, topic, section_title),
            })

    ranked.sort(key=lambda r: r["score"], reverse=True)
    return ranked[:limit]


def explain_learning_resources(client, topic: str, section_title: str, resources: list[dict]) -> str:
    if not resources:
        if APIFY_TOKEN:
            return "No strong internet learning resources were found for this section. Try a more specific topic or check your search/API configuration."
        return "APIFY_TOKEN is not set, so live internet resource search is disabled. Add APIFY_TOKEN to backend/.env.local to enable resource discovery."

    resource_lines = "\n".join(
        f"{i}. {r['title']} ({r['domain']}) - {r['url']}\nSummary: {r['summary'][:400]}"
        for i, r in enumerate(resources, 1)
    )
    prompt = f"""
A student is learning this course topic: {topic}
Current section: {section_title or 'Full course'}

Here are internet learning resources found for the student:
{resource_lines}

Rank these resources for the student. For each one, explain in one short paragraph why it is useful, what type of learner it helps, and the best way to use it after the lesson. Keep the URLs visible.
"""
    return ai(client, prompt, max_tokens=1200)


def show_learning_resources(client, topic: str, section_title: str = "", student_level: str = "beginner"):
    section("GOD MODE INTERNET LEARNING RESOURCES")
    resources = find_learning_resources(topic, section_title, student_level=student_level)
    explanation = explain_learning_resources(client, topic, section_title, resources)
    print(f"\n{explanation}\n")
    if resources:
        print(f"{Fore.CYAN}Direct links:{Style.RESET_ALL}")
        for i, resource in enumerate(resources, 1):
            print(f"  [{i}] {resource['title']} - {resource['url']}")

def deep_research(topic: str, client) -> str:
    """
    Full deep-research pipeline:
    1. Run 5 targeted Google searches on the topic (different angles)
    2. Collect top 3 URLs from each search = up to 15 URLs total
    3. Apify scrapes full text from all URLs simultaneously
    4. Nemotron-3-Super reads all raw content and distils it into one
       comprehensive research document (~8,000 words)
    Returns: raw_research_text (str)
    """
    section("ðŸ”¬ PHASE 1 â€” DEEP INTERNET RESEARCH")
    if FAST_MODE:
        info("Fast mode enabled: using fewer sources and shorter synthesis to reduce wait time.")
    info(f"Scouting the internet for everything about '{topic}'...")
    info(f"Running {len(RESEARCH_SOURCES)} targeted searches across different learning angles...")

    all_urls = []
    seen_urls = set()

    for label, query_template in RESEARCH_SOURCES:
        query = query_template.replace("{topic}", topic)
        info(f"  Searching: {label}...")
        urls = _search_and_get_urls(query, n=RESEARCH_RESULTS_PER_QUERY)
        for u in urls:
            clean = u.split("?")[0].rstrip("/")
            if clean not in seen_urls:
                seen_urls.add(clean)
                all_urls.append(u)

    ok(f"Found {len(all_urls)} unique high-quality sources to research")

    # â”€â”€ Scrape all URLs in parallel via Apify â”€â”€
    section("ðŸ“¡ PHASE 2 â€” SCRAPING ALL SOURCES")
    info(f"Apify is reading {len(all_urls)} web pages simultaneously...")
    info("This ensures every detail is captured â€” nothing left out...")

    raw_texts = _scrape_urls_apify(all_urls)
    # Try to include a Roadmap.sh roadmap as a high-quality source
    try:
        roadmap_md = fetch_roadmap(topic)
        if roadmap_md:
            slug = topic.lower().strip().replace(" ", "-")
            raw_texts.insert(0, f"SOURCE: Roadmap.sh\nURL: https://roadmap.sh/{slug}\n\n" + roadmap_md)
            ok("Included roadmap.sh content as a high-quality source")
    except Exception:
        pass
    ok(f"Successfully scraped {len(raw_texts)} sources")

    if not raw_texts:
        warn("No content scraped â€” using Nemotron-3-Super knowledge base only")
        return f"TOPIC: {topic}\n\nNo external sources scraped. Use your full knowledge."

    # â”€â”€ Combine all scraped text into one research pool â”€â”€
    combined = f"RESEARCH TOPIC: {topic}\n\n"
    combined += "\n\n" + ("â•"*60) + "\n\n".join(raw_texts)

    # Cap at ~60,000 chars to fit Nemotron-3-Super context window
    if len(combined) > 60000:
        combined = combined[:60000] + "\n\n[Research truncated at context limit]"

    total_words = len(combined.split())
    ok(f"Total research pool: {total_words:,} words from {len(raw_texts)} sources")

    # â”€â”€ Nemotron-3-Super distils all research into a master knowledge document â”€â”€
    section("ðŸ§  PHASE 3 â€” Nemotron-3-Super SYNTHESISING MASTER NOTES")
    info("Nemotron-3-Super is reading all sources and creating comprehensive notes...")
    info("This takes 1-2 minutes â€” building your complete course material...")

    distil_prompt = f"""
You have been given raw research content scraped from {len(raw_texts)} internet sources
about the topic: "{topic}"

Your job is to synthesise ALL of this into one comprehensive, well-organised
master knowledge document that covers the topic completely from beginning to end.

REQUIREMENTS:
- Cover EVERYTHING: history, fundamentals, core concepts, how it works,
  practical usage, advanced topics, common mistakes, best practices, real examples
- Leave NOTHING out â€” a student reading this should know the topic completely
- Write in clear, detailed prose (no bullet points, no markdown headers)
- Organise into logical sections with clear section titles in CAPS
- Target length: 8,000-10,000 words â€” be thorough and detailed
- Every section should be deep and complete, not surface-level

RAW RESEARCH CONTENT:
{combined}

Write the complete master knowledge document now:
"""

    master_notes = ai(client, distil_prompt, max_tokens=MASTER_NOTES_MAX_TOKENS)
    word_count   = len(master_notes.split())
    ok(f"Master notes created: {word_count:,} words")

    return master_notes


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# STEP 2 â€” BUILD STRUCTURED 90-MINUTE COURSE FROM MASTER NOTES
# Nemotron-3-Super converts the research into exactly TARGET_SECTIONS lesson sections
# each sized for WORDS_PER_SECTION words of spoken narration
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def infer_student_duration_months(course_name: str, experience_level: str = "beginner",
                                 goals: list[str] | tuple[str, ...] | None = None,
                                 track: str | None = None) -> int:
    """Estimate a realistic BOI learning duration from the selected course and learner profile."""
    course = (course_name or "").lower()
    goals_text = " ".join((goals or [])).lower()

    base = 3
    if any(token in course for token in [
        "data science", "ai", "cybersecurity", "blockchain", "cloud",
        "backend", "full-stack", "full stack", "product management"
    ]):
        base = 6
    elif any(token in course for token in [
        "frontend", "mobile", "ux", "ui", "digital marketing", "video",
        "graphics", "design", "qa", "seo", "virtual assistant"
    ]):
        base = 4
    elif any(token in course for token in ["prompt", "no-code", "low-code", "game"]):
        base = 3

    if any(token in goals_text for token in [
        "job", "relocate", "freelance", "startup", "switch careers",
        "level up", "remote income"
    ]):
        base = min(6, base + 1)

    experience = (experience_level or "beginner").lower()
    if any(token in experience for token in ["advanced", "comfortable", "intermediate", "🚀", "⚙️"]):
        base = max(3, base - 1)

    if track and "weekend" in track.lower():
        base = max(3, base - 1)

    return max(3, min(6, base))


def infer_course_price(course_name: str, duration_months: int = 3, mode: str = "live") -> dict:
    """Return a standard BOI pricing model, with a lower watch-and-learn rate for video-based access."""
    course = (course_name or "").lower()
    duration_months = max(3, min(6, int(duration_months or 3)))
    mode_key = str(mode or "live").lower().replace("-", "_")
    selected_mode = "watch_and_learn" if "watch" in mode_key else "live"

    base_prices = {
        "ai_and_data": {"live": 350000, "watch_and_learn": 120000},
        "cybersecurity": {"live": 320000, "watch_and_learn": 110000},
        "backend": {"live": 280000, "watch_and_learn": 90000},
        "frontend": {"live": 220000, "watch_and_learn": 75000},
        "design": {"live": 180000, "watch_and_learn": 60000},
        "digital_marketing": {"live": 170000, "watch_and_learn": 55000},
        "product_management": {"live": 240000, "watch_and_learn": 80000},
        "default": {"live": 200000, "watch_and_learn": 70000},
    }

    if any(token in course for token in ["data science", "machine learning", "ai", "llm", "python", "ml"]):
        pricing = base_prices["ai_and_data"]
    elif any(token in course for token in ["cyber", "security", "ethical hacking", "network"]):
        pricing = base_prices["cybersecurity"]
    elif any(token in course for token in ["backend", "django", "flask", "api", "database"]):
        pricing = base_prices["backend"]
    elif any(token in course for token in ["frontend", "react", "next", "javascript", "html", "css", "vue"]):
        pricing = base_prices["frontend"]
    elif any(token in course for token in ["ui", "ux", "graphic", "design", "figma"]):
        pricing = base_prices["design"]
    elif any(token in course for token in ["marketing", "seo", "social media", "brand"]):
        pricing = base_prices["digital_marketing"]
    elif any(token in course for token in ["product", "management"]):
        pricing = base_prices["product_management"]
    else:
        pricing = base_prices["default"]

    if duration_months >= 6:
        pricing = {"live": pricing["live"] + 50000, "watch_and_learn": pricing["watch_and_learn"] + 25000}
    elif duration_months == 4:
        pricing = {"live": pricing["live"] + 20000, "watch_and_learn": pricing["watch_and_learn"] + 10000}

    standard_price = pricing["live"]
    watch_price = pricing["watch_and_learn"]
    selected_price = watch_price if selected_mode == "watch_and_learn" else standard_price

    return {
        "course_name": course_name or "General BOI course",
        "currency": "NGN",
        "standard_price": standard_price,
        "watch_and_learn_price": watch_price,
        "selected_price": selected_price,
        "mode": selected_mode,
        "payment_provider": "paystack",
        "payment_options": ["Paystack full payment", "Paystack installment plan", "Paystack watch and learn access"],
        "price_note": "This is the BOI RSU course price processed through Paystack. Watch-and-learn is the reduced-price access tier for video-based learning.",
    }


def build_student_timetable(course_name: str, duration_months: int = 3,
                           track: str = "Weekday · evenings",
                           class_minutes: int = 60,
                           start_date: str | None = None) -> list[dict]:
    """Build a class timetable and countdown metadata for a student from their selected course track."""
    duration_months = max(3, min(6, int(duration_months or 3)))
    class_minutes = max(45, min(90, int(class_minutes or 60)))

    if track and "weekend" in str(track).lower():
        weekdays = ["Saturday", "Sunday"]
        classes_per_week = 2
    elif track and "daytime" in str(track).lower():
        weekdays = ["Monday", "Wednesday", "Friday"]
        classes_per_week = 3
    else:
        weekdays = ["Tuesday", "Thursday", "Saturday"]
        classes_per_week = 2

    anchor = datetime.strptime(start_date, "%Y-%m-%d").date() if start_date else (date.today() + timedelta(days=2))
    total_sessions = max(8, duration_months * classes_per_week * 2)
    sessions = []
    day_index = 0

    for session_num in range(1, total_sessions + 1):
        current = anchor
        while current.strftime("%A") not in weekdays:
            current += timedelta(days=1)
        if day_index > 0 and session_num > 1:
            current = current + timedelta(days=7)
        while current.strftime("%A") not in weekdays:
            current += timedelta(days=1)

        if "evening" in str(track).lower():
            class_time = datetime.combine(current, datetime.strptime("18:30", "%H:%M").time())
        elif "daytime" in str(track).lower():
            class_time = datetime.combine(current, datetime.strptime("10:00", "%H:%M").time())
        else:
            class_time = datetime.combine(current, datetime.strptime("17:30", "%H:%M").time())

        countdown = "Class is live now"
        delta = class_time - datetime.now()
        if delta.total_seconds() > 0:
            total_seconds = max(0, int(delta.total_seconds()))
            days, remainder = divmod(total_seconds, 86400)
            hours, remainder = divmod(remainder, 3600)
            minutes, _ = divmod(remainder, 60)
            countdown = f"Starts in {days}d {hours:02d}h {minutes:02d}m"

        sessions.append({
            "session_number": session_num,
            "topic": f"{course_name} — Module {((session_num - 1) % 6) + 1}",
            "date": current.isoformat(),
            "weekday": current.strftime("%A"),
            "start_datetime": class_time.isoformat(),
            "duration_minutes": class_minutes,
            "countdown": countdown,
        })
        day_index += 1
        anchor = current + timedelta(days=7)

    return sessions


def build_boi_study_plan(topic: str, duration_months: int = 3, classes_per_week: int = 3,
                         class_minutes: int = 60, client=None) -> list[dict]:
    """Create a BOI-friendly study plan with weekday-based 1-hour classes over 3-6 months."""
    if duration_months < 1:
        duration_months = 1
    if classes_per_week < 1:
        classes_per_week = 1
    if class_minutes <= 0:
        class_minutes = 60

    if duration_months >= 6 and classes_per_week < 4:
        classes_per_week = 4
    if classes_per_week > 4:
        classes_per_week = 4

    weekdays = ["Monday", "Wednesday", "Friday"]
    if classes_per_week == 4:
        weekdays = ["Monday", "Tuesday", "Thursday", "Friday"]

    weeks = max(1, duration_months * 4)
    total_classes = weeks * classes_per_week
    total_sections = max(8, min(24, total_classes))

    sections = []
    schedule_lines = []
    topic_focuses = [
        f"Foundations of {topic}",
        f"Core concepts in {topic}",
        f"Practical application of {topic}",
        f"Common mistakes in {topic}",
        f"Hands-on practice with {topic}",
        f"Review and consolidation of {topic}",
        f"Advanced techniques in {topic}",
        f"Project-based learning for {topic}",
    ]
    for i in range(1, total_sections + 1):
        week_num = max(1, ((i - 1) // classes_per_week) + 1)
        class_num = ((i - 1) % classes_per_week) + 1
        weekday = weekdays[(i - 1) % len(weekdays)]
        focus = topic_focuses[(i - 1) % len(topic_focuses)]
        title = f"Week {week_num} — {weekday}: {focus}"
        content = (
            f"This {class_minutes}-minute BOI lesson is part of a structured {duration_months}-month study plan for {topic}. "
            f"On {weekday}, focus on {focus.lower()} with a clear example, a short exercise, and a recap before the next class."
        )
        schedule_lines.append(f"- Week {week_num} — {weekday}")
        sections.append({
            "section_num": i,
            "title": title,
            "content": content,
            "word_count": 220,
            "duration": min(class_minutes, 60),
            "week": week_num,
            "day": weekday,
        })

    sections[0]["schedule"] = "\n".join(schedule_lines[:min(len(schedule_lines), 8)]) if sections else ""
    return sections


def build_course(topic: str, master_notes: str, client) -> list[dict]:
    """
    Takes master research notes and produces a list of lesson sections.
    Each section dict:
        title      : str  â€” section title
        content    : str  â€” full teaching content (~840 words)
        duration   : int  â€” estimated minutes of speech
        section_num: int  â€” 1-based index
    Total course = exactly TARGET_SECTIONS sections = 90 minutes

    NOTE: PDF checkpoint generation is handled in `main()` so it can
    run after each section is created.
    """

    section("ðŸ“š PHASE 4 â€” BUILDING YOUR 90-MINUTE STRUCTURED COURSE")
    info(f"Nemotron-3-Super is structuring {TARGET_SECTIONS} lesson sections...")
    info(f"Each section = ~{WORDS_PER_SECTION} words = ~6 minutes of teaching")
    info(f"Total class = {TARGET_SECTIONS} Ã— 6min = {TOTAL_CLASS_MINUTES} minutes exactly")

    # First, get Nemotron-3-Super to create a course outline
    outline_prompt = f"""
Based on this comprehensive research about "{topic}", create a structured
{TARGET_SECTIONS}-section course outline that covers the topic completely
from absolute beginner to confident understanding.

The course must flow logically: start with what it is and why it matters,
build through core concepts, practical skills, and finish with advanced topics
and next steps.

Return ONLY a numbered list of {TARGET_SECTIONS} section titles, one per line.
Example format:
1. Introduction to {topic} â€” What It Is and Why It Matters
2. ...

RESEARCH:
{master_notes[:4000]}

List the {TARGET_SECTIONS} section titles now:
"""

    outline_raw = ai(client, outline_prompt, max_tokens=1000)

    # Parse the outline into section titles
    titles = []
    for line in outline_raw.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        # Strip leading numbers like "1." or "1)"
        cleaned = re.sub(r'^\d+[\.\)]\s*', '', line).strip()
        if cleaned:
            titles.append(cleaned)

    # Ensure we have exactly TARGET_SECTIONS titles
    if len(titles) < TARGET_SECTIONS:
        warn(f"Only got {len(titles)} section titles â€” padding...")
        for i in range(len(titles) + 1, TARGET_SECTIONS + 1):
            titles.append(f"Section {i}: Advanced Topics and Applications")
    titles = titles[:TARGET_SECTIONS]

    ok(f"Course outline ready: {len(titles)} sections")

    # â”€â”€ Generate full content for each section â”€â”€
    sections = []
    for i, title in enumerate(titles, 1):
        info(f"  Writing Section {i}/{TARGET_SECTIONS}: {title[:50]}...")

        content_prompt = f"""
You are writing Section {i} of {TARGET_SECTIONS} of a spoken class about "{topic}".

SECTION TITLE: {title}

Write a complete, detailed teaching lesson for this section.

CRITICAL REQUIREMENTS:
- Target EXACTLY {WORDS_PER_SECTION} words (this equals ~6 minutes of speech)
- Write in flowing spoken prose â€” no bullet points, no markdown
- Begin with a warm transition: "Welcome to Section {i}..." or similar
- Explain every concept deeply with real-world examples and analogies
- End with a brief summary of what was covered and a bridge to the next section
- A student should finish this section with deep, confident understanding
- DO NOT be superficial â€” go deep on every point

Use this research as your knowledge base:
{master_notes[:8000]}

Previous sections covered: {', '.join(titles[:i-1]) if i > 1 else 'Nothing yet â€” this is the first section'}

Write the full {WORDS_PER_SECTION}-word lesson for "{title}" now:
"""
        content  = ai(client, content_prompt, max_tokens=SECTION_CONTENT_MAX_TOKENS)
        wc       = len(content.split())
        est_mins = round(wc / WORDS_PER_MINUTE, 1)

        sections.append({
            "section_num": i,
            "title":       title,
            "content":     content,
            "word_count":  wc,
            "duration":    est_mins,
        })

        ok(f"    Section {i} ready â€” {wc} words (~{est_mins} min)")

    total_words = sum(s["word_count"] for s in sections)
    total_mins  = round(total_words / WORDS_PER_MINUTE, 1)
    ok(f"Complete course built: {total_words:,} words = ~{total_mins} minutes of class time")

    return sections


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# STEP 3 â€” CLASS MODE (90-minute voice-narrated class)
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def class_mode(client, sections: list[dict], topic: str, course_title: str):
    total      = len(sections)
    voice_on   = bool(DEEPGRAM_KEY)
    start_time = time.time()

    total_words = sum(s["word_count"] for s in sections)
    total_mins  = round(total_words / WORDS_PER_MINUTE, 1)

    print(f"""
{Fore.MAGENTA}{'â–ˆ'*62}
  ðŸ«  CLASS MODE â€” {course_title[:40]}
  ðŸ“š  {total} sections | ~{total_mins} minutes total class time
  ðŸ”Š  Deepgram voice {'ENABLED âœ…' if voice_on else 'DISABLED âš ï¸  (set DEEPGRAM_API_KEY)'}
  â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  ENTER = next section | Q = quit | ? = ask question
  M = mute/unmute voice | S = skip to section number
{'â–ˆ'*62}{Style.RESET_ALL}
""")
    time.sleep(1)

    if voice_on:
        _ensure_audio_player()
        # Opening announcement
        opening = (f"Welcome to your {total_mins}-minute class on {topic}. "
                   f"This class has {total} sections covering everything from "
                   f"the very beginning to advanced topics. Let's get started.")
        speak_text(opening)

    for i, sec in enumerate(sections):
        sec_num  = sec["section_num"]
        title    = sec["title"]
        content  = sec["content"]
        wc       = sec["word_count"]
        est_mins = sec["duration"]

        elapsed_mins = round((time.time() - start_time) / 60, 1)

        # â”€â”€ Section header â”€â”€
        print(f"\n{Fore.MAGENTA}{'â”'*62}")
        print(f"  ðŸ“–  SECTION {sec_num}/{total}  â€”  {title[:48]}")
        print(f"  â±ï¸   ~{est_mins} min  |  Elapsed: {elapsed_mins} min  |  {wc} words")
        print(f"{'â”'*62}{Style.RESET_ALL}\n")

        # â”€â”€ Print full section content to terminal â”€â”€
        print(f"{Fore.WHITE}{content}{Style.RESET_ALL}\n")

        # â”€â”€ Progress bar â”€â”€
        filled = int((sec_num / total) * 50)
        bar    = f"{'â–ˆ'*filled}{'â–‘'*(50-filled)}"
        pct    = int((sec_num / total) * 100)
        print(f"\n{Fore.YELLOW}  [{bar}] {pct}%  â€”  Section {sec_num}/{total}{Style.RESET_ALL}")

        # â”€â”€ Deepgram speaks the full section content â”€â”€
        if voice_on:
            remaining = total - sec_num
            print(f"\n{Fore.MAGENTA}  ðŸ”Š  Speaking section {sec_num} (~{est_mins} min)...{Style.RESET_ALL}")
            speak_text(content, muted=not voice_on)

        # â”€â”€ Pause between sections (except last) â”€â”€
        if i < total - 1:
            print(f"\n{Fore.GREEN}  ENTER=next | Q=quit | ?=question | M=mute/unmute | S=skip to section{Style.RESET_ALL}")
            try:
                cmd = input(f"  > ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                cmd = "q"

            if cmd == "q":
                elapsed = round((time.time() - start_time) / 60, 1)
                print(f"\n{Fore.YELLOW}  â¹ï¸  Class paused after Section {sec_num} ({elapsed} min elapsed){Style.RESET_ALL}\n")
                return i

            elif cmd == "m":
                voice_on = not voice_on
                state    = "ON ðŸ”Š" if voice_on else "OFF ðŸ”‡"
                ok(f"Voice {state}")
                if voice_on:
                    _ensure_audio_player()

            elif cmd == "s":
                try:
                    n = int(input(f"  {Fore.CYAN}Jump to section (1-{total}): {Style.RESET_ALL}").strip())
                    if 1 <= n <= total:
                        # Rewind the loop â€” Python for loop doesn't support this
                        # directly so we set i and break; handled by outer loop restart
                        ok(f"Jumping to Section {n}...")
                        # rebuild slice
                        remaining_sections = sections[n-1:]
                        class_mode_resume(client, remaining_sections, topic,
                                          course_title, voice_on, start_time,
                                          total, total_mins)
                        return n - 1
                    else:
                        err("Invalid section number.")
                except ValueError:
                    err("Please enter a number.")

            elif cmd == "?":
                q = input(f"\n{Fore.CYAN}  Your question: {Style.RESET_ALL}").strip()
                if q:
                    print(f"\n{Fore.CYAN}{'â”€'*62}")
                    print(f"  ðŸ’¬  Nemotron-3-Super ANSWERS:")
                    print(f"{'â”€'*62}{Style.RESET_ALL}\n")
                    # Give context from current + adjacent sections
                    ctx = "\n\n".join(
                        s["content"] for s in sections[max(0,i-1):i+2]
                    )
                    answer = ai(client,
                        f"Course context:\n{ctx}\n\n"
                        f"Student question: {q}\n\n"
                        "Answer clearly, deeply and helpfully as a great tutor would."
                    )
                    print(answer)
                    if voice_on:
                        print(f"\n{Fore.MAGENTA}  ðŸ”Š  Speaking answer...{Style.RESET_ALL}")
                        speak_text(answer)
                    print(f"\n{Fore.GREEN}  Press ENTER to continue...{Style.RESET_ALL}")
                    input("  > ")

        else:
            # â”€â”€ Course complete â”€â”€
            elapsed = round((time.time() - start_time) / 60, 1)
            completion = (
                f"Congratulations! You have successfully completed the full "
                f"{total}-section class on {topic}. You studied for "
                f"{elapsed} minutes and covered everything from the fundamentals "
                f"to advanced topics. Well done â€” keep learning and keep growing!"
            )
            print(f"\n{Fore.GREEN}{'â–ˆ'*62}")
            print(f"  ðŸŽ‰  CLASS COMPLETE!")
            print(f"  âœ…  All {total} sections finished in {elapsed} minutes")
            print(f"  ðŸ†  Topic mastered: {topic}")
            print(f"{'â–ˆ'*62}{Style.RESET_ALL}\n")
            if voice_on:
                speak_text(completion)

        # ---- After each class: file W3Schools textbooks for its videos ----
        try:
            _generate_post_class_textbooks(client, sections, topic, course_title)
        except Exception as e:
            err(f"Post-class textbook step skipped: {str(e)[:140]}")

    return total - 1


def class_mode_resume(client, sections, topic, course_title,
                      voice_on, start_time, total, total_mins):
    """Helper to resume class mode from a jumped-to section."""
    for i, sec in enumerate(sections):
        sec_num  = sec["section_num"]
        title    = sec["title"]
        content  = sec["content"]
        wc       = sec["word_count"]
        est_mins = sec["duration"]
        elapsed_mins = round((time.time() - start_time) / 60, 1)

        print(f"\n{Fore.MAGENTA}{'â”'*62}")
        print(f"  ðŸ“–  SECTION {sec_num}/{total}  â€”  {title[:48]}")
        print(f"  â±ï¸   ~{est_mins} min  |  Elapsed: {elapsed_mins} min")
        print(f"{'â”'*62}{Style.RESET_ALL}\n")
        print(f"{Fore.WHITE}{content}{Style.RESET_ALL}\n")

        filled = int((sec_num / total) * 50)
        bar    = f"{'â–ˆ'*filled}{'â–‘'*(50-filled)}"
        print(f"\n{Fore.YELLOW}  [{'â–ˆ'*filled}{'â–‘'*(50-filled)}] {int(sec_num/total*100)}%{Style.RESET_ALL}")

        if voice_on:
            print(f"\n{Fore.MAGENTA}  ðŸ”Š  Speaking section {sec_num}...{Style.RESET_ALL}")
            speak_text(content)

        if i < len(sections) - 1:
            print(f"\n{Fore.GREEN}  ENTER=next | Q=quit | ?=question | M=mute/unmute{Style.RESET_ALL}")
            try:
                cmd = input(f"  > ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                return
            if cmd == "q":
                return
            elif cmd == "m":
                voice_on = not voice_on
            elif cmd == "?":
                q = input(f"\n{Fore.CYAN}  Your question: {Style.RESET_ALL}").strip()
                if q:
                    ctx    = content
                    answer = ai(client,
                        f"Context:\n{ctx}\n\nQuestion: {q}\n\nAnswer thoroughly:")
                    print(answer)
                    if voice_on:
                        speak_text(answer)
                    input(f"\n{Fore.GREEN}  ENTER to continue...{Style.RESET_ALL}  ")


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# LEARNING MENU â€” browse, quiz, Q&A between class sessions
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def ai_quiz(client, content: str, title: str) -> str:
    return ai(client,
        f"Section content:\n\n{content}\n\n"
        f"Create 5 thoughtful multiple choice questions (A B C D) that "
        f"test deep understanding of '{title}'. "
        f"Mark correct answers with âœ…. Write in spoken prose.",
        max_tokens=1500
    )

def ai_summary(client, content: str, title: str) -> str:
    return ai(client,
        f"Section: {title}\n\nContent:\n{content}\n\n"
        f"Write a thorough 5-7 sentence spoken summary of this section. "
        f"Capture every key point a student must remember.",
        max_tokens=800
    )


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# POST-CLASS TEXTBOOK (W3Schools reference-first format)
# After each class, turn what the YouTube video taught into a structured
# "textbook" saved through boirsu and shown in the student dashboard library:
#   chapter sidebar -> micro-lesson pages -> intro -> live code/image ->
#   Try-it-Yourself sandbox -> variations -> Note/Tip -> Exercise (+ quiz).
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
W3_TEXTBOOK_MAX_TOKENS = int(os.environ.get("W3_TEXTBOOK_MAX_TOKENS", "16000"))
POST_CLASS_MAX_TEXTBOOKS = int(os.environ.get("POST_CLASS_MAX_TEXTBOOKS", "2"))

W3_TEXTBOOK_INSTRUCTION = (
    "You are an expert technical writer and PDF document designer who also "
    "teaches like W3Schools: short plain-language micro-lessons, one concrete "
    "example immediately, hands-on practice right away, progressive "
    "variations, and friendly Note/Tip callouts. You write complete, "
    "professional, book-length learning material with real structure (cover, "
    "table of contents, introduction, chapters, practice, glossary) and you "
    "always answer with raw JSON only - never markdown, never commentary."
)

# ---------------------------------------------------------------------------
# The full author prompt. Kept as a plain (non-f) string so the JSON braces in
# the schema stay literal; the four __TOKENS__ are filled in by
# generate_w3_textbook(). TWO prompts are merged here and must stay merged:
#   1. the original W3Schools reference-first textbook prompt, and
#   2. the expert technical writer / PDF document designer prompt.
# ---------------------------------------------------------------------------
W3_TEXTBOOK_PROMPT = '''Topic/course: __TOPIC__
Video title: __VIDEO_TITLE__
Video URL: __VIDEO_URL__

__TRANSCRIPT__

You are an expert technical writer and PDF document designer. Write and produce
a complete, professional, PDF-ready textbook about everything this class video
actually taught.

AUDIENCE: complete beginners with no experience, unless the video clearly
targets a more advanced audience.
TONE: clear, friendly and practical - W3Schools style (short chapters, many
small examples) mixed with freeCodeCamp handbook style (explained step by step,
in short paragraphs of 3 to 5 sentences).

LENGTH REQUIREMENTS (very important):
- The book must contain AT LEAST 3000 words of real teaching content. Do not
  count headings, the table of contents, or code towards the 3000.
- Do not summarise or rush. Explain every idea in depth, with reasons, not just
  definitions.
- Write chapter by chapter. Every main chapter must be at least 350 words.
- Before you finish, count your words. If you are under 3000, keep adding
  useful explanations, examples and exercises until you pass it.

REQUIRED STRUCTURE (each item maps onto a JSON key further down):
1. Cover page: title, subtitle, and author or date. Nothing else on that page.
2. Table of contents: the chapter names in reading order (real page numbers are
   stamped when the PDF is paginated, so just give the order).
3. Introduction: what the topic is, why it matters, what the reader will learn.
4. At least 6 main chapters, ordered from basic to advanced. Each chapter must
   have a short overview, detailed explanations, at least 2 practical examples
   with a line-by-line explanation, a "Common Mistakes" list, and a "Key Points"
   summary.
5. A practice section with at least 10 exercises, followed by an answers
   section with one answer per exercise.
6. A conclusion with suggested next steps.
7. A short glossary of the important terms.
On top of that, keep the W3Schools teaching rhythm inside every lesson: an
immediate example, a "Try it Yourself" sandbox, progressive variations, a
Note or Tip callout, and an end-of-lesson exercise.

LAYOUT AND FORMATTING RULES (the book is rendered to A4, so write content that
lays out cleanly and nothing may overlap or be cramped):
- A4 pages with margins of at least 2.5 cm on every side.
- Body text 11 to 12 pt in a readable font, with line spacing of at least 1.4.
- Headings clearly larger than body text: chapter title 24 pt, section heading
  16 pt, sub-heading 13 pt.
- Clear space before and after every heading, paragraph, list, table, image and
  code block. Never let elements touch or sit on top of each other.
- Every chapter starts on a new page.
- Code goes in its own shaded box in a monospace font. Keep every code line
  under 78 characters so long lines wrap instead of running past the box or the
  page edge.
- Tables stay inside the margins with padding in every cell.
- Never leave a heading alone at the bottom of a page - keep it with the
  content that follows it.
- One main colour plus grey, used consistently throughout.
- Page numbers in the footer and the chapter title in the header on every page
  except the cover.
- Use real bullet lists and numbered lists instead of long blocks of text.

JSON OUTPUT SHAPE (exact - the rest of the system reads these keys):
Return ONLY raw JSON (no markdown fences, no commentary) shaped exactly like:

{
  "title": "Textbook · <short book title>",
  "subtitle": "<one line saying who the book is for>",
  "cover": {"title": "<cover title>", "subtitle": "<cover subtitle>", "author_or_date": "<author or date>"},
  "toc": [{"chapter": "<chapter name>", "page": 0}],
  "introduction": "<what the topic is, why it matters, what the reader will learn>",
  "chapters": [
    {
      "chapter": "<sidebar chapter name, e.g. Essentials>",
      "overview": "<short chapter overview>",
      "lessons": [
        {
          "title": "<micro-lesson title>",
          "intro": "<1-3 plain sentences explaining the concept>",
          "content": "<the detailed teaching text for this lesson: several short paragraphs of 3 to 5 sentences each that explain the idea in depth with reasons. Across a chapter these add up to more than 350 words, and across the book to more than 3000.>",
          "example": {"lang": "<python|javascript|html|css|sql|java|c|code>", "code": "<short runnable example>", "caption": "<one line>"},
          "example_explanation": "<line-by-line explanation of the example above>",
          "second_example": {"lang": "<same lang>", "code": "<a second, different example>", "caption": "<one line>"},
          "second_example_explanation": "<line-by-line explanation of the second example>",
          "try_it": {"lang": "<same lang>", "starter": "<editable starting code the student edits and runs>", "task": "<what to change/observe>"},
          "variations": [
            {"label": "<e.g. Edge case>", "lang": "<lang>", "code": "<variation code>", "text": "<when/why this variation>"}
          ],
          "common_mistakes": ["<mistake 1>", "<mistake 2>"],
          "key_points": ["<key point 1>", "<key point 2>"],
          "note": "<Note: caveat or related info, 1-2 sentences>",
          "tip": "<Tip: practical advice, 1 sentence>",
          "exercise": {"prompt": "<small hands-on task>", "hint": "<gentle hint>"}
        }
      ]
    }
  ],
  "practice_section": {
    "exercises": [{"number": 1, "prompt": "<exercise prompt>"}],
    "answers": [{"number": 1, "answer": "<answer>"}]
  },
  "conclusion": "<wrap-up and suggested next steps>",
  "glossary": [{"term": "<term>", "definition": "<short definition>"}]
}

Rules:
- 3 to 5 chapters named like a progression: Essentials -> Going Deeper ->
  Advanced/Systems style. Use 6 or more chapters when the topic needs the room
  to reach the 3000-word minimum.
- 2 to 3 lessons per chapter; order the basic case first, edge cases and
  variations later.
- Every lesson MUST have intro, content, example, example_explanation, a second
  example with its explanation, try_it, at least 1 variation, common_mistakes,
  key_points, a note or tip, and an exercise.
- practice_section MUST hold at least 10 exercises, each with a matching answer.
- glossary MUST define every term a beginner would trip over.
- Ground EVERYTHING in what THIS video actually taught (use the transcript).
- If the subject is NOT code/technical: use
  "example": {"lang":"image","url":"","caption":"<describe the exact diagram or photo to show>"}
  instead of code, do the same for the second example, make try_it.lang
  "reflect" with starter being a short reflection prompt, and keep everything
  else exactly as described.
- Keep code examples short enough to read in 20 seconds, and keep every code
  line under 78 characters so it fits the shaded box.
- Never repeat a paragraph and never pad with filler - every sentence must teach
  something.
- Language: plain, warm and encouraging, but never vague.

QUALITY CHECK BEFORE OUTPUT - confirm every point and fix anything that fails:
1. The book has more than 3000 words of real content.
2. Every required section is present: cover, table of contents, introduction,
   at least 6 chapters, practice section with answers, conclusion, glossary.
3. No text, code, table or list overlaps, is cut off, or crosses a margin.
4. The table of contents matches the real chapter order.
5. Every lesson carries the full set of teaching blocks listed above.
6. There are no repeated paragraphs and no filler text.

Now output the finished JSON document. Do not ask questions, and do not give a
summary or an outline.
'''


def _repair_truncated_json(text):
    """Rebalance a JSON object the token budget cut off mid-stream.

    When finish_reason is "length" the book JSON is chopped part-way through;
    plain json.loads then rejects the WHOLE answer and the caller silently
    files an empty fallback skeleton. Closing the dangling string and every
    open bracket keeps every COMPLETE chapter written before the cut.
    """
    stack, in_str, esc = [], False, False
    for ch in text:
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch in "{[":
            stack.append(ch)
        elif ch in "}]":
            if stack:
                stack.pop()
    out = text
    if in_str:
        if esc:
            out = out[:-1]          # dangling backslash: drop it, then close
        out += '"'
    out += "".join("}" if c == "{" else "]" for c in reversed(stack))
    return out


def _extract_json(text):
    """Best-effort JSON extraction from a model answer (fences, prose, etc)."""
    cleaned = re.sub(r"```(?:json)?|```", "", (text or "")).strip()
    # Reasoning models sometimes leak <think>...</think> into content; drop it
    # (and any unclosed <think> tail) before scanning for JSON.
    cleaned = re.sub(r"<think>.*?</think>", "", cleaned, flags=re.S | re.I).strip()
    cleaned = re.sub(r"<think>.*", "", cleaned, flags=re.S | re.I).strip()
    for opener, closer in (("{", "}"), ("[", "]")):
        start, end = cleaned.find(opener), cleaned.rfind(closer)
        if start != -1 and end > start:
            try:
                data = json.loads(cleaned[start:end + 1])
                return data
            except Exception:
                continue
    # Last resort: the answer was probably cut off by the token budget
    # (finish_reason "length"). Rebalance the truncated object so every
    # COMPLETE chapter already written still lands in the book, instead of
    # the whole answer being thrown away for an empty fallback skeleton.
    for opener in ("{", "["):
        start = cleaned.find(opener)
        if start != -1:
            try:
                data = json.loads(_repair_truncated_json(cleaned[start:]))
                if isinstance(data, dict):
                    return data
            except Exception:
                continue
    return None


def generate_w3_textbook(client, topic: str, transcript: str, video_info: dict) -> dict:
    """
    Ask Nemotron for a complete W3Schools-style textbook as strict JSON.

    Returns the parsed dict, or {} when the model output cannot be used
    (the caller then falls back to a transcript-based builder).
    """
    transcript_block = (transcript or "").strip()
    if transcript_block:
        transcript_block = "TRANSCRIPT OF THE VIDEO THE STUDENT JUST WATCHED:\n" + transcript_block[:12000]
    else:
        transcript_block = "(No transcript available - teach from the video title/topic.)"

    prompt = (W3_TEXTBOOK_PROMPT
              .replace("__TOPIC__", str(topic or "").strip())
              .replace("__VIDEO_TITLE__",
                       str((video_info or {}).get("title") or "the class lesson video"))
              .replace("__VIDEO_URL__",
                       str((video_info or {}).get("url") or "n/a"))
              .replace("__TRANSCRIPT__", transcript_block))


    raw = ai(client, prompt, max_tokens=W3_TEXTBOOK_MAX_TOKENS)
    # ai() uses the spoken-tutor system prompt; retry once with the author
    # persona when the first answer is not usable JSON.
    data = _extract_json(raw)
    if not isinstance(data, dict):
        # Permanent diagnosability: never fail to a silent fallback again -
        # show exactly what came back (truncated JSON, error string, prose).
        info("Textbook draft 1 unusable (len=%d) head=%r tail=%r"
             % (len(raw or ""), (raw or "")[:160], (raw or "")[-160:]))
        try:
            response = client.chat.completions.create(
                model=MODEL_ID,
                messages=[
                    {"role": "system", "content": W3_TEXTBOOK_INSTRUCTION},
                    {"role": "user",   "content": prompt},
                ],
                temperature=0.4,
                top_p=0.95,
                max_tokens=W3_TEXTBOOK_MAX_TOKENS,
                timeout=max(180.0, float(W3_TEXTBOOK_MAX_TOKENS) / 25.0),
                extra_body=({"chat_template_kwargs": {"enable_thinking": False}}
                            if "nemotron" in str(MODEL_ID).lower() else None),
            )
            msg = response.choices[0].message
            info("Textbook retry finish_reason=%s usage=%s"
                 % (getattr(response.choices[0], "finish_reason", "?"),
                    getattr(getattr(response, "usage", None), "completion_tokens", "?")))
            data = _extract_json(msg.content or "")
        except Exception as e:
            err(f"Textbook model retry failed: {str(e)[:120]}")
    if not (isinstance(data, dict) and data.get("chapters")):
        info("Textbook JSON unusable after both attempts (chapters missing/empty).")
    return data if isinstance(data, dict) and data.get("chapters") else {}


def _fetch_video_transcript_text(video_url_or_id: str) -> str:
    """
    Pull the caption text for a video via AI-TUTOR/youtube_content.py.
    Returns '' on any failure - the textbook is then written from titles/topic.
    """
    if not video_url_or_id:
        return ""
    try:
        import importlib.util
        m = re.search(r"(?:v=|youtu\.be/|embed/|shorts/)([A-Za-z0-9_-]{11})",
                      str(video_url_or_id))
        vid = m.group(1) if m else (
            video_url_or_id if re.fullmatch(r"[A-Za-z0-9_-]{11}", str(video_url_or_id)) else "")
        if not vid:
            return ""
        yc_path = os.path.join(SCRIPT_DIR, "AI-TUTOR", "youtube_content.py")
        if not os.path.exists(yc_path):
            return ""
        spec = importlib.util.spec_from_file_location("boi_youtube_content", yc_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        entries = mod.fetch_transcript(vid) or []
        parts = [str(e.get("text", "")).strip() for e in entries if isinstance(e, dict)]
        return " ".join(p for p in parts if p)[:14000]
    except Exception as e:
        warn(f"Transcript unavailable ({str(e)[:90]}) - using title/topic only.")
        return ""


def _fallback_w3_textbook(topic: str, transcript: str, video_info: dict) -> dict:
    """
    No-model / unparseable-output path: build a real (if simpler) W3Schools
    book straight from the transcript so the library ALWAYS gets material.
    Non-technical topics get image-style examples instead of code.
    """
    topic_n = (topic or "").lower()
    codey = any(k in topic_n for k in (
        "python", "javascript", "js", "html", "css", "code", "coding",
        "programming", "sql", "java", "react", "web dev", "developer", "php"))
    chunks = [c.strip() for c in re.split(r"(?<=[.!?])\s+", transcript or "") if c.strip()]
    if not chunks:
        chunks = [f"Key ideas from {video_info.get('title') or topic}."]
    per = max(3, len(chunks) // 6 + 1)
    blocks = [" ".join(chunks[i:i + per])[:900] for i in range(0, len(chunks), per)][:6]
    while len(blocks) < 4:
        blocks.append(f"Revise the core ideas of {topic} from the class video.")

    def lesson(n, chunk, chapter_kind):
        return {
            "title": f"Lesson {n}: {(chunk[:48] + '...') if len(chunk) > 48 else chunk}",
            "intro": f"From the class video: {chunk[:280]}",
            "example": ({"lang": "python",
                         "code": "# " + topic + "\nprint(\"" + chunk[:60] + "\")",
                         "caption": "Run this to keep the idea in muscle memory"}
                        if codey and n % 2 == 1 else
                        {"lang": "image", "url": "",
                         "caption": f"Diagram idea: visualise '{topic}' - {chapter_kind}"}),
            "try_it": ({"lang": "python",
                        "starter": "print(\"Today I learned about " + topic + "\")",
                        "task": "Change the message to summarise the lesson in your own words."}
                       if codey else
                       {"lang": "reflect", "starter": "In my own words: " + topic + " means ...",
                        "task": "Finish the sentence with 2-3 lines from the video."}),
            "variations": [{"label": "Going deeper", "text": chunk[-260:] or chunk}],
            "note": "Note: taken automatically from today's class video.",
            "tip": "Tip: teach this back to a classmate within 24 hours.",
            "exercise": {"prompt": "Write 2 sentences applying this lesson to a real project.",
                         "hint": "Use an example you personally care about."},
        }

    half = (len(blocks) + 1) // 2
    chapters = [
        {"chapter": "Essentials",
         "lessons": [lesson(i + 1, b, "essentials") for i, b in enumerate(blocks[:half])]},
        {"chapter": "Going Deeper",
         "lessons": [lesson(half + i + 1, b, "going deeper") for i, b in enumerate(blocks[half:])]},
    ]
    return {
        "title": f"Textbook · {video_info.get('title') or topic}",
        "chapters": chapters,
        "_source": "transcript-fallback",
    }


def build_class_textbook(course="", topic="", video_url="", video_title="",
                         video_id="", class_number=None, client=None,
                         transcript_text="", career_path=""):
    """
    One-stop post-class pipeline used by CLASS MODE and by api_server:

        transcript -> W3Schools JSON -> boirsu.save_class_textbook()

    Works without NVIDIA too: the transcript-fallback builder still files a
    usable book, so the dashboard library never comes up empty.
    Returns the saved library row (or None).
    """
    info(f"Building W3Schools textbook for: {video_title or topic or course}")
    if not client:
        try:
            client = setup_ai()
        except Exception as e:
            warn(f"No AI client ({str(e)[:80]}); using fallback builder.")
            client = None

    vid = video_id or ""
    transcript = transcript_text or _fetch_video_transcript_text(vid or video_url)

    data = {}
    if client:
        data = generate_w3_textbook(
            client, topic or course, transcript,
            {"title": video_title, "url": video_url})
    if not data.get("chapters"):
        warn("Model output unusable - filing transcript-based textbook instead.")
        data = _fallback_w3_textbook(topic or course, transcript,
                                     {"title": video_title, "url": video_url})

    data.setdefault("course", course or topic or "")
    data["career_path"] = career_path
    data["class_number"] = class_number
    data["source_video"] = {
        "title": video_title or "", "url": video_url or "", "video_id": vid,
    }
    data.setdefault("title", f"Textbook · {video_title or topic or course}")

    try:
        import boirsu as boi_store
    except Exception as e:
        err(f"Could not import boirsu store: {e}")
        return None

    row = boi_store.save_class_textbook(data)
    if row:
        ok(f"Textbook filed in the student library: {row['id']}")
    return row


def _generate_post_class_textbooks(client, sections: list[dict], topic: str,
                                   course_title: str):
    """
    Called automatically when CLASS MODE finishes. Files one W3Schools
    textbook per class video (capped) so every watched lesson lands in the
    studentdashboard.vue library aligned with its YouTube source.
    """
    section("POST-CLASS TEXTBOOK GENERATION (W3Schools format)")
    videos, seen = [], set()
    for sec in sections or []:
        for v in (sec.get("videos") or []):
            url = v.get("url") or v.get("watch_url") or ""
            key = url or v.get("title", "")
            if key and key not in seen:
                seen.add(key)
                videos.append(v)
    if not videos:
        warn("No class videos found - filing one topic-level textbook instead.")
        videos = [{"title": topic, "url": ""}]
    built, target = 0, min(len(videos), max(1, POST_CLASS_MAX_TEXTBOOKS))
    for v in videos[:max(1, POST_CLASS_MAX_TEXTBOOKS)]:
        try:
            if build_class_textbook(
                course=course_title or topic, topic=topic,
                video_url=v.get("url") or "", video_title=v.get("title") or "",
                client=client,
            ):
                built += 1
        except Exception as e:
            err(f"Textbook generation failed: {str(e)[:140]}")
    ok(f"{built}/{target} textbook(s) added to the library.")




def _generate_course_pdf_for_topic(topic: str, course_title: str, sections: list[dict]):
    """Write lesson.md for the topic and generate a PDF on-demand."""
    from datetime import datetime

    lessons_dir = os.path.join(os.path.dirname(__file__), "lessons")
    output_dir  = os.path.join(os.path.dirname(__file__), "output")

    course_folder = _sanitize_folder_name(topic) + "_course"
    lesson_dir = os.path.join(lessons_dir, course_folder)

    date_str = datetime.now().strftime("%Y-%m-%d")
    teacher = "AI Tutor"

    _write_lesson_md(
        lesson_dir=lesson_dir,
        class_name=course_folder.replace("_", " "),
        teacher=teacher,
        date_str=date_str,
        course_title=course_title,
        sections=sections,
    )
    _generate_pdf_for_course(lessons_dir=lessons_dir, output_dir=output_dir)
    ok(f"PDF generation completed (output: {output_dir}).")




def build_learning_menu_lines(boi_mode: bool = False) -> list[str]:
    """Build the interactive lesson menu, with a simpler BOI-friendly view by default."""
    lines = [
        f"  {Fore.YELLOW}[1]{Style.RESET_ALL} 📖  Read this section",
        f"  {Fore.YELLOW}[2]{Style.RESET_ALL} 🔊  Read + Speak this section (Deepgram)",
        f"  {Fore.YELLOW}[3]{Style.RESET_ALL} 📝  Summary of this section",
        f"  {Fore.YELLOW}[4]{Style.RESET_ALL} ✓  Quiz on this section",
        f"  {Fore.YELLOW}[5]{Style.RESET_ALL} ❓  Ask a question",
        f"  {Fore.YELLOW}[6]{Style.RESET_ALL} ➡️   Next section",
        f"  {Fore.YELLOW}[7]{Style.RESET_ALL} ⬅️   Previous section",
        f"  {Fore.YELLOW}[8]{Style.RESET_ALL} 🔢  Jump to section number",
        f"  {Fore.YELLOW}[O]{Style.RESET_ALL} 📚  Course overview",
        f"  {Fore.YELLOW}[C]{Style.RESET_ALL} 🎓  CLASS MODE — full 90-min voice class",
        f"  {Fore.YELLOW}[G]{Style.RESET_ALL} 📄  Generate PDF for this course/topic",
        f"  {Fore.YELLOW}[0]{Style.RESET_ALL} ⏹️  Exit",
    ]
    if not boi_mode:
        lines.insert(10, f"  {Fore.YELLOW}[R]{Style.RESET_ALL}  God Mode internet resources for this section")
        lines.insert(11, f"  {Fore.YELLOW}[A]{Style.RESET_ALL}  God Mode resources for the full course")
    return lines


def learning_menu(client, sections: list[dict], topic: str, course_title: str, boi_mode: bool = True):

    current = 0
    total   = len(sections)

    # Print course overview
    section("ðŸ“š COURSE OVERVIEW")
    info("Nemotron-3-Super generating your course overview...")
    titles_list = "\n".join(
        f"  Section {s['section_num']}: {s['title']} (~{s['duration']} min)"
        for s in sections
    )
    total_mins = round(sum(s["duration"] for s in sections), 1)
    overview   = ai(client,
        f"Topic: {topic}\n\nCourse sections:\n{titles_list}\n\n"
        f"Write a warm, motivating 5-sentence spoken overview of what "
        f"this {total_mins}-minute course covers and what the student will "
        f"achieve by the end.",
        max_tokens=600
    )
    print(f"\n{overview}\n")
    if DEEPGRAM_KEY:
        speak_text(overview)

    while True:
        sec      = sections[current]
        sec_num  = sec["section_num"]
        title    = sec["title"]
        wc       = sec["word_count"]
        est_mins = sec["duration"]

        print(f"\n{Fore.CYAN}{'â•'*62}")
        print(f"  ðŸ“– Section {sec_num}/{total}  |  {title[:48]}")
        print(f"  â±ï¸  ~{est_mins} min  |  {wc} words")
        print(f"{'â•'*62}{Style.RESET_ALL}")
        print(f"\n{'-' * 62}")
        for line in build_learning_menu_lines(boi_mode=boi_mode):
            print(line)
        print(f"{'-' * 62}")
        try:
            choice = input(f"{Fore.CYAN}  Your choice: {Style.RESET_ALL}").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if choice == "1":
            section(f"ðŸ“– SECTION {sec_num} â€” {title}")
            print(sec["content"])

        elif choice == "2":
            section(f"ðŸ”Š READING + SPEAKING â€” Section {sec_num}")
            print(sec["content"])
            if DEEPGRAM_KEY:
                print(f"\n{Fore.MAGENTA}  ðŸ”Š  Speaking...{Style.RESET_ALL}")
                speak_text(sec["content"])
            else:
                warn("DEEPGRAM_API_KEY not set â€” voice disabled.")

        elif choice == "3":
            section(f"ðŸ“ SUMMARY â€” Section {sec_num}")
            summary = ai_summary(client, sec["content"], title)
            print(summary)
            if DEEPGRAM_KEY:
                speak_text(summary)

        elif choice == "4":
            section(f"â“ QUIZ â€” Section {sec_num}: {title}")
            quiz = ai_quiz(client, sec["content"], title)
            print(quiz)

        elif choice == "5":
            try:
                q = input(f"\n{Fore.CYAN}  Your question: {Style.RESET_ALL}").strip()
            except (EOFError, KeyboardInterrupt):
                q = ""
            if q:
                section("ðŸ’¬ Nemotron-3-Super ANSWER")
                ctx    = "\n\n".join(
                    s["content"] for s in sections[max(0,current-1):current+2]
                )
                answer = ai(client,
                    f"Course context:\n{ctx}\n\nQuestion: {q}\n\n"
                    "Answer completely and clearly as a great tutor."
                )
                print(answer)
                if DEEPGRAM_KEY:
                    speak_text(answer)

        elif choice == "6":
            if current < total - 1:
                current += 1
                ok(f"Now on Section {current+1}: {sections[current]['title'][:40]}")
            else:
                warn("You are on the last section!")

        elif choice == "7":
            if current > 0:
                current -= 1
                ok(f"Now on Section {current+1}: {sections[current]['title'][:40]}")
            else:
                warn("You are on the first section!")

        elif choice == "8":
            try:
                n = int(input(f"  {Fore.CYAN}Jump to section (1-{total}): {Style.RESET_ALL}").strip())
                if 1 <= n <= total:
                    current = n - 1
                    ok(f"Jumped to Section {n}: {sections[current]['title'][:40]}")
                else:
                    err("Invalid section number.")
            except ValueError:
                err("Please enter a number.")

        elif choice.upper() == "O":
            section("ðŸ“š COURSE OVERVIEW")
            print(overview)
            if DEEPGRAM_KEY:
                speak_text(overview)

        elif choice.upper() == "C":
            section("ðŸ« STARTING 90-MINUTE CLASS MODE")
            class_mode(client, sections, topic, course_title)

        elif choice.upper() == "R" and not boi_mode:
            show_learning_resources(client, topic, title)

        elif choice.upper() == "A" and not boi_mode:
            show_learning_resources(client, topic, "")

        elif choice.upper() == "G":
            section("ðŸ–¨ï¸  GENERATING PDF (ON-DEMAND)")
            _generate_course_pdf_for_topic(topic, course_title, sections)


        elif choice == "0":
            print(f"\n{Fore.GREEN}  âœ… Great session! Keep learning! ðŸŽ“{Style.RESET_ALL}\n")
            break

        else:
            err("Invalid choice.")


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# PDF GENERATION INTEGRATION (generated by ai_learning_system_v4 -> generate_lesson_pdf)
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _sanitize_folder_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", (name or "course").strip())


def _write_lesson_md(lesson_dir: str, class_name: str, teacher: str, date_str: str,
                     course_title: str, sections: list[dict]):
    """Create lessons/<class_name>/lesson.md in the format generate_lesson_pdf.py expects."""
    os.makedirs(lesson_dir, exist_ok=True)
    md_path = os.path.join(lesson_dir, "lesson.md")

    style_hint = (
        "clean modern educational illustration, flat design, soft lighting, "
        "vibrant educational colors, no text or labels"
    )

    lines = []
    lines.append(f"Class: {class_name}")
    lines.append(f"Teacher: {teacher}")
    lines.append(f"Date: {date_str}")
    lines.append("")
    lines.append(f"# {course_title}")
    lines.append("")
    lines.append("What You’ll Learn")
    lines.append("")
    lines.append("This course is structured like premium student workbooks: one idea per page, clear examples, and guided practice.")
    lines.append("")

    for sec in sections:
        sec_title = (sec.get("title") or "Untitled").strip()
        content = (sec.get("content") or "").strip()

        lines.append(f"## {sec_title}")
        lines.append("")
        lines.append("Key Concept: Understand the main idea clearly before moving on.")
        lines.append("")
        lines.append(content)
        lines.append("")
        lines.append("Example: Show a simple worked example that makes the concept concrete.")
        lines.append("")
        lines.append("Output: Write the expected result or final takeaway.")
        lines.append("")
        lines.append("Common Errors: Watch out for the most common mistake students make.")
        lines.append("")
        lines.append("Exercise: Practice the idea with a short challenge.")
        lines.append("")
        img_prompt = f"[Section illustration] {sec_title}. {style_hint}"
        lines.append(f"[IMAGE: {img_prompt}]")
        lines.append("")

    md = "\n".join(lines).strip() + "\n"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md)


def _generate_pdf_for_course(lessons_dir: str, output_dir: str):
    """Call generate_lesson_pdf.py to turn lessons/* into PDFs (blocking)."""

    script_path = os.path.join("C:/Users/Admin/Downloads", "generate_lesson_pdf.py")
    if not os.path.exists(script_path):
        script_path = os.path.join(os.path.dirname(__file__), "generate_lesson_pdf.py")

    cmd = [
        sys.executable,
        script_path,
        "--lessons-dir", lessons_dir,
        "--output-dir", output_dir,
    ]
    info("\nðŸ–¨ï¸  Generating PDF via generate_lesson_pdf.py...")
    subprocess.run(cmd, check=False)


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# MAIN
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def _boi_class_dir_name(course_slug: str, month_number: int, topic_name: str, day: str, class_num: int) -> str:
    safe_topic = _sanitize_folder_name(topic_name)
    safe_day = _sanitize_folder_name(day)
    return f"{course_slug}_m{month_number:02d}_{safe_topic}_{safe_day}_c{class_num:02d}"


def _load_boi_roadmap_frontend_developer() -> dict:
    """Load the roadmap from your BOI RSU curriculum generator.

    We import `CURRICULUM` from lesson.py if present.
    Your `lesson.py` (currently) contains the curriculum map directly.
    """
    # Import locally to avoid hard dependency unless user uses this mode.
    import importlib.util

    lesson_path = os.path.join("C:/Users/Admin/Downloads", "lesson.py")
    if not os.path.exists(lesson_path):
        raise RuntimeError(f"Cannot find lesson.py at: {lesson_path}")

    spec = importlib.util.spec_from_file_location("boi_lesson_module", lesson_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)  # type: ignore

    if not hasattr(module, "CURRICULUM"):
        raise RuntimeError("lesson.py does not define CURRICULUM")

    return getattr(module, "CURRICULUM")


def _generate_lesson_markdown_for_boi_class(lesson_dir: str,
                                            course_title: str,
                                            month_title: str,
                                            topic_name: str,
                                            class_info: dict,
                                            teaching_text: str):
    os.makedirs(lesson_dir, exist_ok=True)
    md_path = os.path.join(lesson_dir, "lesson.md")

    class_num = class_info.get("class", "")
    day = class_info.get("day", "")
    focus = class_info.get("focus", topic_name)

    title = f"{course_title} â€” {topic_name}"

    # Minimal markdown that generate_lesson_pdf.py can parse
    # We will include one image prompt at the top.
    style_hint = "clean modern educational illustration, flat design, soft lighting, vibrant educational colors"
    lines = [
        f"Class: {course_title}",
        f"Teacher: AI Tutor",
        f"Date: {time.strftime('%Y-%m-%d')}",
        "",
        f"# {title}",
        "",
        f"## Today: {topic_name} ({day}, Class {class_num})",
        "",
        f"Focus: {focus}",
        "",
        f"{teaching_text}",
        "",
        f"[IMAGE: {topic_name}. {style_hint} no text or labels]",
        "",
    ]

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main():
    banner()

    # â”€â”€ BOI Curriculum mode (frontend-developer) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # If user sets BOI_FRONTEND_MODE=1, we use your BOI lesson roadmap from lesson.py
    # and generate a single class PDF based on the first scheduled class.
    if os.environ.get("BOI_FRONTEND_MODE", "0") == "1":
        course_slug = "frontend-developer"
        course_title = "Frontend Developer"
        month_title = "Month 1: Web Foundations"

        roadmap = _load_boi_roadmap_frontend_developer()
        months = roadmap.get("monthly_plan", [])
        if not months:
            raise RuntimeError("No monthly_plan found in lesson.py CURRICULUM")

        m = months[0]
        month_number = m.get("month", 1)
        month_title = f"Month {month_number}: {m.get('title','')}"
        topics = m.get("topics", [])
        if not topics:
            raise RuntimeError("No topics found for Month 1")

        topic = topics[0]
        classes = topic.get("classes", [])
        if not classes:
            raise RuntimeError("No classes found for first topic")

        class_info = classes[0]
        topic_name = topic.get("name", "")

        # Create a teacher lesson text for this one class using the focus
        focus = class_info.get("focus", topic_name)
        teaching_text = ai(
            client=setup_ai(),
            prompt=(
                f"Write a 1000-1600 word student lesson note (spoken style) for the BOI RSU class.\n"
                f"Course: {course_title}\n"
                f"{month_title}\n"
                f"Topic: {topic_name}\n"
                f"Day: {class_info.get('day','')} | Class: {class_info.get('class','')}\n"
                f"Today's focus: {focus}\n\n"
                f"Requirements: flowing paragraphs (no markdown/bullets), include clear explanations and examples relevant to Nigeria."
            ),
            max_tokens=2500,
        )

        base_dir = os.path.join(os.path.dirname(__file__), "boi_lessons")
        lessons_dir = base_dir
        output_dir = os.path.join(os.path.dirname(__file__), "boi_output")
        os.makedirs(output_dir, exist_ok=True)

        # Folder name contract for generate_lesson_pdf.py: lessons/<ClassName>/lesson.md
        class_dir_name = _boi_class_dir_name(course_slug, month_number, topic_name, class_info.get('day',''), class_info.get('class',1))
        lesson_dir = os.path.join(lessons_dir, class_dir_name)

        _generate_lesson_markdown_for_boi_class(
            lesson_dir=lesson_dir,
            course_title=course_title,
            month_title=month_title,
            topic_name=topic_name,
            class_info=class_info,
            teaching_text=teaching_text,
        )

        # Generate PDF from lessons/*
        _generate_pdf_for_course(lessons_dir=lessons_dir, output_dir=output_dir)
        ok(f"BOI frontend-developer Month 1 first class PDF generated in: {output_dir}")
        return


    # â”€â”€ Check required keys â”€â”€
    missing = []
    if not NVIDIA_KEY:  missing.append("NVIDIA_API_KEY")
    if not APIFY_TOKEN: missing.append("APIFY_TOKEN")

    if missing:
        err("Missing required environment variables:")
        for m in missing:
            print(f"    export {m}='your-key-here'")
        print(f"""
  {Fore.BLUE}NVIDIA API key : https://build.nvidia.com/nvidia/nemotron-3-super-120b-a12b
  Apify token    : https://console.apify.com/account/integrations{Style.RESET_ALL}
""")
        sys.exit(1)

    if not DEEPGRAM_KEY:
        warn("DEEPGRAM_API_KEY not set â€” voice narration will be disabled.")
        warn("Get a free key: https://console.deepgram.com")
        warn("Set it: export DEEPGRAM_API_KEY='your-key'")
    else:
        ok("Deepgram Aura-2 voice ready!")

    client = setup_ai()
    ok("Nemotron-3-Super (NVIDIA API) ready!")

    # â”€â”€ Topic input â”€â”€
    topic = os.environ.get("AI_LEARNING_TOPIC", "").strip()
    if topic:
        print(f"\n{Fore.CYAN}  Topic from BOI RSU: {topic}{Style.RESET_ALL}\n")
    else:
        print(f"\n{Fore.CYAN}  What topic do you want to learn today?{Style.RESET_ALL}")
        print(f"  Examples: Python, Machine Learning, HTML & CSS, SQL, React, Data Science\n")
        topic = input(f"{Fore.YELLOW}  Topic: {Style.RESET_ALL}").strip() or "Python Programming"

    # â”€â”€ Deep research â”€â”€
    master_notes = deep_research(topic, client)

    # â”€â”€ Build BOI study plan instead of a generic 90-minute course â”€â”€
    duration_months = int(os.environ.get("BOI_STUDY_DURATION_MONTHS", "3"))
    classes_per_week = int(os.environ.get("BOI_CLASSES_PER_WEEK", "3"))
    class_minutes = int(os.environ.get("BOI_CLASS_MINUTES", "60"))
    sections = build_boi_study_plan(
        topic=topic,
        duration_months=duration_months,
        classes_per_week=classes_per_week,
        class_minutes=class_minutes,
        client=client,
    )

    if enrich_course_with_videos is not None:
        try:
            info("Enriching sections with YouTube video recommendations...")
            sections = enrich_course_with_videos(
                topic,
                sections,
                student_level="beginner",
                learning_goal=f"understand {topic}",
                course_context=course_title,
            )
        except Exception as exc:
            warn(f"YouTube enrichment skipped: {exc}")

    if not sections:
        err("Course generation failed. Please try again.")
        return

    course_title = f"{topic} â€” Complete {TOTAL_CLASS_MINUTES}-Minute Course"

    # â”€â”€ Print course outline â”€â”€
    print(f"\n{Fore.GREEN}{'â•'*62}")
    print(f"  ðŸŽ“ YOUR COURSE IS READY: {topic.upper()}")
    print(f"{'â•'*62}{Style.RESET_ALL}")
    total_mins = round(sum(s["duration"] for s in sections), 1)
    print(f"\n  {total_mins} minutes | {len(sections)} sessions | "
          f"{sum(s['word_count'] for s in sections):,} words\n")
    schedule_text = sections[0].get("schedule", "") if sections else ""
    if schedule_text:
        print(f"  {Fore.CYAN}Study Schedule{Style.RESET_ALL}")
        print(schedule_text)
        print()
    for s in sections:
        print(f"  {Fore.YELLOW}[{s['section_num']:>2}]{Style.RESET_ALL} "
              f"{s['title'][:60]:<60} "
              f"{Fore.CYAN}~{s['duration']} min{Style.RESET_ALL}")

    print(f"\n{Fore.GREEN}{'â•'*62}{Style.RESET_ALL}\n")

    # â”€â”€ PDF generation is now manual (only when you request it) â”€â”€
    # This prevents waiting for slow PDF/image generation before you
    # start class mode.


    # â”€â”€ Start learning â”€â”€
    learning_menu(client, sections, topic, course_title, boi_mode=True)



if __name__ == "__main__":
    main()




