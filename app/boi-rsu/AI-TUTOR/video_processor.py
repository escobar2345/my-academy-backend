"""
Downloads a YouTube video, extracts frames at regular intervals, and builds
a full start-to-end "watched" summary by pairing each frame with its matching
transcript window and asking Inkling to note anything visually important.

This is what lets the tutor actually have watched the whole video beginning
to end before students start asking questions, rather than only knowing
audio/transcript content.

Everything is cached to disk under config.VIDEO_CACHE_DIR/<video_id>/, so
re-running on the same video is instant after the first pass.

Note: downloading YouTube videos this way uses yt-dlp, a widely-used open
source tool. It's a grey area under YouTube's Terms of Service - fine for
personal/educational use, but worth knowing it isn't officially sanctioned.
"""

import base64
import io
import json
import os
import subprocess

import yt_dlp
from PIL import Image

import config
import youtube_content
from ai_client import ask_inkling_with_image


def _video_dir(video_id: str) -> str:
    path = os.path.join(config.VIDEO_CACHE_DIR, video_id)
    os.makedirs(path, exist_ok=True)
    return path


def download_video(video_id: str) -> str:
    """Downloads the video (capped resolution) if not already cached. Returns local file path."""
    out_dir = _video_dir(video_id)
    video_path = os.path.join(out_dir, "video.mp4")
    if os.path.exists(video_path):
        return video_path

    ydl_opts = {
        "format": (
            f"bestvideo[height<={config.VIDEO_MAX_HEIGHT}]+bestaudio/"
            f"best[height<={config.VIDEO_MAX_HEIGHT}]"
        ),
        "outtmpl": video_path,
        "merge_output_format": "mp4",
        "quiet": True,
        "no_warnings": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([f"https://www.youtube.com/watch?v={video_id}"])

    return video_path


def extract_frames(video_path: str, video_id: str, interval_seconds: int = None) -> list[dict]:
    """Extracts one frame every `interval_seconds` via ffmpeg. Returns [{"time": t, "path": p}, ...]."""
    interval_seconds = interval_seconds or config.VIDEO_FRAME_INTERVAL_SECONDS
    frames_dir = os.path.join(_video_dir(video_id), "frames")
    os.makedirs(frames_dir, exist_ok=True)

    existing = sorted(f for f in os.listdir(frames_dir) if f.endswith(".jpg"))
    if existing:
        return [
            {"time": i * interval_seconds, "path": os.path.join(frames_dir, name)}
            for i, name in enumerate(existing)
        ]

    pattern = os.path.join(frames_dir, "frame_%06d.jpg")
    subprocess.run(
        ["ffmpeg", "-i", video_path, "-vf", f"fps=1/{interval_seconds}", "-q:v", "4", pattern],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    names = sorted(f for f in os.listdir(frames_dir) if f.endswith(".jpg"))
    return [
        {"time": i * interval_seconds, "path": os.path.join(frames_dir, name)}
        for i, name in enumerate(names)
    ]


def _encode_frame_b64(path: str) -> str:
    img = Image.open(path).convert("RGB")
    if img.width > config.SCREENSHOT_MAX_WIDTH:
        ratio = config.SCREENSHOT_MAX_WIDTH / img.width
        img = img.resize((config.SCREENSHOT_MAX_WIDTH, int(img.height * ratio)))
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=75)
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def build_video_summary(video_url: str, on_progress=None) -> dict:
    """
    Full pipeline: download -> extract transcript -> extract frames ->
    describe each segment (transcript text + matching frame). Cached to disk
    so re-running on the same video is instant.

    `on_progress(str)` is called with human-readable status updates, useful
    for printing progress to the console while a long video processes.
    """
    video_id = youtube_content.extract_video_id(video_url)
    out_dir = _video_dir(video_id)
    summary_path = os.path.join(out_dir, "summary.json")
    if os.path.exists(summary_path):
        if on_progress:
            on_progress("Found cached summary, skipping reprocessing.")
        with open(summary_path) as f:
            return json.load(f)

    metadata = youtube_content.fetch_metadata(video_id)

    if on_progress:
        on_progress("Fetching transcript...")
    try:
        transcript = youtube_content.fetch_transcript(video_id)
    except Exception as e:
        transcript = []
        print(f"[warning] No transcript available: {e}")

    if on_progress:
        on_progress("Downloading video (this can take a while for long videos)...")
    video_path = download_video(video_id)

    if on_progress:
        on_progress("Extracting frames...")
    frames = extract_frames(video_path, video_id)

    segments = []
    for i, frame in enumerate(frames):
        t_start = frame["time"]
        t_end = (
            frames[i + 1]["time"] if i + 1 < len(frames)
            else t_start + config.VIDEO_FRAME_INTERVAL_SECONDS
        )
        segment_text = " ".join(
            seg["text"] for seg in transcript if t_start <= seg["start"] < t_end
        )

        if on_progress:
            on_progress(f"Watching {t_start}s-{t_end}s  ({i + 1}/{len(frames)} segments)")

        try:
            frame_b64 = _encode_frame_b64(frame["path"])
            visual_note = ask_inkling_with_image(
                prompt=(
                    "This is a frame from an educational video at this point in the "
                    "timeline. In one short sentence, note anything visually important "
                    "(slide text, diagram, code, on-screen demo) that isn't already "
                    "obvious from narration alone. If nothing visually notable, say "
                    "'no key visuals'."
                ),
                image_b64=frame_b64,
            )
        except Exception as e:
            visual_note = f"[frame description unavailable: {e}]"

        segments.append({
            "start": t_start,
            "end": t_end,
            "transcript": segment_text,
            "visual_note": visual_note,
        })

    summary = {
        "video_id": video_id,
        "url": f"https://www.youtube.com/watch?v={video_id}",
        "metadata": metadata,
        "segments": segments,
        "total_duration": segments[-1]["end"] if segments else None,
    }

    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)

    if on_progress:
        on_progress(f"Done - fully watched, {len(segments)} segments processed.")

    return summary


def segments_up_to(summary: dict, seconds_elapsed: float) -> list[dict]:
    """All segments the tutor has 'seen' so far given elapsed time into the video."""
    return [s for s in summary["segments"] if s["start"] <= seconds_elapsed]
