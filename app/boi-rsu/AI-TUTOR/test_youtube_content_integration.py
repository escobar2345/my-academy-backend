import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import youtube_content


def test_resolve_video_source_uses_boi_recommendation(monkeypatch):
    def fake_get_boi_course_videos(topic, max_results=3, student_level="beginner"):
        return [{
            "id": "abc12345678",
            "title": "Python tutorial",
            "url": "https://www.youtube.com/watch?v=abc12345678",
            "watch_url": "https://www.youtube.com/watch?v=abc12345678",
            "thumbnail": "https://img.youtube.com/vi/abc12345678/hqdefault.jpg",
            "channel": "Example Channel",
        }]

    monkeypatch.setattr(youtube_content, "get_boi_course_videos", fake_get_boi_course_videos)

    result = youtube_content.resolve_video_source("Python Programming", student_level="beginner")

    assert result["content_source"]["type"] == "boi_rsu_recommendation"
    assert result["video_id"] == "abc12345678"
    assert result["content_source"]["topic"] == "Python Programming"
