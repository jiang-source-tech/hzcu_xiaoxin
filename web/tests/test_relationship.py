import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import relationship_state
import turn_analyzer


class TurnAnalyzerTest(unittest.TestCase):
    def test_prospective_anxiety_about_course_rhythm_gets_light_hook(self):
        result = turn_analyzer.analyze("信电会不会很难，我怕跟不上。")

        self.assertIn(result["stage_signal"], {"prospective", "pre_enrollment"})
        self.assertNotEqual(result["stage_signal"], "early_freshman")
        self.assertEqual(result["mood"], "anxious")
        self.assertEqual(result["topic"], "course_rhythm")
        self.assertTrue(result["memory_worthy"])
        self.assertEqual(result["memory_type"], "concern")
        self.assertEqual(result["memory_content"], "担心信电课程跟不上")
        self.assertEqual(result["next_hook"], {
            "topic": "course_rhythm",
            "label": "课程节奏",
            "active": True,
        })
        self.assertIn("reply_strategy", result)
        self.assertNotIn("下次", str(result["next_hook"]))

    def test_early_freshman_stage_signal_when_user_says_school_started(self):
        result = turn_analyzer.analyze("我已经开学了，第一周课好多，有点顶不住。")

        self.assertEqual(result["stage_signal"], "early_freshman")
        self.assertEqual(result["mood"], "anxious")
        self.assertEqual(result["topic"], "course_rhythm")
        self.assertIn("reply_strategy", result)

    def test_hypothetical_first_week_question_keeps_prospective_stage(self):
        result = turn_analyzer.analyze(
            "那如果开学后第一周上课就听不懂怎么办啊，我还没开学，有点担心。"
        )

        self.assertIn(result["stage_signal"], {"prospective", "pre_enrollment"})
        self.assertNotEqual(result["stage_signal"], "early_freshman")
        self.assertEqual(result["mood"], "anxious")
        self.assertEqual(result["topic"], "course_rhythm")

    def test_refusing_topic_deactivates_current_hook(self):
        current_state = {
            "next_hook": {
                "topic": "course_rhythm",
                "label": "课程节奏",
                "active": True,
            }
        }

        result = turn_analyzer.analyze("别聊课程了，烦。", current_state)

        self.assertEqual(result["mood"], "frustrated")
        self.assertEqual(result["topic"], "general_checkin")
        self.assertFalse(result["next_hook"]["active"])
        self.assertIn("reply_strategy", result)

    def test_refusal_preserves_existing_stage_signal(self):
        current_state = {
            "user_stage": "early_freshman",
            "next_hook": {
                "topic": "course_rhythm",
                "label": "课程节奏",
                "active": True,
            }
        }

        result = turn_analyzer.analyze("别聊了。", current_state)

        self.assertEqual(result["stage_signal"], "early_freshman")
        self.assertEqual(result["topic"], "general_checkin")
        self.assertFalse(result["next_hook"]["active"])
        self.assertIn("reply_strategy", result)

    def test_neutral_no_topic_preserves_existing_hook(self):
        current_state = {
            "user_stage": "early_freshman",
            "next_hook": {
                "topic": "course_rhythm",
                "label": "课程节奏",
                "active": True,
            }
        }

        result = turn_analyzer.analyze("嗯嗯", current_state)

        self.assertEqual(result["stage_signal"], "early_freshman")
        self.assertEqual(result["topic"], "general_checkin")
        self.assertEqual(result["next_hook"], current_state["next_hook"])
        self.assertIn("reply_strategy", result)

    def test_topic_labels_match_relationship_plan(self):
        self.assertEqual(turn_analyzer.TOPIC_LABELS["major_choice"], "专业理解")
        self.assertEqual(turn_analyzer.TOPIC_LABELS["social_adaptation"], "人际适应")
        self.assertEqual(turn_analyzer.TOPIC_LABELS["family_concern"], "家长沟通")
        self.assertEqual(turn_analyzer.TOPIC_LABELS["general_checkin"], "近况")

    def test_news_report_does_not_regress_early_freshman_stage(self):
        result = turn_analyzer.analyze(
            "我看到学校公众号报道新生社团活动。",
            {"user_stage": "early_freshman"},
        )

        self.assertEqual(result["stage_signal"], "early_freshman")

    def test_polite_mafan_is_not_frustrated_memory(self):
        result = turn_analyzer.analyze("麻烦介绍一下课程安排。")

        self.assertNotEqual(result["mood"], "frustrated")
        self.assertFalse(result["memory_worthy"])

    def test_negated_refusal_does_not_deactivate_hook(self):
        current_state = {
            "next_hook": {
                "topic": "course_rhythm",
                "label": "课程节奏",
                "active": True,
            }
        }

        result = turn_analyzer.analyze("不是不聊课程，我是想问怎么安排。", current_state)

        self.assertEqual(result["topic"], "course_rhythm")
        self.assertTrue(result["next_hook"]["active"])

