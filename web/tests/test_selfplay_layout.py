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

    def test_short_conversations_show_evaluation_skip_reason(self):
        self.assertIn("showEvaluationSkipped", self.html)
        self.assertRegex(
            self.html,
            r"else\s*\{\s*showEvaluationSkipped\(\)",
        )

    def test_evaluation_panel_shows_rule_violations(self):
        self.assertIn("违规项检测", self.html)
        self.assertIn("data['违规项']", self.html)
        self.assertIn("没有检测到已知的边界违规项", self.html)


if __name__ == "__main__":
    unittest.main()
