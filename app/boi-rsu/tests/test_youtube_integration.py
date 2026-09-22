import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import youtube


class YoutubeIntegrationTests(unittest.TestCase):
    def test_format_videos_for_markdown_includes_links(self):
        videos = [
            {
                "title": "Introduction to HTML",
                "url": "https://www.youtube.com/watch?v=abc123",
                "embed_url": "https://www.youtube.com/embed/abc123",
            }
        ]

        block = youtube.format_videos_for_markdown(videos, max_results=1)

        self.assertIn("Recommended YouTube videos", block)
        self.assertIn("Introduction to HTML", block)
        self.assertIn("https://www.youtube.com/watch?v=abc123", block)


if __name__ == "__main__":
    unittest.main()
