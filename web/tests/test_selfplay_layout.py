import re
import unittest
from pathlib import Path


TEST_HTML = Path(__file__).resolve().parents[1] / "static" / "test.html"


class SelfplayLayoutTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = TEST_HTML.read_text(encoding="utf-8")

    def test_chat_rows_use_full_width_layout(self):
        self.assertRegex(
            self.html,
            r"\.character-row\s*\{[^}]*width:\s*100%",
        )

    def test_bubbles_keep_chinese_phrases_together(self):
        self.assertRegex(
            self.html,
            r"\.bubble\s*\{[^}]*word-break:\s*keep-all",
        )

    def test_short_student_bubbles_have_minimum_width(self):
        self.assertRegex(
            self.html,
            r"\.bubble\.student\s*\{[^}]*min-width:\s*9em",
        )


if __name__ == "__main__":
    unittest.main()
