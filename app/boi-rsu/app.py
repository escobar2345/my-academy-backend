import os
import sys
from flask import Flask, jsonify, request
from flask_cors import CORS

sys.path.append(os.path.dirname(__file__))

try:
    from youtube import get_boi_course_videos
except Exception as exc:  # pragma: no cover - optional dependency at import time
    get_boi_course_videos = None
    INITIAL_IMPORT_ERROR = str(exc)
else:
    INITIAL_IMPORT_ERROR = None

app = Flask(__name__)
CORS(app)


@app.get("/health")
def health():
    return jsonify({"ok": True, "service": "boi-youtube-api"})


@app.get("/api/videos")
def list_videos():
    topic = (request.args.get("topic") or "").strip()
    if not topic:
        return jsonify({"videos": []})

    if get_boi_course_videos is None:
        return jsonify({"videos": [], "error": INITIAL_IMPORT_ERROR or "youtube helper unavailable"})

    max_results = int(request.args.get("max_results") or 3)
    student_level = (request.args.get("student_level") or "beginner").strip()
    videos = get_boi_course_videos(topic, max_results=max_results, student_level=student_level)
    return jsonify({"topic": topic, "videos": videos})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
