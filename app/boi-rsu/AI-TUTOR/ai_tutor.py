"""
The tutoring brain. Combines:
  - the full video summary (transcript + visual notes per segment), sliced
    down to only what's been "watched" so far based on elapsed time
  - what's currently visible on the student's own screen (separate from the
    video - their code editor, notes, quiz app, etc), via the live screen
    watcher
into a system prompt, then answers student questions or generates a
comprehension-check question of its own.

Session is shared: any student's question is answered with the same shared
context, and everyone in the room sees the same Q&A feed (handled by server.py).
"""

import time

import video_processor
from ai_client import ask_inkling
from screen_watcher import ScreenWatcher


class TutorSession:
    def __init__(self, video_url: str, on_progress=None):
        # Full start-to-end processing happens up front: download, extract
        # frames, pair with transcript, describe each segment. This is the
        # "watch the whole video" step.
        self.video_summary = video_processor.build_video_summary(video_url, on_progress=on_progress)

        self.start_time = time.time()
        self.watcher = ScreenWatcher()  # watches the STUDENT's own screen, separate from the video
        self.watcher.start()
        self.chat_log = []  # [{"student": str, "question": str, "answer": str, "t": float}]

    def elapsed_seconds(self) -> float:
        """
        Best-effort guess at video progress: wall-clock time since the session
        started, assuming the video plays roughly in real time alongside the
        session. Not exact sync - if students pause/skip, this can drift.
        """
        return time.time() - self.start_time

    def _build_system_prompt(self) -> str:
        elapsed = self.elapsed_seconds()
        segments = video_processor.segments_up_to(self.video_summary, elapsed)
        title = self.video_summary["metadata"].get("title", "Unknown title")

        watched_so_far = "\n".join(
            f"[{s['start']}s-{s['end']}s] {s['transcript']} "
            f"(visual: {s['visual_note']})"
            for s in segments
        )
        recent_segments = segments[-3:]  # roughly the last ~45s at default interval
        recent_text = "\n".join(
            f"[{s['start']}s-{s['end']}s] {s['transcript']} (visual: {s['visual_note']})"
            for s in recent_segments
        )

        return f"""You are a patient, encouraging AI tutor who has watched this video
end-to-end alongside a group of students in a shared session.

VIDEO: {title}
URL: {self.video_summary['url']}
Approx. time into video: {int(elapsed)}s

WHAT'S BEEN WATCHED SO FAR (transcript + visual notes per segment - do not
discuss anything beyond this, the students haven't reached it yet):
\"\"\"{watched_so_far[-6000:] if watched_so_far else "(nothing watched yet)"}\"\"\"

MOST RECENT SEGMENTS (use this for "what did they just cover" questions):
\"\"\"{recent_text}\"\"\"

WHAT'S CURRENTLY VISIBLE ON THE STUDENT'S OWN SCREEN (separate from the video
- e.g. their code editor, notes, or quiz app):
\"\"\"{self.watcher.latest_description}\"\"\"

Rules:
- Only answer using what has been covered so far in the video (above), plus
  what's visible on the student's screen. Don't spoil later parts of the video.
- If a student asks about something not yet covered, tell them it hasn't come
  up yet and, if you can, roughly when it might.
- Keep answers concise and clear, like a helpful classmate, not a lecture.
- Use the visual notes when a question is about something shown on screen in
  the video (a diagram, code, slide) rather than just spoken.
"""

    def answer_question(self, student_name: str, question: str) -> str:
        system_prompt = self._build_system_prompt()
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"{student_name} asks: {question}"},
        ]
        answer = ask_inkling(messages)
        entry = {
            "student": student_name,
            "question": question,
            "answer": answer,
            "t": time.time(),
        }
        self.chat_log.append(entry)
        return answer

    def generate_check_in_question(self) -> str:
        """AI proactively asks the group a comprehension question about what just played."""
        system_prompt = self._build_system_prompt()
        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    "Based only on what's been covered so far, ask the group ONE short "
                    "comprehension-check question to see if they're following along."
                ),
            },
        ]
        question = ask_inkling(messages, temperature=0.8, max_tokens=150)
        self.chat_log.append({
            "student": "AI Tutor",
            "question": None,
            "answer": question,
            "t": time.time(),
        })
        return question

    def stop(self):
        self.watcher.stop()
