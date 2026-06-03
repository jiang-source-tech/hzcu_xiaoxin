import unittest
from pathlib import Path


SKILL_MD = Path(__file__).resolve().parents[2] / "skills" / "xiaoxin-senior" / "SKILL.md"


class SkillBoundariesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.skill = SKILL_MD.read_text(encoding="utf-8")

    def test_forbids_unverified_room_and_floor_details(self):
        self.assertIn("不编造楼层、门牌号、基地位置", self.skill)
        self.assertIn("如果知识库没有明确写出位置", self.skill)

    def test_does_not_claim_unverified_lab_exhibit_locations(self):
        self.assertNotIn("学院实验室展厅里还放着往年比赛的车", self.skill)


if __name__ == "__main__":
    unittest.main()
