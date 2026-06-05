import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class RelationshipV2PageTest(unittest.TestCase):
    def setUp(self):
        self.html = (ROOT / "static" / "relationship-v2-test.html").read_text(
            encoding="utf-8"
        )
        self.app_py = (ROOT / "app.py").read_text(encoding="utf-8")

    def test_relationship_test_is_the_only_relationship_replay_route(self):
        relationship_route = re.search(
            r'@app\.route\("/relationship-test"\).*?send_static_file\("([^"]+)"\)',
            self.app_py,
            re.S,
        )
        v2_route = re.search(
            r'@app\.route\("/relationship-v2-test"\)',
            self.app_py,
        )

        self.assertIsNotNone(relationship_route)
        self.assertIsNone(v2_route)
        self.assertEqual(relationship_route.group(1), "relationship-v2-test.html")

    def test_page_centers_daily_llm_replay(self):
        expected_snippets = [
            "每日 LLM 对话回放",
            "用户 LLM",
            "小信 LLM",
            "state-strip",
            "renderViolation",
        ]

        for snippet in expected_snippets:
            with self.subTest(snippet=snippet):
                self.assertIn(snippet, self.html)

    def test_stage_mismatch_shows_expected_and_actual_values(self):
        self.assertIn("期望阶段", self.html)
        self.assertIn("实际阶段", self.html)
        self.assertIn("formatViolationDetail", self.html)


if __name__ == "__main__":
    unittest.main()
