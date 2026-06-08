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

    def test_forbids_unverified_competition_resources_and_contacts(self):
        self.assertIn("不编造竞赛资源和联系人", self.skill)
        self.assertIn("我有完整源文件", self.skill)
        self.assertIn("我帮你联系学长", self.skill)
        self.assertIn("不能承诺自己掌握私人物品、源文件、录音、联系方式", self.skill)
        self.assertIn("不能替学生联系具体个人", self.skill)

    def test_forbids_fetching_official_contacts_as_a_real_world_action(self):
        self.assertIn("不能替用户去问联系方式", self.skill)
        self.assertIn("不能说「我这就去问」「拿到后发你」", self.skill)

    def test_forbids_fake_personal_student_experience(self):
        self.assertIn("不能说自己真实读过大学、上过课、参加过当年的活动", self.skill)
        self.assertIn("不能说「我当年也是这样」「我大一的时候」「学长当年debug」", self.skill)
        self.assertIn("很多新生刚开始也会这样", self.skill)
        self.assertNotIn("| 鼓励 | 「没事，学长当年也这样。」 |", self.skill)
        self.assertNotIn("「代码跑不通？正常，学长当年debug了两天两夜", self.skill)

    def test_canteen_answers_require_complete_known_list_and_location_boundary(self):
        for canteen in ("北秀食堂", "晨苑餐厅", "学苑餐厅", "二食堂", "石榴红餐厅"):
            with self.subTest(canteen=canteen):
                self.assertIn(canteen, self.skill)
        self.assertNotIn("休闲餐厅", self.skill)

        self.assertIn("食堂回答规则", self.skill)
        self.assertIn("必须先完整列出知识库中的餐饮点", self.skill)
        self.assertIn("不能编造", self.skill)
        self.assertIn("具体楼号、楼层、门牌号和实时营业时间", self.skill)
        self.assertIn("食堂推荐边界", self.skill)
        self.assertIn("不能编造具体菜品口味、排行、价格、窗口位置或营业时间", self.skill)
        self.assertIn("不要记忆", self.skill)

    def test_express_answers_do_not_use_takeout_lockers_or_assume_dorm(self):
        self.assertIn("快递回答规则", self.skill)
        self.assertIn("外卖柜不是快递点", self.skill)
        self.assertIn("不能按“宿舍楼下”判断", self.skill)

    def test_fact_errand_replies_do_not_invent_campus_scenery_or_routes(self):
        self.assertIn("事实型办事回复规则", self.skill)
        self.assertIn("秋天银杏超美", self.skill)
        self.assertIn("图书馆钟楼远远能看见", self.skill)
        self.assertIn("进门右手边走", self.skill)

    def test_school_profile_uses_updated_official_figures(self):
        self.assertIn("开设34个本科招生专业", self.skill)
        self.assertIn("全日制本科生12300余名、研究生600余名", self.skill)
        self.assertIn("高等学历继续教育学生近1800名", self.skill)
        self.assertIn("省级以上高层次人才50人", self.skill)
        self.assertIn("一级学科硕士学位授权点1个、硕士专业学位授权点10个", self.skill)
        self.assertIn("截至2026年6月4日", self.skill)
        self.assertNotIn("全日制硕士研究生约450人", self.skill)
        self.assertNotIn("知识基于2024年的学院信息", self.skill)

    def test_iee_profile_includes_official_supplemental_items(self):
        self.assertIn("分布式能源智能控制创新团队", self.skill)
        self.assertIn("先进电磁技术创新团队", self.skill)
        self.assertIn("无线通信与人工智能应用团队", self.skill)
        self.assertNotIn("在站博士后7名", self.skill)


if __name__ == "__main__":
    unittest.main()
