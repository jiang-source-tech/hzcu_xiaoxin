import sys
import json
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

        self.assertEqual(result["stage_signal"], "prospective")
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

    def test_c_language_result_is_growth_signal(self):
        result = turn_analyzer.analyze("我今天终于把链表跑通了，之前一直卡住。")

        self.assertEqual(result["growth_signal"]["kind"], "result")
        self.assertEqual(result["growth_signal"]["topic"], "course_rhythm")
        self.assertIn("链表", result["growth_signal"]["label"])


class RelationshipStateTest(unittest.TestCase):
    def test_default_state_contains_normalized_pet_state(self):
        state = relationship_state.default_state()

        self.assertEqual(state["pet_state"]["mood"], "calm")
        self.assertEqual(state["pet_state"]["energy"], 70)
        self.assertEqual(state["pet_state"]["bond"], 0)
        self.assertEqual(state["pet_state"]["relationship_stage"], "first_meet")
        self.assertEqual(state["pet_state"]["presence_mode"], "idle")
        self.assertIsNone(state["pet_state"]["last_seen_at"])
        self.assertEqual(state["growth_timeline"], [])

    def test_load_state_migrates_missing_pet_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            with open(data_dir / "relationship_alice.json", "w", encoding="utf-8") as f:
                json.dump({"recent_mood": "anxious", "followups": []}, f)

            state = relationship_state.load_state(data_dir, "alice")

        self.assertEqual(state["pet_state"]["mood"], "calm")
        self.assertEqual(state["pet_state"]["relationship_stage"], "first_meet")
        self.assertEqual(state["growth_timeline"], [])

    def test_growth_signal_adds_timeline_and_softens_followup(self):
        state = relationship_state.default_state()
        concern = turn_analyzer.analyze("我怕 C 语言跟不上，指针也听不懂。")
        state = relationship_state.update_after_turn(
            state, concern, now=datetime(2026, 6, 10, 8, 0, tzinfo=timezone.utc)
        )
        progress = turn_analyzer.analyze("我今天终于把链表跑通了，之前一直卡住。", state)

        updated = relationship_state.update_after_turn(
            state, progress, now=datetime(2026, 6, 10, 9, 0, tzinfo=timezone.utc)
        )

        self.assertEqual(updated["growth_timeline"][-1]["kind"], "result")
        self.assertEqual(updated["pet_state"]["presence_mode"], "celebrating")
        self.assertGreater(updated["pet_state"]["bond"], state["pet_state"]["bond"])
        active_course = [
            f for f in updated["followups"]
            if f.get("topic") == "course_rhythm" and f.get("status") == "active"
        ]
        self.assertEqual(active_course, [])

    def test_prompt_summary_includes_companion_context_and_tts_rules(self):
        state = relationship_state.default_state()
        state["pet_state"]["bond"] = 12
        text = relationship_state.prompt_summary(
            state,
            {"growth_signal": {"kind": "result", "topic": "course_rhythm", "label": "链表跑通"}},
        )

        self.assertIn("伙伴状态", text)
        self.assertIn("可轻触线索", text)
        self.assertIn("speech", text)
        self.assertIn("action", text)
        self.assertIn("不要把动作旁白", text)

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


    def test_record_chat_reply_returns_action_alias_and_clean_speech(self):
        app_module = self.app_module
        action = {"kind": "celebrate", "intensity": 0.55}
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(app_module, "DATA_DIR", Path(tmp)):
                with patch.object(app_module, "run_tool", return_value=""):
                    payload = app_module.record_chat_reply(
                        "alice",
                        "sid",
                        [],
                        "我今天把链表跑通了",
                        "[proud]这个要庆祝一下。{action:celebrate}",
                        relationship=relationship_state.default_state(),
                        companion_action=action,
                    )

        self.assertEqual(payload["action"], action)
        self.assertEqual(payload["companion_action"], action)
        self.assertNotIn("action", payload["speech"])
        self.assertNotIn("[proud]", payload["speech"])

    def test_hard_template_route_does_not_increase_bond_or_growth(self):
        app_module = self.app_module
        with tempfile.TemporaryDirectory() as tmp:
            app_module.active_conversations.clear()
            with patch.object(app_module, "DATA_DIR", Path(tmp)):
                with patch.object(app_module, "run_tool", return_value=""):
                    response = app_module.app.test_client().post("/api/chat", json={
                        "user_id": "alice",
                        "message": "小芯，你能帮我查一下我的期末成绩吗？",
                    })
            payload = response.get_json()
            saved = relationship_state.load_state(Path(tmp), "alice")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(saved["pet_state"]["bond"], 0)
        self.assertEqual(saved["growth_timeline"], [])
        self.assertEqual(payload["state"]["pet_state"]["bond"], 0)


if __name__ == "__main__":
    unittest.main()
