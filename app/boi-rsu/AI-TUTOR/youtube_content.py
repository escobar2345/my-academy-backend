"""
Pulls what we can know about a YouTube video WITHOUT downloading it:

    1. Metadata (title, channel, duration) via the configured Apify YouTube actor.

  2. Full timestamped transcript/captions via `youtube-transcript-api`.
     This works for any video that has captions (auto-generated or manual)
     and does NOT require downloading the video or even an API key.

The transcript is what lets the AI actually know "what is being taught" at
any point in the video, without ever touching video frames. Visual context
comes separately from the screen watcher while the video plays.
"""

import os
import re
import sys
import requests
from apify_client import ApifyClient
from youtube_transcript_api import YouTubeTranscriptApi

import config

# Allow the AI tutor to reach the BOI RSU youtube helper even when run from
# the AI-TUTOR folder.
BOI_RSU_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if BOI_RSU_ROOT not in sys.path:
    sys.path.insert(0, BOI_RSU_ROOT)

try:
    from youtube import get_boi_course_videos
except Exception:  # pragma: no cover - optional dependency at import time
    get_boi_course_videos = None


def extract_video_id(url_or_id: str) -> str:
    """Accepts a full YouTube URL or a bare video ID and returns the video ID."""
    patterns = [
        r"(?:v=|\/)([0-9A-Za-z_-]{11}).*",
        r"youtu\.be\/([0-9A-Za-z_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url_or_id)
        if match:
            return match.group(1)
    if re.fullmatch(r"[0-9A-Za-z_-]{11}", url_or_id):
        return url_or_id
    raise ValueError(f"Could not extract a video ID from: {url_or_id}")


def fetch_metadata(video_id: str) -> dict:
    """Fetch title/channel/duration through Apify. Returns {} if unavailable."""
    if not config.APIFY_TOKEN:
        return {}
    actor_id = os.environ.get("APIFY_YOUTUBE_ACTOR", "streamers/youtube-scraper")
    client = ApifyClient(config.APIFY_TOKEN)
    run = client.actor(actor_id).call(
        run_input={"startUrls": [{"url": f"https://www.youtube.com/watch?v={video_id}"}]}
    )
    items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
    if not items:
        return {}

    item = items[0]
    return {
        "title": item.get("title", ""),
        "channel": item.get("channelName") or item.get("channelTitle", ""),
        "description": item.get("description", ""),
        "duration_iso8601": item.get("duration", ""),
    }


def fetch_transcript(video_id: str) -> list[dict]:
    """
    Returns a list of {"start": float_seconds, "duration": float, "text": str}
    covering the whole video, in order. Raises if no captions exist.
    """
    transcript = YouTubeTranscriptApi().fetch(video_id)
    return [
        {"start": snippet.start, "duration": snippet.duration, "text": snippet.text}
        for snippet in transcript
    ]


def transcript_up_to(transcript: list[dict], seconds_elapsed: float) -> str:
    """
    Collapses all transcript lines spoken up to `seconds_elapsed` into one
    block of text — this is "how much of the video the AI has watched so far".
    """
    lines = [seg["text"] for seg in transcript if seg["start"] <= seconds_elapsed]
    return " ".join(lines)


def transcript_window(transcript: list[dict], seconds_elapsed: float, back_seconds: float = 30.0) -> str:
    """Just the last `back_seconds` of dialogue — useful for 'what did they just say'."""
    lines = [
        seg["text"] for seg in transcript
        if seconds_elapsed - back_seconds <= seg["start"] <= seconds_elapsed
    ]
    return " ".join(lines)


def resolve_video_source(topic_or_url: str, student_level: str = "beginner") -> dict:
    """
    Resolve a YouTube source for the AI tutor.

    If the input looks like a direct YouTube URL or video ID, use it directly.
    Otherwise, ask the BOI RSU youtube helper for ranked recommendations for
    the given topic and return the top candidate as the tutor source.
    """
    cleaned = (topic_or_url or "").strip()
    if not cleaned:
        raise ValueError("A YouTube URL or a topic is required")

    if cleaned.startswith(("http://", "https://", "youtu.be/")) or re.fullmatch(r"[0-9A-Za-z_-]{11}", cleaned):
        video_id = extract_video_id(cleaned)
        return {
            "video_id": video_id,
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "content_source": {
                "type": "direct_url",
                "value": cleaned,
            },
        }

    if get_boi_course_videos is not None:
        videos = get_boi_course_videos(cleaned, max_results=1, student_level=student_level)
        if videos:
            first = videos[0]
            video_url = first.get("watch_url") or first.get("url") or ""
            video_id = extract_video_id(video_url) if video_url else ""
            return {
                "video_id": video_id,
                "url": video_url,
                "content_source": {
                    "type": "boi_rsu_recommendation",
                    "topic": cleaned,
                    "student_level": student_level,
                    "source_title": first.get("title"),
                },
            }

    raise ValueError(f"Could not resolve a video source from: {topic_or_url}")


def load_video(url_or_id: str) -> dict:
    """Convenience: fetch everything we can about a video in one call."""
    video_id = extract_video_id(url_or_id)
    metadata = fetch_metadata(video_id)
    try:
        transcript = fetch_transcript(video_id)
    except Exception as e:
        transcript = []
        print(f"[warning] No transcript available for {video_id}: {e}")

    return {
        "video_id": video_id,
        "url": f"https://www.youtube.com/watch?v={video_id}",
        "metadata": metadata,
        "transcript": transcript,
        "total_duration": transcript[-1]["start"] + transcript[-1]["duration"] if transcript else None,
    }
