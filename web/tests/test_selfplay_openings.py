import re
import unittest
from pathlib import Path


TEST_HTML = Path(__file__).resolve().parents[1] / "static" / "test.html"


class SelfplayOpeningsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = TEST_HTML.read_text(encoding="utf-8")

    def test_persona_specific_openings_exist_for_non_xindian_roles(self):
        self.assertIn("const personaOpenings = {", self.html)
        self.assertRegex(
            self.html,
            r"'非信电学生':\s*'[^']*商学院[^']*'",
        )
        self.assertRegex(
            self.html,
            r"'非信电学生':\s*'[^']*(?!电子信息工程)[^']*'",
        )

    def test_test_page_uses_role_only(self):
        self.assertNotIn('id="scenarioSelect"', self.html)
        self.assertNotIn("const scenarioOpenings", self.html)
        self.assertNotIn("选择场景和角色", self.html)
        self.assertIn("选择角色，点「开始」", self.html)

    def test_opening_selector_uses_persona_only(self):
        self.assertRegex(
            self.html,
            r"function getOpeningMessage\(persona\)\s*\{[\s\S]*personaOpenings\[persona\]",
        )
        self.assertIn("currentMessage = getOpeningMessage(persona);", self.html)

    def test_frontend_stops_when_student_reply_is_empty(self):
        self.assertIn("新生这轮没有生成有效回复，已停止本次测试", self.html)
        self.assertRegex(
            self.html,
            r"if \(data\.student && data\.student\.content\)[\s\S]*else\s*\{[\s\S]*break;",
        )


if __name__ == "__main__":
    unittest.main()
