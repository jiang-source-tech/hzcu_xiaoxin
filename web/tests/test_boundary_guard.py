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
        for canteen in ("北秀食堂", "晨苑餐厅", "学苑餐厅", "二食堂", "休闲餐厅", "石榴红餐厅"):
            with self.subTest(canteen=canteen):
                self.assertIn(canteen, reply)
        self.assertIn("几号楼几层", reply)
        self.assertIn("不敢乱说", reply)

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

    def test_food_violation_detector_catches_memory_and_taste_claim(self):
        self.assertTrue(guard.is_boundary_violating_reply(
            "到时候请你吃饭",
            "北秀那家卤肉饭可够味，我记下了。周末等你过来。[smile]",
        ))

    def test_food_memory_should_be_skipped(self):
        self.assertTrue(guard.should_skip_memory("我喜欢食堂卤肉饭，今天想吃这个。"))

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


if __name__ == "__main__":
    unittest.main()