class RelationshipStateTest(unittest.TestCase):
    def test_update_and_greeting_rules(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            state = relationship_state.default_state()
            analysis = turn_analyzer.analyze("信电会不会很难，我怕跟不上。")
            updated = relationship_state.update_after_turn(
                state, analysis, now=datetime(2026, 6, 5, 10, 0, tzinfo=timezone.utc)
            )
            relationship_state.save_state(data_dir, "alice", updated)

            self.assertEqual(updated["core_concern"], "担心信电课程跟不上")
            self.assertEqual(updated["next_hook"]["topic"], "course_rhythm")
            self.assertEqual(relationship_state.growth_profile_for_stage("early_freshman"), "大一上")

            first = relationship_state.greeting_payload(data_dir, "alice", today="2026-06-06")
            second = relationship_state.greeting_payload(data_dir, "alice", today="2026-06-06")

            self.assertEqual(first["kind"], "contextual")
            self.assertIn("课程节奏", first["greeting"])
            self.assertEqual(second["kind"], "generic")
            self.assertNotIn("课程节奏", second["greeting"])
            for phrase in ("我一直记得", "我一直在想", "我等你很久", "你怎么又不来了"):
                self.assertNotIn(phrase, first["greeting"])


class AppRelationshipTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import os
        import importlib
        os.environ.setdefault("DEEPSEEK_API_KEY", "test-key")
        cls.app_module = importlib.import_module("app")

    def test_chat_returns_relationship_fields(self):
        app_module = self.app_module

        class FakeMessage:
            content = "怕跟不上很正常，我们先把开学第一个月拆小一点。[smile]"

        class FakeChoice:
            finish_reason = "stop"
            message = FakeMessage()

        class FakeResponse:
            choices = [FakeChoice()]

        class FakeCompletions:
            def create(self, **kwargs):
                return FakeResponse()

        class FakeClient:
            class chat:
                completions = FakeCompletions()

        with tempfile.TemporaryDirectory() as tmp:
            app_module.active_conversations.clear()
            with patch.object(app_module, "DATA_DIR", Path(tmp)):
                with patch.object(app_module, "run_tool", return_value=""):
                    with patch.object(app_module, "client", FakeClient()):
                        response = app_module.app.test_client().post("/api/chat", json={
                            "user_id": "alice",
                            "message": "信电会不会很难，我怕跟不上。",
                        })
                        payload = response.get_json()
                saved = relationship_state.load_state(Path(tmp), "alice")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["state"]["recent_mood"], "anxious")
        self.assertEqual(payload["next_hook"]["topic"], "course_rhythm")
        self.assertEqual(saved["core_concern"], "担心信电课程跟不上")

    def test_chat_core_builds_safe_location_fact_for_relationship_test(self):
        app_module = self.app_module

        class FakeMessage:
            content = "行政楼往南校区进门右手边走，图书馆的钟楼远远就能看见。[think]"

        class FakeChoice:
            finish_reason = "stop"
            message = FakeMessage()

        class FakeResponse:
            choices = [FakeChoice()]

        class FakeCompletions:
            def __init__(self):
                self.calls = []

            def create(self, **kwargs):
                self.calls.append(kwargs)
                return FakeResponse()

        class FakeChat:
            def __init__(self):
                self.completions = FakeCompletions()

        class FakeClient:
            def __init__(self):
                self.chat = FakeChat()

        fake_client = FakeClient()
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(app_module, "client", fake_client):
                payload = app_module.chat_core(
                    "alice",
                    "我要打印成绩单英文材料，你知道学校哪里能打印不？",
                    tmp,
                )

        self.assertIn("行政楼一楼自助终端", payload["reply"])
        self.assertIn("以终端页面", payload["reply"])
        self.assertNotIn("右手边", payload["reply"])
        self.assertNotIn("钟楼", payload["reply"])
        self.assertEqual(len(fake_client.chat.completions.calls), 0)

    def test_greeting_route_context_once_per_day(self):
        app_module = self.app_module
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            state = relationship_state.default_state()
            state["next_hook"] = {
                "topic": "course_rhythm",
                "label": "课程节奏",
                "last_mentioned": "2026-06-04T10:00:00+00:00",
                "active": True,
            }
            relationship_state.save_state(data_dir, "alice", state)
            with patch.object(app_module, "DATA_DIR", data_dir):
                client = app_module.app.test_client()
                first = client.get("/api/greeting?user_id=alice&today=2026-06-05").get_json()
                second = client.get("/api/greeting?user_id=alice&today=2026-06-05").get_json()

        self.assertEqual(first["kind"], "contextual")
        self.assertIn("课程节奏", first["greeting"])
        self.assertEqual(second["kind"], "generic")


