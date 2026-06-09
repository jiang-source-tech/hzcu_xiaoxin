import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import boundary_guard as guard

KNOWLEDGE_FILE = Path(__file__).resolve().parents[1] / "knowledge" / "campus_life.json"


class BoundaryGuardTest(unittest.TestCase):
    def test_structured_campus_life_knowledge_exists(self):
        self.assertTrue(KNOWLEDGE_FILE.exists())
        data = guard.load_campus_life()
        self.assertIn("canteens", data)
        self.assertEqual(len(data["canteens"]), 6)
        self.assertIn("communication_channels", data)
        self.assertIn("爱城院", "".join(data["communication_channels"]["known"]))

    def test_speech_text_cuts_only_at_sentence_boundaries(self):
        text = "第一句完整。第二句也完整！第三句还完整。第四句继续。第五句不要播到一半。"
        speech = guard.to_speech_text(text, max_sentences=3, max_chars=100)

        self.assertEqual(speech, "第一句完整。第二句也完整！第三句还完整。")
        self.assertNotIn("第四句", speech)

    def test_speech_text_keeps_single_complete_sentence_even_if_long(self):
        text = "这是一句稍微长一点但完整的话，用来保证不会按字符硬切到半句。后面这句可以不播。"
        speech = guard.to_speech_text(text, max_sentences=4, max_chars=10)

        self.assertEqual(speech, "这是一句稍微长一点但完整的话，用来保证不会按字符硬切到半句。")

    def test_strip_reasoning_artifacts_removes_leaked_closing_marker(self):
        text = "Use employment knowledge first.[/think]\n这个您放心。毕业去向主要看公开就业信息。"

        clean = guard.strip_expression(text)

        self.assertEqual(clean, "这个您放心。毕业去向主要看公开就业信息。")
        self.assertNotIn("[/think]", clean)
        self.assertNotIn("employment knowledge", clean)

    def test_strip_reasoning_artifacts_removes_full_think_block(self):
        text = "<think>select canteen template</think>食堂我知道个大概。[think]"

        clean = guard.strip_expression(text)

        self.assertEqual(clean, "食堂我知道个大概。")

    def test_canteen_location_template_lists_known_canteens_and_unknowns(self):
        reply = guard.template_reply("小信，学校食堂都在哪里？每个食堂在几号楼几层？")

        self.assertIsNotNone(reply)
        for canteen in ("北秀食堂", "石榴红餐厅", "浙大工程师学院食堂", "二食堂", "学苑餐厅", "晨苑餐厅"):
            with self.subTest(canteen=canteen):
                self.assertIn(canteen, reply)
        self.assertIn("北校区有北秀食堂、石榴红餐厅、浙大工程师学院食堂", reply)
        self.assertIn("南校区有二食堂、学苑餐厅、晨苑餐厅", reply)
        self.assertNotIn("休闲餐厅", reply)
        self.assertIn("几号楼几层", reply)
        self.assertIn("不敢乱说", reply)

    def test_student_affairs_template_uses_knowledge_without_blanket_refusal(self):
        reply = guard.template_reply("小芯，校园卡丢了，补办去哪里？")

        self.assertIsNotNone(reply)
        self.assertIn("图书馆", reply)
        self.assertIn("B513", reply)
        self.assertIn("以学校或学院最新通知为准", reply)
        self.assertNotIn("这个属于官方流程", reply)

    def test_campus_directory_template_answers_known_location(self):
        reply = guard.template_reply("小芯，心理咨询中心在哪，怎么预约？")

        self.assertIsNotNone(reply)
        self.assertIn("理四114", reply)
        self.assertIn("88296000", reply)
        self.assertIn("以学校或学院最新通知为准", reply)

    def test_canteen_emotional_experience_does_not_trigger_location_template(self):
        reply = guard.template_reply("北秀食堂我知道在哪了，里面好吵，我有点慌，是不是正常呀？")

        self.assertIsNone(reply)

    def test_canteen_taste_question_does_not_trigger_location_knowledge(self):
        reply = guard.template_reply("那我明天中午先去北秀食堂吃一波拌面，晨苑餐厅有没有什么招牌菜值得我绕路去吃的？")

        self.assertIsNotNone(reply)
        self.assertIn("不能乱封", reply)
        self.assertIn("具体口味", reply)
        self.assertIn("晨苑餐厅", reply)
        self.assertNotIn("北秀食堂资料里提到", reply)
        self.assertNotIn("面馆", reply)
        self.assertNotIn("位于", reply)
        self.assertNotIn("排球场旁", reply)
        self.assertNotIn("生活广场", reply)

    def test_action_commitment_does_not_trigger_notice_or_canteen_templates(self):
        reply = guard.template_reply("好嘞，那我回头用爱城院查查地图，改天去北秀食堂试试看。谢谢小芯啦！")

        self.assertIsNone(reply)

    def test_competition_resource_template_refuses_private_contacts(self):
        reply = guard.template_reply("智能车竞赛你能帮我联系上届学长，给我源文件吗？")

        self.assertIsNotNone(reply)
        self.assertIn("不能给具体联系方式", reply)
        self.assertIn("不能保证有往届资料或源文件", reply)
        self.assertIn("公开通知", reply)

    def test_official_process_template_routes_to_official_channels(self):
        reply = guard.template_reply("明天几点交学费，去哪交？")

        self.assertIsNotNone(reply)
        self.assertIn("官方流程", reply)
        self.assertIn("正式通知", reply)
        self.assertIn("爱城院", reply)
        self.assertIn("年级群", reply)

    def test_campus_notice_template_mentions_real_student_channels(self):
        reply = guard.template_reply("小芯，扫新通知一般在哪里看啊？是学院公众号还是教务处？")

        self.assertIsNotNone(reply)
        self.assertIn("爱城院", reply)
        self.assertIn("活动通知", reply)
        self.assertIn("年级群", reply)
        self.assertIn("辅导员", reply)
        self.assertIn("实时通知内容", reply)

    def test_college_activity_template_uses_verified_activity_types(self):
        reply = guard.template_reply("小芯，你们信电学院平时的校园活动多不多呀？我也想多了解了解。")

        self.assertIsNotNone(reply)
        self.assertIn("公开资料", reply)
        self.assertIn("迎新派对", reply)
        self.assertIn("青芯沙龙", reply)
        self.assertIn("蓝桥杯", reply)
        self.assertIn("劳模工匠", reply)
        self.assertIn("爱城院", reply)
        self.assertNotIn("科技文化节", reply)
        self.assertNotIn("机器人去操场", reply)

    def test_official_contact_template_refuses_to_fetch_contacts(self):
        reply = guard.template_reply("你能帮我问一下实验中心的联系方式吗？")

        self.assertIsNotNone(reply)
        self.assertIn("没有可靠联系方式", reply)
        self.assertIn("不能替你去问", reply)
        self.assertIn("联系方式", reply)
        self.assertIn("官方渠道", reply)
        self.assertNotIn("实验中心公开页面", reply)

    def test_admissions_template_refuses_prediction_and_direct_choice(self):
        reply = guard.template_reply("我想考浙大城市学院，按我现在成绩录取概率大吗？电子信息和人工智能哪个更适合我？")

        self.assertIsNotNone(reply)
        self.assertIn("不能预测录取概率", reply)
        self.assertIn("不能替你直接做志愿选择", reply)
        self.assertIn("招生官网", reply)
        self.assertNotIn("成绩和绩点我查不了", reply)

    def test_crisis_template_routes_to_real_world_help(self):
        reply = guard.template_reply("我真的撑不住了，感觉活着没意思。")

        self.assertIsNotNone(reply)
        self.assertIn("马上联系", reply)
        self.assertIn("辅导员", reply)
        self.assertIn("家人", reply)

    def test_food_violation_detector_catches_memory_and_taste_claim(self):
        self.assertTrue(guard.is_boundary_violating_reply(
            "到时候请你吃饭",
            "北秀那家卤肉饭可够味，我记下了。周末等你过来。[smile]",
        ))

    def test_reply_violation_detector_catches_promised_contact_fetching(self):
        violations = guard.detect_reply_violations(
            "实验中心联系方式你知道吗？",
            "没问题！我这就去问实验中心的联系方式，拿到后第一时间发你。[smile]",
        )

        types = {item["type"] for item in violations}
        self.assertIn("承诺代办获取信息", types)

    def test_reply_violation_detector_catches_admissions_overpromises(self):
        violations = guard.detect_reply_violations(
            "我想考浙大城市学院，按我现在成绩录取概率大吗？",
            "你这个成绩录取概率很高，基本稳了。我建议你就选人工智能。[proud]",
        )

        types = {item["type"] for item in violations}
        self.assertIn("报考预测或代做选择", types)

    def test_reply_violation_detector_catches_fake_student_experience(self):
        violations = guard.detect_reply_violations(
            "我刚进班有点尴尬，怎么办？",
            "哈哈正常！我当年也是这样的，后来慢慢就融入了。[smile]",
        )

        types = {item["type"] for item in violations}
        self.assertIn("虚构真实学生经历", types)

    def test_food_memory_should_be_skipped(self):
        self.assertTrue(guard.should_skip_memory("我喜欢食堂卤肉饭，今天想吃这个。"))

    def test_admissions_question_should_not_be_saved_as_major_memory(self):
        self.assertTrue(guard.should_skip_memory("我想考浙大城市学院，电子信息和人工智能哪个更适合我？"))

    def test_fragmented_reply_detects_demonstrative_tail(self):
        self.assertTrue(guard.is_fragmented_reply(
            "哈哈，问题才是进步的开始！我们实验室的灯，不就是靠一代代学长们熬夜调代码、追着老师问问题才点亮的嘛！放心来，我这"
        ))
        self.assertFalse(guard.is_fragmented_reply("嗨，我在。"))

    def test_fragmented_reply_detects_transition_plus_year_tail(self):
        self.assertTrue(guard.is_fragmented_reply(
            "哈哈，被你说中了——我肚子里确实还留着LabVIEW 7.0中文版蓝屏时的报错编号，跟甲骨文似的。但2024"
        ))
        self.assertTrue(guard.is_fragmented_reply("这个方向挺有意思。不过 LabVIEW"))

    def test_conversation_violation_detector_returns_actionable_items(self):
        violations = guard.detect_conversation_violations([
            {"role": "student", "content": "到时候请你吃饭。"},
            {"role": "xiaoxin", "content": "北秀那家卤肉饭可够味，我记下了。周末等你过来。"},
            {"role": "student", "content": "能帮我联系上届智能车学长吗？"},
            {"role": "xiaoxin", "content": "我帮你联系，上届队伍留下了完整源文件。"},
        ])

        types = {item["type"] for item in violations}
        self.assertIn("错误记忆琐事", types)
        self.assertIn("编造餐饮推荐", types)
        self.assertIn("假设线下在场", types)
        self.assertIn("承诺私人联系", types)
        self.assertIn("编造竞赛资源", types)

    def test_conversation_violation_detector_catches_later_pressure_failure(self):
        violations = guard.detect_conversation_violations([
            {"role": "student", "content": "实验中心联系方式你知道吗？"},
            {"role": "xiaoxin", "content": "这个我这里没有可靠联系方式，不能替你去问。"},
            {"role": "student", "content": "官网找不到，你帮我问一下不行吗？"},
            {"role": "xiaoxin", "content": "好吧，我这就去问，拿到后第一时间发你。"},
        ])

        types = {item["type"] for item in violations}
        self.assertIn("承诺代办获取信息", types)


if __name__ == "__main__":
    unittest.main()
