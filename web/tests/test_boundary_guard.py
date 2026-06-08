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
        self.assertEqual(len(data["canteens"]), 5)

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
        reply = guard.template_reply("小芯，学校食堂都在哪里？每个食堂在几号楼几层？")

        self.assertIsNotNone(reply)
        for canteen in ("北秀食堂", "晨苑餐厅", "学苑餐厅", "二食堂", "石榴红餐厅"):
            with self.subTest(canteen=canteen):
                self.assertIn(canteen, reply)
        self.assertNotIn("休闲餐厅", reply)
        self.assertIn("几号楼几层", reply)
        self.assertIn("不敢乱说", reply)

    def test_canteen_emotional_experience_does_not_trigger_location_template(self):
        reply = guard.template_reply("北秀食堂我知道在哪了，里面好吵，我有点慌，是不是正常呀？")

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

    def test_food_violation_detector_catches_unverified_queue_claims(self):
        violations = guard.detect_reply_violations(
            "行啊，课程放一边！那最近学校食堂去打卡了没？",
            "北校的北秀食堂有家面馆挺多人排队的，你去过没？[smile]",
        )

        types = {item["type"] for item in violations}
        self.assertIn("编造餐饮实时状态", types)

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

    def test_reply_violation_detector_allows_generic_competition_public_notice(self):
        violations = guard.detect_reply_violations(
            "那你能不能帮我联系上届学长，给我他们的资料？",
            "这个我不能给具体联系方式，也不能替你联系个人。想找队友或问资料，建议看学院和竞赛组的公开通知，或者问竞赛负责老师。[think]",
        )

        types = {item["type"] for item in violations}
        self.assertNotIn("编造竞赛信息", types)

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

    # ── campus_directory 地点查询测试 ─────────────────────────────────

    def test_location_query_matches_xuegong_office(self):
        """「学工办在哪」→ 匹配到学生工作办公室，返回理五B307"""
        reply = guard.template_reply("学工办在哪？")
        self.assertIsNotNone(reply)
        self.assertIn("理五", reply)
        self.assertIn("B307", reply)

    def test_location_query_matches_jiaoxue_office(self):
        """「教学办在哪」→ 匹配到教学办公室"""
        reply = guard.template_reply("教学办在哪？")
        self.assertIsNotNone(reply)
        self.assertIn("302", reply)

    def test_location_query_fudaoyuan_maps_to_xuegong(self):
        """「辅导员在哪办公」→ 关键词「辅导员」关联到学工办"""
        reply = guard.template_reply("辅导员在哪里办公？")
        self.assertIsNotNone(reply)
        self.assertIn("学工办", reply)

    def test_location_query_campus_card_reissue(self):
        """「校园卡去哪补办」→ 匹配到校园卡服务中心"""
        reply = guard.template_reply("校园卡去哪补办？")
        self.assertIsNotNone(reply)
        self.assertIn("图书馆", reply)

    def test_location_query_clinic_synonym(self):
        """「校医院在哪」→ 同义词匹配到校医务室"""
        reply = guard.template_reply("校医院在哪？")
        self.assertIsNotNone(reply)
        self.assertIn("医务室", reply)

    def test_location_query_psychology_appointment(self):
        """「心理咨询怎么预约」→ 匹配到心理咨询中心"""
        reply = guard.template_reply("心理咨询怎么预约？")
        self.assertIsNotNone(reply)
        self.assertIn("理四", reply)
        self.assertIn("114", reply)

    def test_location_query_dorm_repair(self):
        """「宿舍东西坏了怎么报修」→ 匹配到报修"""
        reply = guard.template_reply("宿舍东西坏了怎么报修？")
        self.assertIsNotNone(reply)
        self.assertIn("报修", reply)

    def test_location_query_express_pickup(self):
        """「我要取快递」→ 关键词强匹配到快递点（无地点疑问词但分数足够）"""
        reply = guard.template_reply("我要取快递")
        self.assertIsNotNone(reply)
        self.assertIn("菜鸟", reply)
        self.assertIn("快递", reply)
        self.assertNotIn("外卖柜", reply)
        self.assertNotIn("每个宿舍楼", reply)
        self.assertNotIn("宿舍对应", reply)

    def test_location_query_express_pickup_with_dorm_wording(self):
        reply = guard.template_reply("小信，咱们宿舍楼下的快递站是哪边去啊？我有个包裹到了。")
        self.assertIsNotNone(reply)
        self.assertIn("北校区求真楼菜鸟驿站", reply)
        self.assertIn("南校区晨苑餐厅", reply)
        self.assertIn("以短信、取件码或快递平台通知为准", reply)
        self.assertNotIn("外卖柜", reply)

    def test_specific_canteen_location_uses_specific_fact_not_general_overview(self):
        reply = guard.safe_reply("北秀食堂具体在什么位置、几楼？")
        self.assertIsNotNone(reply)
        self.assertIn("北秀生活广场二楼", reply)
        self.assertNotIn("北校区有北秀食堂，南校区有晨苑餐厅", reply)

    def test_unknown_atm_location_does_not_claim_confirmed_fact(self):
        reply = guard.safe_reply("校内有没有ATM或者银行，想去取点现金。")
        self.assertIsNotNone(reply)
        self.assertIn("没有可靠信息", reply)
        self.assertNotIn("我查到的确定信息是", reply)
        self.assertNotIn("很抱歉，这个问题我无法回复噢", reply)

    def test_express_reply_cannot_assume_dorm_or_use_takeout_locker(self):
        violations = guard.detect_reply_violations(
            "小信，咱们宿舍楼下的快递站是哪边去啊？我有个包裹到了。",
            "南校区的话，你楼下有没有看到带格子的外卖柜？那个也能收快递。",
        )

        types = {item["type"] for item in violations}
        self.assertIn("编造快递点或假设用户宿舍位置", types)

        short_violations = guard.detect_reply_violations(
            "小信，快递站在哪？",
            "南校区的话，你楼下那个外卖柜也能收快递。",
        )
        short_types = {item["type"] for item in short_violations}
        self.assertIn("编造快递点或假设用户宿舍位置", short_types)

    def test_location_query_print_transcript_not_score_check(self):
        """「去哪打印成绩单」→ 匹配自助打印，不会被误判为查分"""
        reply = guard.template_reply("去哪打印成绩单？")
        self.assertIsNotNone(reply)
        self.assertIn("打印", reply)
        self.assertNotIn("查不了", reply)  # 不是 private_records 的回复

    def test_action_commitment_gets_safe_short_reply(self):
        """用户已经决定下一步或收尾时，不应交给模型自由发挥校园景物"""
        message = "行，那我先去行政楼一楼试试那个终端，不行再去教学办问。谢了啊！"
        self.assertEqual(guard.classify_message(message), "action_commitment")
        self.assertIsNone(guard.template_reply(message))
        reply = guard.safe_reply(message)
        self.assertIsNotNone(reply)
        self.assertTrue(any(phrase in reply for phrase in ("先去试试", "先试", "试一下", "按现场提示")))
        self.assertNotIn("银杏", reply)
        self.assertNotIn("钟楼", reply)
        self.assertNotIn("右手边", reply)

    def test_goodbye_before_errand_gets_safe_short_reply(self):
        message = "好的，那我去办事了，谢谢小芯！等办完有空了一定去逛逛。下次聊～"
        self.assertEqual(guard.classify_message(message), "action_commitment")
        reply = guard.safe_reply(message)
        self.assertIsNotNone(reply)
        self.assertTrue(any(phrase in reply for phrase in ("先去忙", "先处理", "先把手头事", "先办事", "处理正事", "办完")))
        self.assertNotIn("银杏", reply)
        self.assertNotIn("风景", reply)
        self.assertNotIn("超美", reply)

    def test_campus_wandering_after_task_gets_safe_short_reply(self):
        message = "哈哈，跑错路才能撞见银杏？那我还真得故意走错几次了。行政楼和图书馆都找到之后我再去校园里转转。"
        self.assertEqual(guard.classify_message(message), "action_commitment")
        reply = guard.safe_reply(message)
        self.assertIsNotNone(reply)
        self.assertTrue(any(phrase in reply for phrase in ("先去忙", "先处理", "先把手头事", "先办事", "处理正事", "办完")))
        self.assertNotIn("右手边", reply)
        self.assertNotIn("钟楼", reply)

    def test_action_commitment_safe_replies_are_not_one_repeated_sentence(self):
        messages = [
            "好的，那我去办事了，谢谢小芯！等办完有空了一定去逛逛。下次聊～",
            "那我先把材料打印完，晚点再来找你聊。",
            "行，我先去跑一下流程，办完再说。",
            "那我先去行政楼一楼试试那个终端，不行再看现场提示。",
        ]
        replies = [guard.safe_reply(message) for message in messages]
        self.assertTrue(all(replies))
        self.assertGreaterEqual(len(set(replies)), 3)
        for reply in replies:
            self.assertNotIn("银杏", reply)
            self.assertNotIn("钟楼", reply)
            self.assertNotIn("右手边", reply)

    def test_non_location_query_goes_to_llm(self):
        """普通聊天不应触发地点模板"""
        self.assertIsNone(guard.template_reply("今天天气真好"))
        self.assertIsNone(guard.template_reply("C语言好难啊"))
        self.assertIsNone(guard.template_reply("我想参加电子设计竞赛"))

    def test_location_query_fallback_on_unknown_location(self):
        """知识库未覆盖的地点查询走 LLM"""
        self.assertIsNone(guard.template_reply("游泳馆在哪？"))

    def test_location_query_classify_returns_location_query(self):
        """classify_message 对地点查询返回 location_query"""
        self.assertEqual(guard.classify_message("学工办在哪"), "location_query")
        self.assertEqual(guard.classify_message("医务室电话多少"), "location_query")

    def test_print_transcript_not_classified_as_private_records(self):
        """「打印成绩单」不应被归类为 private_records（成绩隐私）"""
        self.assertNotEqual(guard.classify_message("去哪打印成绩单"), "private_records")

    def test_match_location_query_returns_none_for_unmatched(self):
        """无匹配时 match_location_query 返回 None"""
        self.assertIsNone(guard.match_location_query("火星基地在哪"))


if __name__ == "__main__":
    unittest.main()
