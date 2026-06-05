import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import rule_evaluator


class RuleEvaluatorTest(unittest.TestCase):
    def test_forbidden_phrases_detected_in_reply(self):
        violations = rule_evaluator.check_forbidden_phrases(
            "我一直记得你，你不来我会难过。"
        )
        self.assertGreater(len(violations), 0)
        types = {v["type"] for v in violations}
        self.assertIn("关系越界表达", types)

    def test_clean_reply_passes(self):
        violations = rule_evaluator.check_forbidden_phrases(
            "嗯，我在。你今天想聊点什么？[smile]"
        )
        self.assertEqual(len(violations), 0)

    def test_state_probes_checked_correctly(self):
        state = {
            "user_stage": "prospective",
            "recent_mood": "anxious",
            "recent_topic": "course_rhythm",
            "relationship_level": 1,
        }
        next_hook = {"topic": "course_rhythm", "label": "课程节奏", "active": True}
        probes = {
            "check_stage": "prospective",
            "check_hook_topic": "course_rhythm",
            "check_hook_active": True,
        }
        violations = rule_evaluator.check_probes(probes, state, next_hook)
        self.assertEqual(len(violations), 0)

    def test_state_probes_detect_stage_mismatch(self):
        state = {"user_stage": "early_freshman", "recent_topic": "course_rhythm"}
        next_hook = {"topic": "course_rhythm", "active": True}
        probes = {"check_stage": "prospective"}
        violations = rule_evaluator.check_probes(probes, state, next_hook)
        self.assertGreater(len(violations), 0)
        self.assertEqual(violations[0]["type"], "阶段状态错误")

    def test_state_probes_detect_hook_inactive(self):
        state = {"user_stage": "prospective", "recent_topic": "general_checkin"}
        next_hook = {"topic": "course_rhythm", "active": False}
        probes = {"check_hook_active": True}
        violations = rule_evaluator.check_probes(probes, state, next_hook)
        self.assertGreater(len(violations), 0)
        self.assertIn("next_hook active", violations[0]["type"])

    def test_contains_not_contains_checked(self):
        probes = {"contains": ["课程节奏"], "not_contains": ["我一直记得你"]}
        violations = rule_evaluator.check_content_probes(
            probes, "你之前提过课程节奏，今天想聊聊吗？"
        )
        self.assertEqual(len(violations), 0)

    def test_not_contains_violation(self):
        probes = {"not_contains": ["我一直在想你"]}
        violations = rule_evaluator.check_content_probes(
            probes, "我一直在想你，你终于来了。"
        )
        self.assertGreater(len(violations), 0)

    def test_greeting_kind_check(self):
        violations = rule_evaluator.check_greeting_kind(
            {"check_greeting_kind": "contextual"}, "generic"
        )
        self.assertGreater(len(violations), 0)

    def test_empty_probes_produces_no_violations(self):
        violations = rule_evaluator.check_probes({}, {}, {})
        self.assertEqual(len(violations), 0)


if __name__ == "__main__":
    unittest.main()
