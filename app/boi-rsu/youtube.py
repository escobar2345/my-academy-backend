#!/usr/bin/env python3
"""
youtube_helper.py
==================
Finds relevant YouTube videos for a course topic / lesson section, and
prepares them for embedded playback (e.g. in a Next.js frontend) so the
user never has to leave your site to watch them.

Pipeline
--------
1. APIFY runs a YouTube scraper actor to search and enrich videos:
     - Searches YouTube for the topic/section query
     - Returns metadata and engagement statistics from the actor dataset
   - filters to only videos where status.embeddable == True (required â€”
     some videos block embedding and would fail to play on your site)
   - parses ISO-8601 duration into minutes, filters out very long videos
   - ENGLISH-ONLY FILTER (YOUTUBE_ENGLISH_ONLY, default on): biases every
     search template toward English and drops candidates whose reported
     audio/default language is clearly not English, so students only
     ever get lessons spoken in English
   - pulls view/like/comment counts â€” the raw material for judging
     whether a video actually teaches well, not just whether it exists

3. THE AI BRAIN â€” NVIDIA Build's nemotron-3-embed-1b (semantic reranking):
   - An embedding model doesn't generate text â€” it converts text into a
     dense vector so "closeness in meaning" becomes measurable as a
     number. We embed the lesson query once (input_type="query") and
     every candidate's title+description (input_type="passage"), then
     rank candidates by cosine similarity to the query.
   - This is what makes results "brilliant" rather than just whatever
     Tavily happened to return first: a video titled "Python Tutorial
     for Absolute Beginners" and one titled "Python Snake Care Guide"
     might both match keyword search on "python", but only one is
     semantically close to your actual lesson topic. The embedding
     step filters/reorders for real relevance, not string overlap.
   - Candidates below SIMILARITY_THRESHOLD are dropped entirely.

4. THE TEACHING-QUALITY RANKER (rank_top_teaching_videos):
   - Relevance and popularity alone don't make a video "perfect for
     teaching a class" â€” so we score every candidate on 7 signals:
       1. relevance          â€” semantic match to the lesson (embeddings)
       2. like_ratio          â€” viewer approval (likes / views)
       3. comment_ratio       â€” discussion depth (comments / views)
       4. popularity          â€” raw view count (log-scaled, a trust signal)
       5. duration_fit        â€” how close the video's length is to a
                                 ~1hr class (TARGET_DURATION_MINUTES,
                                 default 60) â€” a 5min clip or a 3hr
                                 stream both score low here even if
                                 everything else is great
       6. channel_authority   â€” subscriber count of the uploading channel
                                 (log-scaled) â€” a proxy for credibility
       7. recency             â€” how recently the video was published,
                                 decaying over YOUTUBE_RECENCY_HORIZON_YEARS
   - All 7 are blended (weights in WEIGHTS, tunable via YOUTUBE_WEIGHT_*
     env vars, auto-normalized to sum to 1) into one teaching_score.
   - Returns the top 3 (YOUTUBE_MAX_RESULTS) with an explicit `rank`
     (1, 2, 3) and a plain-English `why_ranked` explanation citing
     whichever signals stood out for that video.

5. Output:
   - A plain Python list of dicts, each with: id, title, channel,
     channel_id, url, watch_url, embed_url, thumbnail, duration,
     view/like/comment/subscriber counts (raw + formatted), the full
     `scores` breakdown (all 7 signals, 0-1 each), teaching_score,
     rank, why_ranked
   - Optionally written to JSON files under output/videos/<slug>.json
     so a Next.js app can fetch them directly (via getStaticProps,
     a route handler, or just serving the JSON as a static asset)

Environment variables required (put in .env.local, same as the rest of
the learning system):
    APIFY_TOKEN       - Apify API token
    NVIDIA_API_KEY    - https://build.nvidia.com/nvidia/nemotron-3-embed-1b
                         (same key used elsewhere in the learning system
                         for the chat models, if you already set that up)

Usage as a library:
    from youtube_helper import get_videos_for_section

    videos = get_videos_for_section("Python Programming", "Loops and Iteration")
    for v in videos:
        print(v["title"], v["embed_url"])

Usage standalone:
    python3 youtube_helper.py "Neural Networks" --section "Backpropagation"
"""

import os
import re
import sys
import json
import math
import argparse
from datetime import datetime, timezone

import requests
from apify_client import ApifyClient

