"""
Central configuration. Reads secrets from environment variables so you never
hardcode keys into the source. Set these before running main.py:

    export NVIDIA_API_KEY="your-nvidia-build-api-key"
    export APIFY_TOKEN="your-apify-token"

On Windows (PowerShell):
    $env:NVIDIA_API_KEY="your-nvidia-build-api-key"
    $env:APIFY_TOKEN="your-apify-token"
"""

import os

NVIDIA_API_KEY = os.environ.get("NVIDIA_API_KEY", "")
APIFY_TOKEN = os.environ.get("APIFY_TOKEN", "")

NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
MODEL_NAME = "thinkingmachines/inkling"

# How often the screen watcher takes a screenshot (seconds).
# Lower = more real-time, but more API calls/cost. 3-5s is a good default.
SCREEN_CAPTURE_INTERVAL_SECONDS = 4

# Max width screenshots are resized to before sending to the model
# (keeps payloads small and calls fast; Inkling doesn't need full-res).
SCREENSHOT_MAX_WIDTH = 1024

# Local web server settings (this is what students connect to)
SERVER_HOST = "0.0.0.0"   # 0.0.0.0 = reachable by other devices on your LAN
SERVER_PORT = 5000

# --- Video download & pre-processing settings ---
# Where downloaded videos, extracted frames, and cached summaries live.
VIDEO_CACHE_DIR = "video_cache"

# Cap download resolution to keep this fast and light (480p is plenty for
# reading slides/code on screen; bump up if the video has fine detail).
VIDEO_MAX_HEIGHT = 480

# Extract one frame every N seconds of video to build the "watched" timeline.
# Lower = more accurate visual coverage but more Inkling vision calls (cost/time)
# during preprocessing. 15s is a reasonable default for lecture-style content.
VIDEO_FRAME_INTERVAL_SECONDS = 15
