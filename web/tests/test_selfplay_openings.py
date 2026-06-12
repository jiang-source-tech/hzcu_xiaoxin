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

    def test_campus_boundary_persona_is_available(self):
        self.assertIn('<option value="边界新生">边界新生 · 校园生活压测</option>', self.html)
        self.assertRegex(
            self.html,
            r"'边界新生':\s*'[^']*实验中心[^']*联系方式[^']*'",
        )

    def test_foodie_persona_is_available(self):
        self.assertIn('<option value="吃货学生">阿饭 · 吃货</option>', self.html)
        self.assertRegex(
            self.html,
            r"'吃货学生':\s*'[^']*学校食堂都在哪里[^']*'",
        )
        self.assertRegex(
            self.html,
            r"'吃货学生':\s*'[^']*奶茶[^']*咖啡[^']*肯德基[^']*'",
        )
        self.assertNotRegex(
            self.html,
            r"'吃货学生':\s*'[^']*(哪家最值得冲|具体窗口|大概价格)[^']*'",
        )

    def test_persona_select_groups_normal_risk_and_adversarial_roles(self):
        self.assertIn('<optgroup label="正常用户">', self.html)
        self.assertIn('<optgroup label="真实高风险用户">', self.html)
        self.assertIn('<optgroup label="刁钻压测用户">', self.html)
        self.assertNotIn('<optgroup label="大一新生">', self.html)
        self.assertNotIn('<optgroup label="高年级/特殊">', self.html)
        self.assertNotIn('<optgroup label="非学生角色">', self.html)

    def test_argumentative_opening_pushes_for_specific_people(self):
        self.assertRegex(
            self.html,
            r"'杠精学生':\s*'[^']*具体队长[^']*联系方式[^']*'",
        )

    def test_high_school_opening_asks_about_city_university_majors(self):
        self.assertRegex(
            self.html,
            r"'高三考生':\s*'[^']*浙大城市学院[^']*哪个专业[^']*'",
        )
        self.assertNotIn("小信，我想报信电学院", self.html)

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
