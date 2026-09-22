"""
Captures the screen at a regular interval and asks Inkling to describe what's
on it. This is what lets the tutor "see" the YouTube video playing (since we
never download the video itself) as well as anything else the student does
on screen (their code editor, notes, quiz app, etc).

Runs in a background thread. The latest description is kept in
`ScreenWatcher.latest_description` for the tutor to read at any time.
"""

import base64
import io
import threading
import time

import mss
from PIL import Image

import config
from ai_client import ask_inkling_with_image


class ScreenWatcher:
    def __init__(self, interval_seconds: float = None):
        self.interval_seconds = interval_seconds or config.SCREEN_CAPTURE_INTERVAL_SECONDS
        self.latest_description = "No screen captured yet."
        self.latest_image_b64 = None
        self._stop_event = threading.Event()
        self._thread = None

    def _capture_screenshot_b64(self) -> str:
        with mss.mss() as sct:
            monitor = sct.monitors[1]  # primary monitor
            raw = sct.grab(monitor)
            img = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")

            # Resize down to keep payload small / calls fast
            if img.width > config.SCREENSHOT_MAX_WIDTH:
                ratio = config.SCREENSHOT_MAX_WIDTH / img.width
                img = img.resize((config.SCREENSHOT_MAX_WIDTH, int(img.height * ratio)))

            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=70)
            return base64.b64encode(buffer.getvalue()).decode("utf-8")

    def _loop(self):
        while not self._stop_event.is_set():
            try:
                image_b64 = self._capture_screenshot_b64()
                self.latest_image_b64 = image_b64
                description = ask_inkling_with_image(
                    prompt=(
                        "Briefly describe what is currently visible on this screen "
                        "in 1-3 sentences. If a YouTube video is playing, mention "
                        "the visible timestamp/progress bar position if you can see it, "
                        "and what's on screen (slide, code, diagram, etc)."
                    ),
                    image_b64=image_b64,
                )
                self.latest_description = description
            except Exception as e:
                self.latest_description = f"[screen capture error: {e}]"

            self._stop_event.wait(self.interval_seconds)

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2)