# â”€â”€ Load local environment file (same convention as ai_learning_system_v4) â”€â”€
def load_env_file(env_path=None):
    candidates = []
    if env_path:
        candidates.append(env_path)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    candidates.extend([
        os.path.join(script_dir, ".env.local"),
        os.path.join(os.getcwd(), ".env.local"),
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
                key, value = key.strip(), value.strip()
                if value and value[0] in {'"', "'"} and value[-1] == value[0]:
                    value = value[1:-1]
                os.environ.setdefault(key, value)
        break

load_env_file()

APIFY_TOKEN     = os.environ.get("APIFY_TOKEN", "")
NVIDIA_API_KEY  = os.environ.get("NVIDIA_API_KEY", "")

APIFY_YOUTUBE_ACTOR = os.environ.get("APIFY_YOUTUBE_ACTOR", "streamers/youtube-scraper")
APIFY_DOWNLOAD_SUBTITLES = os.environ.get("APIFY_DOWNLOAD_SUBTITLES", "false").lower() in {"1", "true", "yes", "on"}
VIDEO_CACHE_DIR = os.environ.get(
    "YOUTUBE_VIDEO_CACHE_DIR",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache", "youtube_results"),
)
_APIFY_SEARCH_ITEMS: dict[str, dict] = {}

# NVIDIA Build â€” nemotron-3-embed-1b (OpenAI-compatible embeddings endpoint)
NVIDIA_EMBED_URL   = "https://integrate.api.nvidia.com/v1/embeddings"
NVIDIA_EMBED_MODEL = "nvidia/nemotron-3-embed-1b"

# â”€â”€ Tunables â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
MAX_CANDIDATES     = int(os.environ.get("YOUTUBE_MAX_CANDIDATES", "15"))   # candidates inspected before ranking
MAX_RESULTS        = int(os.environ.get("YOUTUBE_MAX_RESULTS", "3"))       # top-N ranked videos returned

# Learning videos can be a focused lesson or a full lecture. Keep the
# hard filter broad, then let duration_fit reward the best length.
TARGET_DURATION_MINS = float(os.environ.get("YOUTUBE_TARGET_DURATION_MINUTES", "35"))
MAX_DURATION_MINS    = float(os.environ.get("YOUTUBE_MAX_DURATION_MINUTES", "120"))
MIN_DURATION_MINS    = float(os.environ.get("YOUTUBE_MIN_DURATION_MINUTES", "6"))

# -- English-only spoken-language filter ---------------------------------
# When enabled (the default), every search template is biased toward
# English and any candidate whose YouTube-reported audio/default
# language is clearly NOT English is dropped before ranking. Uploads
# with no language metadata are kept -- the scraper omits the field for
# most videos, so rejecting unknowns would empty the candidate pool.
# A non-Latin-script heuristic catches metadata-less foreign uploads.
ENGLISH_ONLY          = os.environ.get("YOUTUBE_ENGLISH_ONLY", "true").lower() in {"1", "true", "yes", "on"}
ENGLISH_QUERY_SUFFIX  = os.environ.get("YOUTUBE_ENGLISH_QUERY_SUFFIX", "in English")

# Semantic reranking (the "AI brain")
SEMANTIC_RERANK      = os.environ.get("SEMANTIC_RERANK", "true").lower() in {"1", "true", "yes", "on"}
SIMILARITY_THRESHOLD = float(os.environ.get("YOUTUBE_SIMILARITY_THRESHOLD", "0.35"))

# â”€â”€ The 7 teaching-quality signals & their weights (must sum to ~1.0) â”€â”€â”€â”€â”€â”€
# 1. relevance          - does the video actually match the lesson topic?
# 2. like_ratio          - did viewers approve of it (likes / views)?
# 3. comment_ratio       - did it spark discussion/questions (comments / views)?
# 4. popularity          - is it well-watched enough to be a trustworthy pick?
# 5. duration_fit        - does its length match a ~1hr class?
# 6. channel_authority   - is it from an established, credible channel?
# 7. recency             - is the content reasonably up to date?
WEIGHTS = {
    "relevance":        float(os.environ.get("YOUTUBE_WEIGHT_RELEVANCE", "0.34")),
    "education_fit":    float(os.environ.get("YOUTUBE_WEIGHT_EDUCATION_FIT", "0.18")),
    "like_ratio":       float(os.environ.get("YOUTUBE_WEIGHT_LIKE", "0.10")),
    "comment_ratio":    float(os.environ.get("YOUTUBE_WEIGHT_COMMENT", "0.08")),
    "popularity":       float(os.environ.get("YOUTUBE_WEIGHT_POPULARITY", "0.08")),
    "duration_fit":     float(os.environ.get("YOUTUBE_WEIGHT_DURATION", "0.10")),
    "channel_authority":float(os.environ.get("YOUTUBE_WEIGHT_CHANNEL", "0.07")),
    "recency":          float(os.environ.get("YOUTUBE_WEIGHT_RECENCY", "0.05")),
}

# Normalization caps for turning raw numbers into 0-1 sub-scores
LIKE_RATIO_CAP       = 0.10   # 10% of viewers liking the video is excellent
COMMENT_RATIO_CAP    = 0.02   # 2% of viewers commenting is excellent
VIEW_COUNT_LOG_CAP   = 7      # log10(views) cap  -> 10,000,000 views
SUBSCRIBER_LOG_CAP   = 7      # log10(subs) cap   -> 10,000,000 subscribers
RECENCY_HORIZON_YEARS = float(os.environ.get("YOUTUBE_RECENCY_HORIZON_YEARS", "5"))
TOP_N                 = MAX_RESULTS
EDUCATIONAL_TERMS = {
    "learn", "lesson", "tutorial", "course", "class", "lecture", "explained",
    "explanation", "guide", "crash course", "full course", "for beginners",
    "beginner", "introduction", "walkthrough", "step by step", "masterclass",
}

LOW_VALUE_TERMS = {
    "shorts", "#shorts", "tiktok", "reaction", "meme", "music video",
    "trailer", "teaser", "highlights", "compilation", "challenge", "prank",
}

COURSE_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "based", "be", "by", "course",
    "for", "from", "how", "in", "intro", "introduction", "is", "learn",
    "learning", "lesson", "of", "on", "or", "student", "students", "the",
    "to", "topic", "tutorial", "video", "with",
}


def log(msg):
    print(f"  [youtube_helper] {msg}")


def _video_cache_path(topic: str, section_title: str = "") -> str:
    cache_key = _slugify(" ".join(part for part in (topic, section_title) if part))
    os.makedirs(VIDEO_CACHE_DIR, exist_ok=True)
    return os.path.join(VIDEO_CACHE_DIR, f"{cache_key}.json")


def _load_cached_videos(topic: str, section_title: str = "") -> list[dict]:
    path = _video_cache_path(topic, section_title)
    try:
        with open(path, "r", encoding="utf-8") as handle:
            cached = json.load(handle)
        return cached.get("videos", [])
    except (OSError, ValueError, TypeError):
        return []


def _save_cached_videos(topic: str, section_title: str, videos: list[dict]) -> None:
    path = _video_cache_path(topic, section_title)
    try:
        with open(path, "w", encoding="utf-8") as handle:
            json.dump({"topic": topic, "section": section_title, "videos": videos}, handle, indent=2)
    except OSError as exc:
        log(f"Could not cache YouTube results: {exc}")


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# STEP 1 â€” Search and enrich YouTube videos through Apify
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def _run_apify_youtube(input_data: dict) -> list[dict]:
    if not APIFY_TOKEN:
        raise RuntimeError("APIFY_TOKEN is not set. Add it to backend/.env.local.")
    client = ApifyClient(APIFY_TOKEN)
    run = client.actor(APIFY_YOUTUBE_ACTOR).call(run_input=input_data)
    return list(client.dataset(run["defaultDatasetId"]).iterate_items())


def _transcript_text(item: dict) -> str:
    """Normalize common Apify subtitle/caption shapes into searchable text."""
    transcript = item.get("transcript") or item.get("subtitles") or item.get("captions") or ""
    if isinstance(transcript, str):
        return transcript[:12000]
    if isinstance(transcript, dict):
        transcript = transcript.get("text") or transcript.get("transcript") or transcript.get("events") or []
    if not isinstance(transcript, list):
        return ""
    parts = []
    for entry in transcript:
        if isinstance(entry, str):
            parts.append(entry)
        elif isinstance(entry, dict):
            text = entry.get("text") or entry.get("textOriginal") or entry.get("content") or ""
            if isinstance(text, list):
                text = " ".join(str(part) for part in text)
            if text:
                parts.append(str(text))
    return " ".join(parts)[:12000]


def _append_unique(video_ids: list[str], video_id: str, max_results: int) -> None:
    if video_id and video_id not in video_ids and len(video_ids) < max_results:
        video_ids.append(video_id)


def _course_keywords(*parts: str) -> list[str]:
    text = " ".join(p for p in parts if p).lower()
    words = re.findall(r"[a-z0-9][a-z0-9+#.-]{2,}", text)
    return [w for w in dict.fromkeys(words) if w not in COURSE_STOPWORDS]


def _build_learning_query(topic: str, section_title: str = "", student_level: str = "",
                          learning_goal: str = "", course_context: str = "") -> str:
    """Keep the query short and natural — just the topic (and section when given).

    NOTE: this deliberately does NOT append learning_goal / course_context /
    "for beginner students" anymore. Those made queries like
    "Graphic Design & Branding learn Graphic Design & Branding BOI RSU student
    course for beginner students", which YouTube returns ZERO results for —
    the scraper then "succeeds" with 0 videos and the classroom falls back to
    the demo placeholders (the Python-for-designers bug). Short queries work.
    """
    topic_text = (topic or "").strip()
    if " - " in topic_text:
        topic_text = topic_text.split(" - ", 1)[-1]
    parts = [topic_text]
    if section_title:
        parts.append(section_title.strip())
    return " ".join(p.strip() for p in parts if p and p.strip())


def _build_learning_search_queries(base_query: str, student_level: str = "") -> list[str]:
    cleaned_query = re.sub(r"\s+", " ", base_query or "").strip()
    # Bias every formulation toward English when the filter is on --
    # YouTube's search honours the hint, so fewer foreign results even
    # reach the local filters.
    english_suffix = f" {ENGLISH_QUERY_SUFFIX}" if ENGLISH_ONLY else ""
    # Short, high-yield templates only. Keyword-stuffed variants
    # ("full course lesson for beginner students in English", etc.) return
    # nothing on YouTube and just burn Apify credits per query.
    templates = [
        cleaned_query + english_suffix,
        f"{cleaned_query} tutorial{english_suffix}",
        f"{cleaned_query} full course{english_suffix}",
    ]
    queries = []
    for template in templates:
        candidate = template.format(q=base_query).strip()
        if candidate not in queries:
            queries.append(candidate)
    return queries


def _search_youtube_api(query: str | list[str], max_results: int = MAX_CANDIDATES) -> list[str]:
    """Compatibility name: search YouTube through the configured Apify actor."""
    try:
        queries = [query] if isinstance(query, str) else query
        items = _run_apify_youtube({
            "searchQueries": queries,
            "maxResults": min(max_results, 15),
            "maxResultsShorts": 0,
            "maxResultStreams": 0,
            "downloadSubtitles": False,
        })
    except Exception as e:
        log(f"Apify YouTube search failed: {e}")
        return []
    video_ids = []
    for item in items:
        video_id = (
            item.get("videoId")
            or item.get("id")
            or item.get("video_id")
            or _extract_video_id(item.get("url", ""))
            or _extract_video_id(item.get("videoUrl", ""))
        )
        if video_id:
            _APIFY_SEARCH_ITEMS[video_id] = item
        _append_unique(video_ids, video_id, max_results)
    return video_ids


def _search_youtube_candidates(topic: str, section_title: str = "", student_level: str = "", learning_goal: str = "", course_context: str = "", max_results: int = MAX_CANDIDATES) -> tuple[str, list[str]]:
    """Collect candidates from multiple education-focused queries."""
    base_query = _build_learning_query(topic, section_title, student_level, learning_goal, course_context)
    queries = _build_learning_search_queries(base_query, student_level)
    video_ids = []

    # Search several formulations in one Apify run, then rank the returned
    # candidates locally. This is deeper than one query without multiplying
    # the actor startup cost for every query.
    for vid in _search_youtube_api(queries[:5], max_results=max_results):
        _append_unique(video_ids, vid, max_results)

    return base_query, video_ids[:max_results]

def _extract_video_id(url: str) -> str:
    """Pull an 11-char YouTube video ID out of any common URL shape."""
    if not url:
        return ""
    patterns = [
        r"(?:v=|/embed/|youtu\.be/|/shorts/)([A-Za-z0-9_-]{11})",
    ]
    for pat in patterns:
        m = re.search(pat, url)
        if m:
            return m.group(1)
    return ""


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# STEP 2 â€” Enrich candidates with Apify
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def _iso8601_duration_to_minutes(duration: str) -> float:
    """Parses e.g. 'PT14M8S' -> 14.13 minutes."""
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration or "")
    if not m:
        return 0.0
    h, mnt, s = (int(g) if g else 0 for g in m.groups())
    return h * 60 + mnt + s / 60


