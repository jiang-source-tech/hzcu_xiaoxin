import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

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


if __name__ == "__main__":
    unittest.main()
