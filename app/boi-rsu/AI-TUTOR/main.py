"""
Entry point.

Usage:
    export NVIDIA_API_KEY="your-key"
    export APIFY_TOKEN="your-apify-token"
    python main.py "https://www.youtube.com/watch?v=XXXXXXXXXXX"

Then have students on the same network open:
    http://<this-computer's-LAN-IP>:5000
in their browser.
"""

import sys

import config
import server
import youtube_content
from ai_tutor import TutorSession


def main():
    if len(sys.argv) < 2:
        print("Usage: python main.py <youtube-url-or-topic>")
        sys.exit(1)

    if not config.NVIDIA_API_KEY:
        print("ERROR: set NVIDIA_API_KEY first, e.g.\n  export NVIDIA_API_KEY=your-key")
        sys.exit(1)

    source_input = sys.argv[1]
    print(f"Resolving video source from: {source_input}")
    source = youtube_content.resolve_video_source(source_input)
    video_url = source["url"]
    print(f"Using video: {video_url}")
    print("Watching the full video end-to-end before opening the session "
          "(downloading, extracting frames, pairing with transcript)...\n")

    tutor_session = TutorSession(video_url, on_progress=lambda msg: print(f"  {msg}"))

    total_segments = len(tutor_session.video_summary["segments"])
    print(f"\nFinished watching - {total_segments} segments processed.")

    print("Screen watcher started for the student's own screen (capturing every "
          f"{config.SCREEN_CAPTURE_INTERVAL_SECONDS}s).")

    server.session = tutor_session

    print(f"\nStudents can join at: http://<your-lan-ip>:{config.SERVER_PORT}")
    print(f"(Locally: http://localhost:{config.SERVER_PORT})\n")

    try:
        server.run()
    finally:
        tutor_session.stop()


if __name__ == "__main__":
    main()
