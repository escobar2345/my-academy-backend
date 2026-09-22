"""
Local web server students connect to (from their own laptop/phone browser,
on the same WiFi/network as the machine running this). One shared session,
one shared chat feed, one AI tutor watching one shared screen + video.

Run via main.py, not directly.
"""

from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit

import config
from ai_tutor import TutorSession

app = Flask(__name__)
app.config["SECRET_KEY"] = "ai-tutor-dev-key"
socketio = SocketIO(app, cors_allowed_origins="*")

session: TutorSession = None  # set by main.py before running the server


@app.route("/")
def index():
    return render_template(
        "index.html",
        video_url=session.video_summary["url"],
        video_title=session.video_summary["metadata"].get("title", "Shared session video"),
    )


@socketio.on("ask_question")
def handle_question(data):
    student_name = (data.get("name") or "Student").strip()[:40]
    question = (data.get("question") or "").strip()
    if not question:
        return

    # Let everyone see the question was asked immediately (feels live),
    # then broadcast the answer once Inkling responds.
    emit("new_message", {"student": student_name, "text": question, "kind": "question"}, broadcast=True)

    answer = session.answer_question(student_name, question)
    emit("new_message", {"student": "AI Tutor", "text": answer, "kind": "answer"}, broadcast=True)


@socketio.on("connect")
def handle_connect():
    emit("new_message", {
        "student": "AI Tutor",
        "text": f"Welcome! I've watched \"{session.video_summary['metadata'].get('title', 'the video')}\" "
                f"end-to-end and I'm watching the shared screen with you. Ask me anything "
                f"about what's been covered so far.",
        "kind": "answer",
    })


def run():
    socketio.run(app, host=config.SERVER_HOST, port=config.SERVER_PORT, allow_unsafe_werkzeug=True)
