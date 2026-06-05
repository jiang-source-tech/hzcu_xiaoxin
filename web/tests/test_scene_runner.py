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


if __name__ == "__main__":
    unittest.main()