class FollowupSystemTest(unittest.TestCase):
    """关心系统 followups 功能测试"""

    def setUp(self):
        self.data_dir = Path(tempfile.mkdtemp(prefix="test_followups_"))
        self.user_id = "test_followup_user"

    def tearDown(self):
        import shutil
        shutil.rmtree(self.data_dir, ignore_errors=True)

    def test_concern_creates_followup(self):
        """用户表达课程焦虑 → 创建 concern followup"""
        state = relationship_state.default_state()
        analysis = turn_analyzer.analyze("信电会不会很难，我怕跟不上。", state)
        state = relationship_state.update_after_turn(state, analysis)

        followups = state.get("followups", [])
        self.assertGreater(len(followups), 0)
        self.assertEqual(followups[0]["kind"], "concern")
        self.assertEqual(followups[0]["status"], "active")

    def test_repeated_concern_increases_intensity(self):
        """多次提到同一问题 → mention_count 增加"""
        state = relationship_state.default_state()

        # 使用相似措辞确保匹配到同一个 label
        for msg in ["C语言好难，指针搞不懂", "C语言的指针还是不会", "C语言太难了"]:
            analysis = turn_analyzer.analyze(msg, state)
            state = relationship_state.update_after_turn(state, analysis)

        followups = state.get("followups", [])
        self.assertGreater(len(followups), 0, "应至少创建一个 followup")
        mention_counts = [f.get("mention_count", 0) for f in followups]
        self.assertGreaterEqual(max(mention_counts), 2, "重复提到应增加 mention_count")

    def test_refusal_deactivates_hook(self):
        """用户说聊点别的 → next_hook 应失活"""
        state = relationship_state.default_state()

        # 先创建一个 active hook
        analysis = turn_analyzer.analyze("信电会不会很难，我怕跟不上。", state)
        state = relationship_state.update_after_turn(state, analysis)
        self.assertTrue(state["next_hook"].get("active"))

        # 用户拒绝
        analysis2 = turn_analyzer.analyze("聊点别的吧，累了", state)
        state = relationship_state.update_after_turn(state, analysis2)
        self.assertFalse(state["next_hook"].get("active"),
                         "用户说聊点别的后 hook 应失活")

    def test_followups_survive_save_load_cycle(self):
        """followups 在 save/load 后保持"""
        state = relationship_state.default_state()
        analysis = turn_analyzer.analyze("信电会不会很难，我怕跟不上。", state)
        state = relationship_state.update_after_turn(state, analysis)

        relationship_state.save_state(self.data_dir, self.user_id, state)
        loaded = relationship_state.load_state(self.data_dir, self.user_id)

        self.assertEqual(
            len(loaded.get("followups", [])),
            len(state.get("followups", [])),
        )

    def test_followups_prompt_includes_active_items(self):
        """活跃 followups 应出现在 prompt 中"""
        state = relationship_state.default_state()
        analysis = turn_analyzer.analyze("C语言好难，指针完全搞不懂", state)
        state = relationship_state.update_after_turn(state, analysis)

        prompt = relationship_state.followups_prompt(state)
        self.assertIn("关心的线索", prompt)
        # label 中应包含 C语言 或 指针
        self.assertTrue("C语言" in prompt or "指针" in prompt or "C语言学习" in prompt,
                        f"prompt should contain followup label, got: {prompt[:200]}")

    def test_decision_detection(self):
        """纠结考研应创建 decision followup"""
        state = relationship_state.default_state()
        analysis = turn_analyzer.analyze("我在纠结要不要考研", state)
        state = relationship_state.update_after_turn(state, analysis)

        followups = state.get("followups", [])
        decisions = [f for f in followups if f["kind"] == "decision"]
        self.assertGreater(len(decisions), 0)

    def test_no_followup_for_neutral_chat(self):
        """普通聊天不应创建 followup"""
        state = relationship_state.default_state()
        analysis = turn_analyzer.analyze("嗯，我知道了，谢谢你小芯", state)
        state = relationship_state.update_after_turn(state, analysis)

        # 不应新增 followup
        self.assertEqual(
            len(state.get("followups", [])), 0,
            "普通聊天不应创建 followup"
        )

    def test_greeting_uses_followup(self):
        """问候应引用活跃 followup"""
        state = relationship_state.default_state()
        analysis = turn_analyzer.analyze("信电会不会很难，我怕跟不上。", state)
        state = relationship_state.update_after_turn(state, analysis)
        relationship_state.save_state(self.data_dir, self.user_id, state)

        payload = relationship_state.greeting_payload(
            self.data_dir, self.user_id, today="2026-06-08"
        )
        self.assertEqual(payload["kind"], "contextual")
        self.assertIn("课程", payload["greeting"])


if __name__ == "__main__":
    unittest.main()
