import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import youtube


def test_get_boi_course_videos_falls_back_to_demo(monkeypatch):
    monkeypatch.setattr(youtube, "get_videos_for_section", lambda **kwargs: [])

    videos = youtube.get_boi_course_videos(
        "Python Programming",
        max_results=2,
        student_level="beginner",
    )

    assert videos
    assert videos[0]["title"].startswith("Python Programming")