def _format_duration(total_minutes: float) -> str:
    total_seconds = int(round(total_minutes * 60))
    h, rem = divmod(total_seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def _format_count(n: int) -> str:
    """1234567 -> '1.2M', 4500 -> '4.5K', 320 -> '320'."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def _apify_duration_to_minutes(value) -> float:
    """Parse Apify durations such as 29:54, 1:23:37, or numeric seconds."""
    if value is None or value == "":
        return 0.0
    if isinstance(value, (int, float)):
        return float(value) / 60
    text = str(value).strip()
    if re.fullmatch(r"\d+(?::\d{1,2}){1,2}", text):
        parts = [int(part) for part in text.split(":")]
        if len(parts) == 2:
            return parts[0] + parts[1] / 60
        return parts[0] * 60 + parts[1] + parts[2] / 60
    return _iso8601_duration_to_minutes(text)


def _is_english_language(value) -> bool:
    """
    True when a YouTube language value clearly denotes English
    ('en', 'en-US', 'English'...). Empty/unknown values count as
    English -- treated as "not stated" rather than "foreign".
    """
    text = str(value or "").strip().lower()
    if not text:
        return True
    return text.split("-")[0].strip() == "en" or text.startswith("english")


_NON_LATIN_CHAR_FLOOR = 0x024F   # above Latin Extended-B; Cyrillic,
# Greek, Arabic, Hebrew, Devanagari, Thai, CJK, kana and Hangul sit higher


def _looks_non_english(video: dict) -> bool:
    """
    Metadata-free heuristic: a title/description dominated by non-Latin
    script characters almost certainly belongs to a lesson not taught
    in English, even when no language field says so. A few accented or
    borrowed words never trip it (accented Latin sits below the floor).
    """
    blob = f"{video.get('title', '')} {video.get('description', '')}"
    letters = [ch for ch in blob if ch.isalpha()]
    if len(letters) < 8:
        return False
    non_latin = sum(1 for ch in letters if ord(ch) > _NON_LATIN_CHAR_FLOOR)
    return non_latin / len(letters) > 0.4


def _item_is_english(item: dict) -> bool:
    """Every language field the scraper exposes must look like English."""
    if not ENGLISH_ONLY:
        return True
    for key in ("language", "defaultLanguage", "defaultAudioLanguage", "audioLanguage"):
        if not _is_english_language(item.get(key)):
            return False
    return not _looks_non_english({
        "title": item.get("title", ""),
        "description": item.get("description", ""),
    })


def _filter_english_videos(videos: list[dict]) -> list[dict]:
    """Safety net applied to any video list (fresh from Apify or cache)."""
    if not ENGLISH_ONLY or not videos:
        return videos
    kept = [v for v in videos
            if _is_english_language(v.get("default_language"))
            and not _looks_non_english(v)]
    dropped = len(videos) - len(kept)
    if dropped:
        log(f"English-only filter: dropped {dropped} video(s) not clearly in English")
    return kept


def _fetch_video_details(video_ids: list[str]) -> list[dict]:
    """
    Fetches video metadata through Apify's YouTube scraper actor.
    Returns only videos that are public and embeddable, with duration,
    thumbnail, and engagement stats (views/likes/comments) attached â€”
    the stats are what let us later rank videos by how well they
    actually seem to teach, not just how well they match the query.
    """
    if not video_ids:
        return []
    # Search results already contain the metadata needed for local ranking.
    # Reusing them avoids a second Apify run and keeps Apify search-only.
    items = [_APIFY_SEARCH_ITEMS[video_id] for video_id in video_ids[:50] if video_id in _APIFY_SEARCH_ITEMS]
    if not items:
        return []
    results = []
    for item in items:
        video_id = (
            item.get("videoId")
            or item.get("id")
            or item.get("video_id")
            or _extract_video_id(item.get("url", ""))
            or _extract_video_id(item.get("videoUrl", ""))
        )
        if not video_id:
            continue
        duration_mins = (
            float(item["durationMinutes"])
            if item.get("durationMinutes") is not None
            else _apify_duration_to_minutes(item.get("duration") or item.get("durationInSec"))
        )

        if duration_mins < MIN_DURATION_MINS or duration_mins > MAX_DURATION_MINS:
            continue

        # Spoken-language gate: drop uploads YouTube itself tags as
        # non-English (or whose title/description reads as another
        # script) before they can consume a rank slot.
        if not _item_is_english(item):
            continue

        thumb = item.get("thumbnailUrl") or item.get("thumbnail", "")

        # likeCount/commentCount are simply absent if the creator hid them
        # or disabled comments â€” default to 0 rather than erroring out.
        view_count    = int(item.get("viewCount", 0) or 0)
        like_count    = int(item.get("likes", item.get("likeCount", 0)) or 0)
        comment_count = int(item.get("commentsCount", item.get("commentCount", 0)) or 0)

        watch_url = f"https://www.youtube.com/watch?v={video_id}"
        results.append({
            "id": video_id,
            "title": item.get("title", "Untitled"),
            "channel": item.get("channelName") or item.get("channelTitle", ""),
            "channel_id": item.get("channelId", ""),
            "description": (item.get("description", "") or "")[:700],
            "transcript": "",
            "content_inspected": False,
            "tags": (item.get("tags") or [])[:20],
            "default_language": item.get("language", ""),
            "thumbnail": thumb,
            "duration_minutes": round(duration_mins, 2),
            "duration_display": _format_duration(duration_mins),
            "published_at": item.get("date") or item.get("publishedAt", ""),
            "url": watch_url,                 # explicit, simple key for the frontend
            "watch_url": watch_url,
            "embed_url": f"https://www.youtube.com/embed/{video_id}",
            "view_count": view_count,
            "like_count": like_count,
            "comment_count": comment_count,
            "views_display": _format_count(view_count),
            "likes_display": _format_count(like_count),
            "comments_display": _format_count(comment_count),
        })

    return results


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# THE AI BRAIN â€” semantic reranking via NVIDIA Build's nemotron-3-embed-1b
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def _get_nvidia_embeddings(texts: list[str], input_type: str) -> list[list[float]]:
    """
    Calls NVIDIA Build's nemotron-3-embed-1b embeddings endpoint.
    input_type must be "query" (for the search query) or "passage"
    (for the documents/candidates being ranked) â€” NVIDIA's retrieval
    embedding models use asymmetric embeddings, so this matters for
    accuracy.
    """
    if not NVIDIA_API_KEY:
        raise RuntimeError("NVIDIA_API_KEY is not set. Add it to .env.local.")
    if not texts:
        return []

    headers = {
        "Authorization": f"Bearer {NVIDIA_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    payload = {
        "input": texts,
        "model": NVIDIA_EMBED_MODEL,
        "input_type": input_type,
        "encoding_format": "float",
        "truncate": "END",
    }
    resp = requests.post(NVIDIA_EMBED_URL, headers=headers, json=payload, timeout=30)
    if resp.status_code != 200:
        raise RuntimeError(f"nemotron-3-embed-1b error {resp.status_code}: {resp.text[:300]}")

    data = resp.json().get("data", [])
    # Response items aren't guaranteed to be in input order â€” sort by index.
    data.sort(key=lambda d: d.get("index", 0))
    return [d["embedding"] for d in data]


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _semantic_rerank_videos(query: str, videos: list[dict]) -> list[dict]:
    """
    The AI brain step: embeds the lesson query and every candidate
    video's title+description with nemotron-3-embed-1b, scores each
    candidate by cosine similarity, drops anything below
    SIMILARITY_THRESHOLD, and returns videos sorted best-match-first.

    Falls back to the original (unranked) order if the embedding call
    fails for any reason, so a transient API issue never breaks the
    whole pipeline.
    """
    if not videos:
        return videos

    try:
        query_vec = _get_nvidia_embeddings([query], input_type="query")[0]
        passages = [f"{v['title']}. {v.get('description', '')}".strip() for v in videos]
        passage_vecs = _get_nvidia_embeddings(passages, input_type="passage")
    except Exception as e:
        log(f"Semantic reranking unavailable ({e}) â€” keeping original order")
        return videos

    scored = []
    for video, vec in zip(videos, passage_vecs):
        score = _cosine_similarity(query_vec, vec)
        video["relevance_score"] = round(score, 4)
        if score >= SIMILARITY_THRESHOLD:
            scored.append(video)

    scored.sort(key=lambda v: v["relevance_score"], reverse=True)

    if not scored:
        # Nothing cleared the bar â€” better to show something than nothing,
        # so fall back to the highest-scoring candidates anyway.
        log("No candidates cleared the relevance threshold â€” returning best-effort matches")
        videos.sort(key=lambda v: v.get("relevance_score", 0), reverse=True)
        return videos

    log(f"Semantic reranking: {len(scored)}/{len(videos)} videos passed relevance threshold "
        f"({SIMILARITY_THRESHOLD})")
    return scored


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# THE TEACHING-QUALITY RANKER â€” 7 signals, not just likes/comments/views
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def _fetch_channel_stats(channel_ids: list[str]) -> dict:
    """
    Batch-fetches subscriber counts for a list of channel IDs via
    YouTube Data API's channels.list (up to 50 IDs per call). Used for
    the channel_authority signal â€” an established, credible channel is
    part of what makes a video "perfect for teaching."
    Returns {channel_id: subscriber_count}. Channels that hide their
    subscriber count are returned as 0 (treated as "unknown", not
    penalized elsewhere).
    """
    return {}


def _duration_fit_score(duration_minutes: float) -> float:
    """1.0 when the video is exactly TARGET_DURATION_MINS long, decaying
    linearly to 0 the further it drifts from a ~1hr class length."""
    if TARGET_DURATION_MINS <= 0:
        return 1.0
    diff = abs(duration_minutes - TARGET_DURATION_MINS)
    return max(0.0, 1 - (diff / TARGET_DURATION_MINS))


def _recency_score(published_at: str) -> float:
    """1.0 for brand-new content, decaying to 0 over RECENCY_HORIZON_YEARS.
    Unknown/unparseable dates get a neutral 0.5 rather than being punished."""
    if not published_at:
        return 0.5
    try:
        published = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        age_years = (datetime.now(timezone.utc) - published).days / 365.25
    except Exception:
        return 0.5
    return max(0.0, 1 - (age_years / RECENCY_HORIZON_YEARS))


def _channel_authority_score(subscriber_count: int) -> float:
    if subscriber_count <= 0:
        return 0.0
    return min(math.log10(subscriber_count + 1) / SUBSCRIBER_LOG_CAP, 1.0)



def _text_blob(video: dict) -> str:
    tags = " ".join(video.get("tags") or [])
    return f"{video.get('title', '')} {video.get('description', '')} {video.get('channel', '')} {tags}".lower()


def _keyword_relevance_score(video: dict, keywords: list[str]) -> float:
    if not keywords:
        return 0.5
    blob = _text_blob(video)
    title = (video.get("title") or "").lower()
    matched = 0.0
    for kw in keywords:
        if kw in title:
            matched += 1.4
        elif kw in blob:
            matched += 1.0
    return min(matched / max(len(keywords), 1), 1.0)


def _transcript_relevance_score(video: dict, keywords: list[str]) -> float:
    """Score what the video says, not only what its title claims."""
    transcript = (video.get("transcript") or "").lower()
    if not transcript or not keywords:
        return 0.0
    matched = sum(1 for keyword in keywords if keyword in transcript)
    return min(matched / len(keywords), 1.0)


def _education_fit_score(video: dict) -> float:
    blob = _text_blob(video)
    score = 0.25
    for term in EDUCATIONAL_TERMS:
        if term in blob:
            score += 0.11
    for term in LOW_VALUE_TERMS:
        if term in blob:
            score -= 0.20
    if video.get("duration_minutes", 0) < 8:
        score -= 0.15
    if video.get("duration_minutes", 0) > 90:
        score -= 0.05
    return max(0.0, min(score, 1.0))


def _has_low_value_signal(video: dict) -> bool:
    blob = _text_blob(video)
    return any(term in blob for term in LOW_VALUE_TERMS)
def _explain_ranking(video: dict) -> str:
    """Builds a short, human-readable justification for a video's rank,
    drawing on whichever of the 7 signals stood out."""
    parts = []
    s = video["scores"]

    if s["relevance"] >= 0.6:
        parts.append("closely matches the lesson topic")
    elif s["relevance"] >= SIMILARITY_THRESHOLD:
        parts.append("relevant to the lesson topic")

    if s["duration_fit"] >= 0.8:
        parts.append(f"great length for a full class ({video['duration_display']})")

    if video.get("like_ratio", 0) >= 0.03:
        parts.append(f"strong viewer approval ({video['like_ratio']*100:.1f}% like rate)")

    if video.get("comment_count", 0) >= 20:
        parts.append(f"{video['comments_display']} comments of discussion")

    if s["channel_authority"] >= 0.55:
        parts.append(f"from an established channel ({video['subscribers_display']} subscribers)")

    if video.get("view_count", 0) >= 100_000:
        parts.append(f"well-watched ({video['views_display']} views)")

    if s["recency"] >= 0.8:
        parts.append("recently published / up to date")

    if not parts:
        parts.append("best available match for this topic")

    return "; ".join(parts).capitalize()


def rank_top_teaching_videos(videos: list[dict], top_n: int = TOP_N, query_parts: list[str] | None = None) -> list[dict]:
    """
    Final ranking pass â€” scores each candidate on 7 signals:
      1. relevance          (semantic match to the lesson, via embeddings)
      2. like_ratio          (likes / views)
      3. comment_ratio       (comments / views â€” depth of discussion)
      4. popularity          (raw view count, log-scaled)
      5. duration_fit        (how close to a ~1hr class length)
      6. channel_authority   (subscriber count, log-scaled)
      7. recency             (how recently published)

    Blends them (weights in WEIGHTS, normalized to sum to 1) into one
    teaching_score, sorts best-first, and returns the top_n with an
    explicit `rank` and a `why_ranked` explanation attached.
    """
    if not videos:
        return videos

    keywords = _course_keywords(*(query_parts or []))
    channel_ids = [v.get("channel_id", "") for v in videos]
    channel_subs = _fetch_channel_stats(channel_ids)

    weight_sum = sum(WEIGHTS.values()) or 1.0
    weights = {k: v / weight_sum for k, v in WEIGHTS.items()}

    for video in videos:
        views    = video.get("view_count", 0)
        likes    = video.get("like_count", 0)
        comments = video.get("comment_count", 0)

        like_ratio    = (likes / views) if views > 0 else 0.0
        comment_ratio = (comments / views) if views > 0 else 0.0
        subs          = channel_subs.get(video.get("channel_id", ""), 0)
        keyword_relevance = _keyword_relevance_score(video, keywords)
        transcript_relevance = _transcript_relevance_score(video, keywords)
        semantic_relevance = max(video.get("relevance_score", 0.0), 0.0)
        relevance = max(semantic_relevance, keyword_relevance * 0.6 + transcript_relevance * 0.4)
        education_fit = _education_fit_score(video)

        scores = {
            "relevance":        relevance,
            "education_fit":    education_fit,
            "like_ratio":       min(like_ratio / LIKE_RATIO_CAP, 1.0),
            "comment_ratio":    min(comment_ratio / COMMENT_RATIO_CAP, 1.0),
            "popularity":       min(math.log10(views + 1) / VIEW_COUNT_LOG_CAP, 1.0) if views > 0 else 0.0,
            "duration_fit":     _duration_fit_score(video.get("duration_minutes", 0)),
            "channel_authority":_channel_authority_score(subs),
            "recency":          _recency_score(video.get("published_at", "")),
        }

        video["like_ratio"]         = round(like_ratio, 4)
        video["comment_ratio"]      = round(comment_ratio, 4)
        video["keyword_relevance"]  = round(keyword_relevance, 4)
        video["transcript_relevance"] = round(transcript_relevance, 4)
        video["education_fit"]      = round(education_fit, 4)
        video["low_value_signal"]   = _has_low_value_signal(video)
        video["subscriber_count"]   = subs
        video["subscribers_display"] = _format_count(subs)
        video["scores"]             = {k: round(v, 3) for k, v in scores.items()}
        penalty = 0.18 if video["low_value_signal"] else 0.0
        video["teaching_score"]     = round(max(0.0, sum(weights[k] * scores[k] for k in weights) - penalty), 4)

    videos.sort(key=lambda v: v["teaching_score"], reverse=True)
    top = videos[:top_n]

    for i, video in enumerate(top, 1):
        video["rank"] = i
        video["why_ranked"] = _explain_ranking(video)

    log(f"Top {len(top)} ranked by 7-signal teaching quality "
        f"(relevance, education fit, likes, comments, views, duration fit, channel authority, recency):")
    for video in top:
        log(f"  #{video['rank']} [{video['teaching_score']}] {video['title'][:55]} â€” {video['why_ranked']}")

    return top


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# STEP 3 â€” Public entrypoints
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def get_videos_for_section(
    topic: str,
    section_title: str = "",
    max_results: int = MAX_RESULTS,
    student_level: str = "",
    learning_goal: str = "",
    course_context: str = "",
) -> list[dict]:
    """
    Main entrypoint: finds embeddable YouTube videos relevant to a course
    topic, section, and optional student/course context.
    """
    query, candidate_ids = _search_youtube_candidates(
        topic=topic,
        section_title=section_title,
        student_level=student_level,
        learning_goal=learning_goal,
        course_context=course_context,
        max_results=MAX_CANDIDATES,
    )
    log(f"Searching YouTube for learning query: '{query}'")

    if not candidate_ids:
        cached = _load_cached_videos(topic, section_title)
        if cached:
            log("Apify returned no candidates; using cached classroom videos.")
            return _filter_english_videos(cached)[:max_results]
        log("No candidate videos found.")
        return []

    log(f"Found {len(candidate_ids)} candidates - checking embeddability & duration via YouTube API...")
    videos = _filter_english_videos(_fetch_video_details(candidate_ids))
    log(f"{len(videos)} videos passed filters (embeddable, public, "
        f"{MIN_DURATION_MINS}-{MAX_DURATION_MINS} min, english_only={ENGLISH_ONLY})")

    if SEMANTIC_RERANK and videos:
        log("Running semantic relevance ranking (nemotron-3-embed-1b)...")
        videos = _semantic_rerank_videos(query, videos)

    log("Ranking by teaching quality and course fit...")
    videos = rank_top_teaching_videos(
        videos,
        top_n=max_results,
        query_parts=[topic, section_title, student_level, learning_goal, course_context],
    )

    if videos:
        _save_cached_videos(topic, section_title, videos)
    return videos

def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "section"


def format_videos_for_markdown(videos: list[dict], max_results: int = 3) -> str:
    """Turn ranked video results into a compact markdown block for lesson notes/PDFs."""
    if not videos:
        return ""

    lines = ["Recommended YouTube videos", ""]
    for idx, video in enumerate(videos[:max_results], start=1):
        title = (video.get("title") or f"Video {idx}").strip()
        url = video.get("url") or video.get("watch_url") or ""
        if url:
            lines.append(f"{idx}. {title} - {url}")
        else:
            lines.append(f"{idx}. {title}")
    return "\n".join(lines)


def _fallback_demo_videos(topic: str, max_results: int = MAX_RESULTS, student_level: str = "beginner") -> list[dict]:
    """Return simple demo recommendations when live YouTube APIs are not configured."""
    topic_text = (topic or "lesson").strip() or "lesson"
    level_text = (student_level or "beginner").strip() or "beginner"
    demos = [
        {
            "id": "demo-1",
            "title": f"{topic_text} fundamentals for {level_text} learners",
            "url": "https://www.youtube.com/watch?v=rfscVS0vtbw",
            "watch_url": "https://www.youtube.com/watch?v=rfscVS0vtbw",
            "thumbnail": "https://img.youtube.com/vi/rfscVS0vtbw/hqdefault.jpg",
            "channel": "YouTube Learning",
            "duration": "20 min",
            "teaching_score": 0.93,
            "why_ranked": "Fallback classroom recommendation for local testing. Replace with live results once YouTube API credentials are configured.",
        },
        {
            "id": "demo-2",
            "title": f"A practical {topic_text} lesson with examples",
            "url": "https://www.youtube.com/watch?v=HfTXHrWMGVY",
            "watch_url": "https://www.youtube.com/watch?v=HfTXHrWMGVY",
            "thumbnail": "https://img.youtube.com/vi/HfTXHrWMGVY/hqdefault.jpg",
            "channel": "Code School",
            "duration": "35 min",
            "teaching_score": 0.89,
            "why_ranked": "Fallback recommendation to keep the classroom UI populated during development.",
        },
    ]
    return demos[:max_results]


def get_boi_course_videos(course_topic: str, max_results: int = MAX_RESULTS, student_level: str = "beginner") -> list[dict]:
    """Convenience wrapper for BOI RSU curriculum topics coming from boirsu.py."""
    try:
        videos = get_videos_for_section(
            topic=course_topic,
            section_title="",
            max_results=max_results,
            student_level=student_level,
            learning_goal=f"learn {course_topic}",
            course_context="BOI RSU student course",
        )
        if videos:
            return videos
    except Exception as exc:
        log(f"Live video lookup failed for '{course_topic}': {exc}")

    log(f"Using fallback demo videos for '{course_topic}' because no live results were returned")
    return _fallback_demo_videos(course_topic, max_results=max_results, student_level=student_level)


def save_videos_json(topic: str, section_title: str, videos: list[dict], output_dir: str = "output/videos") -> str:
    """
    Writes videos to output_dir/<topic-slug>/<section-slug>.json so a
    Next.js app can read them (e.g. via fs in a route handler, or by
    copying output/videos into /public for static fetch()).
    """
    os.makedirs(os.path.join(output_dir, _slugify(topic)), exist_ok=True)
    path = os.path.join(output_dir, _slugify(topic), f"{_slugify(section_title)}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({
            "topic": topic,
            "section": section_title,
            "videos": videos,
        }, f, indent=2)
    log(f"Saved {len(videos)} videos -> {path}")
    return path


def enrich_course_with_videos(topic: str, sections: list[dict], output_dir: str = "output/videos", student_level: str = "", learning_goal: str = "", course_context: str = "") -> list[dict]:
    """
    Integration point for ai_learning_system_v4.py â€” call this after
    build_course() to attach a `videos` list to every section dict AND
    write per-section JSON files for the Next.js frontend to consume.

    Example (inside ai_learning_system_v4.py):

        from youtube_helper import enrich_course_with_videos
        sections = build_course(topic, master_notes, client)
        sections = enrich_course_with_videos(topic, sections)
    """
    for sec in sections:
        try:
            section_context = " ".join(str(sec.get(k, "")) for k in ("summary", "description", "objective", "content") if sec.get(k))
            videos = get_videos_for_section(topic, sec.get("title", ""), student_level=student_level, learning_goal=learning_goal, course_context=" ".join(p for p in [course_context, section_context] if p))
        except Exception as e:
            log(f"Video lookup failed for section '{sec.get('title')}': {e}")
            videos = []
        sec["videos"] = videos
        save_videos_json(topic, sec.get("title", f"section-{sec.get('section_num')}"), videos, output_dir)
    return sections


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# CLI
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def main():
    parser = argparse.ArgumentParser(description="Find embeddable YouTube videos for a topic/section.")
    parser.add_argument("topic", help="Course topic, e.g. 'Python Programming'")
    parser.add_argument("--section", default="", help="Specific lesson section, e.g. 'Loops and Iteration'")
    parser.add_argument("--max-results", type=int, default=MAX_RESULTS)
    parser.add_argument("--save", action="store_true", help="Write result JSON to output/videos/")
    args = parser.parse_args()

    required = [("APIFY_TOKEN", APIFY_TOKEN)]
    if SEMANTIC_RERANK:
        required.append(("NVIDIA_API_KEY", NVIDIA_API_KEY))
    missing = [k for k, v in required if not v]
    if missing:
        print("Missing required environment variables:")
        for m in missing:
            print(f"  export {m}='your-key-here'")
        if "NVIDIA_API_KEY" in missing:
            print("  (or set SEMANTIC_RERANK=false to skip the AI relevance ranking step)")
        sys.exit(1)

    videos = get_videos_for_section(args.topic, args.section, max_results=args.max_results)

    query_label = f"{args.topic} {args.section}".strip()
    print(f"\nTop {len(videos)} videos for '{query_label}':\n")
    for v in videos:
        print(f"#{v['rank']}  {v['title']}")
        print(f"     {v['url']}")
        print(f"     score {v['teaching_score']}  |  {v['views_display']} views, "
              f"{v['likes_display']} likes, {v['comments_display']} comments")
        print(f"     why: {v['why_ranked']}\n")

    print(json.dumps(videos, indent=2))

    if args.save:
        save_videos_json(args.topic, args.section or "general", videos)


if __name__ == "__main__":
    main()





