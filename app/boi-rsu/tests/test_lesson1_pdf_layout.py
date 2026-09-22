import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock
import unittest

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import lesson1


class Lesson1PdfLayoutTests(unittest.TestCase):
    def test_header_footer_draws_a_page_image_when_available(self):
        canvas = Mock()
        doc = Mock(page=3)

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            image_path = tmp.name

        try:
            Image.new("RGB", (200, 100), color="blue").save(image_path)
            lesson1.header_footer(canvas, doc, "Biology Class", image_path)

            self.assertTrue(canvas.drawImage.called)
            args, kwargs = canvas.drawImage.call_args
            self.assertEqual(args[0], image_path)
            self.assertGreater(kwargs["width"], 0)
            self.assertGreater(kwargs["height"], 0)
        finally:
            Path(image_path).unlink(missing_ok=True)

    def test_parse_lesson_file_recognizes_workbook_callouts(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            lesson_path = Path(tmp_dir) / "lesson.md"
            lesson_path.write_text(
                "## Topic\n\nKey Concept: Understand the idea\nExercise: Try it yourself\n",
                encoding="utf-8",
            )

            lesson = lesson1.parse_lesson_file(lesson_path)

            self.assertTrue(any(block.kind == "callout" for block in lesson.blocks))


if __name__ == "__main__":
    unittest.main()
