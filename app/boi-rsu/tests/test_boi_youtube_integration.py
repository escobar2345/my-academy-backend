import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import boirsu


class BoirsuYoutubeIntegrationTests(unittest.TestCase):
    def test_get_topic_youtube_recommendations_uses_helper(self):
        with patch.object(boirsu, "get_boi_course_videos", return_value=[{"title": "Intro", "url": "https://example.com"}]):
            videos = boirsu.get_topic_youtube_recommendations("HTML Basics", max_results=1)

        self.assertEqual(len(videos), 1)
        self.assertEqual(videos[0]["title"], "Intro")


if __name__ == "__main__":
    unittest.main()
