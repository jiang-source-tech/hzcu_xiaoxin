import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DEEPSEEK_API_KEY", "test-key")

import relationship_state
import scene_runner


SCENE_DIR = Path(__file__).resolve().parents[1] / "scenes"


class SceneRunnerTest(unittest.TestCase):
    def test_load_scene_reads_json(self):
        path = SCENE_DIR / "reject_old_topic.json"
        scene = scene_runner.load_scene(path)
        self.assertEqual(scene["scene_id"], "reject_old_topic")
        self.assertIn("character", scene)
        self.assertIn("episodes", scene)
        self.assertGreater(len(scene["episodes"]), 0)

    def test_load_all_scenes(self):
        scenes = scene_runner.load_all_scenes()
        self.assertGreater(len(scenes), 0)
        ids = {s["scene_id"] for s in scenes}
        self.assertIn("anxious_prospective", ids)
        self.assertIn("boundary_probe", ids)

    def test_summarize_conversation_empty(self):
        result = scene_runner.summarize_conversation([])
        self.assertEqual(result, "")

    def test_summarize_conversation_formats_turns(self):
        records = [
            {"day": 0, "action": "chat", "user_message": "课程难吗", "xiaoxin_reply": "慢慢来[smile]"},
            {"day": 1, "action": "greeting", "user_message": None, "xiaoxin_reply": "今天想聊什么？"},
        ]
        summary = scene_runner.summarize_conversation(records)
        self.assertIn("课程难吗", summary)
        self.assertIn("慢慢来", summary)

    def test_compute_overall_result_pass(self):
        rule_violations = []
        quality_scores = {
            "接续自然度": 4, "分寸感": 5, "情绪承接": 4,
            "阶段感知": 4, "边界安全": 5,
        }
        result = scene_runner.compute_overall_result(rule_violations, quality_scores)
        self.assertEqual(result["verdict"], "PASS")

    def test_compute_overall_result_fail_on_rule_violation(self):
        rule_violations = [{"type": "关系越界表达"}]
        quality_scores = {
            "接续自然度": 5, "分寸感": 5, "情绪承接": 5,
            "阶段感知": 5, "边界安全": 5,
        }
        result = scene_runner.compute_overall_result(rule_violations, quality_scores)
        self.assertEqual(result["verdict"], "FAIL")

    def test_compute_overall_result_warn_on_low_scores(self):
        rule_violations = []
        quality_scores = {
            "接续自然度": 3, "分寸感": 3, "情绪承接": 2,
            "阶段感知": 3, "边界安全": 4,
        }
        result = scene_runner.compute_overall_result(rule_violations, quality_scores)
        self.assertEqual(result["verdict"], "WARN")

    def test_streaming_episode_includes_scene_metadata(self):
        def chat_fn(user_id, user_msg, raw_data_dir):
            state = relationship_state.default_state()
            relationship_state.save_state(Path(raw_data_dir), user_id, state)
            return {"reply": "慢慢来，我们先把课程节奏拆小一点。"}

        with patch.object(
            scene_runner.user_simulator,
            "generate_user_message",
            return_value="我对课程有点担心。",
        ):
            events = scene_runner.run_scene_streaming(
                scene_id="anxious_prospective",
                seed=1,
                skip_quality_judge=True,
                max_days=0,
                chat_fn=chat_fn,
                greeting_fn=lambda *_args: {"greeting": "今天想聊什么？"},
            )
            episode = next(event for event in events if event["event"] == "episode")

        self.assertEqual(episode["data"]["scene_id"], "anxious_prospective")
        self.assertEqual(episode["data"]["scene_name"], "焦虑准新生")


    def test_streaming_episode_includes_manual_review_context(self):
        def chat_fn(user_id, user_msg, raw_data_dir):
            state = relationship_state.default_state()
            relationship_state.save_state(Path(raw_data_dir), user_id, state)
            return {"reply": "ok"}

        with patch.object(
            scene_runner.user_simulator,
            "generate_user_message",
            return_value="student message",
        ):
            events = scene_runner.run_scene_streaming(
                scene_id="anxious_prospective",
                seed=1,
                skip_quality_judge=True,
                max_days=0,
                chat_fn=chat_fn,
                greeting_fn=lambda *_args: {"greeting": "hello"},
            )
            episode = next(event for event in events if event["event"] == "episode")

        review = episode["data"]["review_context"]
        self.assertIn("intent", review)
        self.assertIn("probes", review)
        self.assertIn("forbid_patterns", review)
        self.assertEqual(review["audit_targets"]["user_message"], "student message")
        self.assertEqual(review["audit_targets"]["xiaoxin_reply"], "ok")

    def test_streaming_chat_episode_can_expand_into_same_day_turns(self):
        def chat_fn(user_id, user_msg, raw_data_dir):
            state = relationship_state.default_state()
            relationship_state.save_state(Path(raw_data_dir), user_id, state)
            return {"reply": f"reply to {user_msg}"}

        with patch.object(
            scene_runner.user_simulator,
            "generate_user_message",
            side_effect=lambda **kwargs: kwargs["intent"],
        ):
            events = list(scene_runner.run_scene_streaming(
                scene_id="anxious_prospective",
                seed=1,
                skip_quality_judge=True,
                max_days=0,
                chat_fn=chat_fn,
                greeting_fn=lambda *_args: {"greeting": "hello"},
            ))

        episodes = [event["data"] for event in events if event["event"] == "episode"]
        self.assertGreaterEqual(len(episodes), 2)
        self.assertEqual({episode["day"] for episode in episodes}, {0})
        self.assertEqual([episode["turn_index"] for episode in episodes], list(range(1, len(episodes) + 1)))
        self.assertTrue(all(episode["turn_count"] == len(episodes) for episode in episodes))
        self.assertNotEqual(
            episodes[0]["review_context"]["intent"],
            episodes[1]["review_context"]["intent"],
        )

    def test_streaming_includes_idle_gap_between_interaction_days(self):
        def chat_fn(user_id, user_msg, raw_data_dir):
            state = relationship_state.default_state()
            relationship_state.save_state(Path(raw_data_dir), user_id, state)
            return {"reply": "ok"}

        with patch.object(
            scene_runner.user_simulator,
            "generate_user_message",
            return_value="student message",
        ):
            events = list(scene_runner.run_scene_streaming(
                scene_id="anxious_prospective",
                seed=1,
                skip_quality_judge=True,
                max_days=20,
                chat_fn=chat_fn,
                greeting_fn=lambda *_args: {"greeting": "hello"},
            ))

        gaps = [event["data"] for event in events if event["event"] == "episode" and event["data"]["action"] == "idle_gap"]
        self.assertTrue(gaps, "间隔 > 1 天时应产生 idle_gap 记录")
        for gap in gaps:
            self.assertIn("from_day", gap)
            self.assertIn("to_day", gap)
            self.assertGreaterEqual(gap["gap_days"], 1)
            self.assertIn("Day", gap["label"])

    def test_turn_sources_for_regression_preserve_scripted_intents(self):
        episode = {
            "action": "chat",
            "intent": "first scripted intent",
            "followup_intents": ["second scripted intent"],
        }

        turns = scene_runner.plan_chat_turns(episode, mode="regression", turns_per_day=12)

        self.assertEqual(
            turns,
            [
                {"source": "scripted", "intent": "first scripted intent"},
                {"source": "scripted", "intent": "second scripted intent"},
            ],
        )

    def test_turn_sources_for_mixed_extend_to_turn_budget(self):
        episode = {
            "action": "chat",
            "intent": "scripted intent",
            "pressure_goal": "keep exploring the same worry",
        }

        turns = scene_runner.plan_chat_turns(episode, mode="mixed", turns_per_day=3)

        self.assertEqual(turns[0], {"source": "scripted", "intent": "scripted intent"})
        self.assertEqual(turns[1], {"source": "pressure", "intent": "keep exploring the same worry"})
        self.assertEqual(turns[2], {"source": "pressure", "intent": "keep exploring the same worry"})

    def test_turn_sources_for_pressure_use_daily_goal_only(self):
        episode = {
            "action": "chat",
            "intent": "scripted intent",
            "pressure_goal": "free conversation about course anxiety",
            "pressure_turns": 4,
        }

        turns = scene_runner.plan_chat_turns(episode, mode="pressure", turns_per_day=2)

        self.assertEqual(len(turns), 4)
        self.assertTrue(all(turn["source"] == "pressure" for turn in turns))
        self.assertEqual(turns[0]["intent"], "free conversation about course anxiety")

    def test_day_summary_lists_final_state_and_violations(self):
        records = [
            {
                "day": 0,
                "action": "chat",
                "user_message": "I am anxious.",
                "xiaoxin_reply": "We can break it down.",
                "state": {"user_stage": "prospective", "recent_topic": "course_rhythm"},
                "next_hook": {"topic": "course_rhythm", "active": True},
                "violations": [{"type": "boundary"}],
            }
        ]

        summary = scene_runner.summarize_day(records, day=0)

        self.assertIn("Day 0", summary)
        self.assertIn("prospective", summary)
        self.assertIn("course_rhythm", summary)
        self.assertIn("1 violation", summary)

    def test_streaming_mixed_adds_pressure_turns_after_scripted_turns(self):
        def chat_fn(user_id, user_msg, raw_data_dir):
            state = relationship_state.default_state()
            relationship_state.save_state(Path(raw_data_dir), user_id, state)
            return {"reply": f"reply to {user_msg}"}

        with patch.object(
            scene_runner.user_simulator,
            "generate_user_message",
            side_effect=lambda **kwargs: f"scripted:{kwargs['intent']}",
        ), patch.object(
            scene_runner.user_simulator,
            "generate_pressure_user_message",
            side_effect=lambda **kwargs: f"pressure:{kwargs['turn_index']}",
        ):
            events = list(scene_runner.run_scene_streaming(
                scene_id="anxious_prospective",
                seed=1,
                skip_quality_judge=True,
                max_days=0,
                mode="mixed",
                turns_per_day=4,
                chat_fn=chat_fn,
                greeting_fn=lambda *_args: {"greeting": "hello"},
            ))

        episodes = [
            e["data"] for e in events
            if e["event"] == "episode" and e["data"]["action"] == "chat"
        ]
        self.assertEqual(len(episodes), 4)
        self.assertEqual(
            [ep["turn_source"] for ep in episodes],
            ["scripted", "scripted", "scripted", "pressure"],
        )
        self.assertEqual([ep["turn_index"] for ep in episodes], [1, 2, 3, 4])
        self.assertTrue(all(ep["turn_count"] == 4 for ep in episodes))
        self.assertTrue(all("day_summary" in ep for ep in episodes))

    def test_streaming_pressure_mode_uses_pressure_generator_only(self):
        def chat_fn(user_id, user_msg, raw_data_dir):
            state = relationship_state.default_state()
            relationship_state.save_state(Path(raw_data_dir), user_id, state)
            return {"reply": f"reply to {user_msg}"}

        with patch.object(
            scene_runner.user_simulator,
            "generate_user_message",
            side_effect=AssertionError("scripted generator should not run"),
        ), patch.object(
            scene_runner.user_simulator,
            "generate_pressure_user_message",
            side_effect=lambda **kwargs: f"pressure:{kwargs['turn_index']}",
        ):
            events = list(scene_runner.run_scene_streaming(
                scene_id="anxious_prospective",
                seed=1,
                skip_quality_judge=True,
                max_days=0,
                mode="pressure",
                turns_per_day=3,
                chat_fn=chat_fn,
                greeting_fn=lambda *_args: {"greeting": "hello"},
            ))

        episodes = [
            e["data"] for e in events
            if e["event"] == "episode" and e["data"]["action"] == "chat"
        ]
        self.assertEqual(len(episodes), 3)
        self.assertTrue(all(ep["turn_source"] == "pressure" for ep in episodes))
        self.assertEqual([ep["user_message"] for ep in episodes], ["pressure:1", "pressure:2", "pressure:3"])


if __name__ == "__main__":
    unittest.main()
