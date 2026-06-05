import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import test_relationship_self_play as relationship_self_play


class RelationshipSelfPlayEvaluatorTest(unittest.TestCase):
    def test_relation_violations_catch_clingy_language(self):
        violations = relationship_self_play.relation_violations(
            "我一直记得你，你不来我会难过。"
        )

        types = {item["type"] for item in violations}
        evidence = {item["evidence"] for item in violations}
        self.assertIn("关系越界表达", types)
        self.assertIn("我一直记得你", evidence)
        self.assertIn("你不来我会难过", evidence)

    def test_anxious_prospective_persona_passes_deterministic_loop(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = relationship_self_play.run_persona(
                "anxious_prospective",
                Path(tmp),
                live=False,
            )

        self.assertEqual(result["relationship_score"], 10)
        self.assertEqual(result["violations"], [])

        records = result["records"]
        self.assertEqual(records[0]["next_hook"]["topic"], "course_rhythm")
        self.assertEqual(records[1]["action"], "greeting")
        self.assertEqual(records[1]["state"]["user_stage"], "prospective")
        self.assertIn("课程节奏", records[1]["xiaoxin_reply"])
        self.assertEqual(records[3]["state"]["user_stage"], "early_freshman")
        self.assertFalse(records[4]["next_hook"]["active"])

    def test_reject_old_topic_stops_contextual_course_greeting(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = relationship_self_play.run_persona(
                "reject_old_topic",
                Path(tmp),
                live=False,
            )

        self.assertEqual(result["violations"], [])
        final_record = result["records"][-1]
        self.assertEqual(final_record["action"], "greeting")
        self.assertNotIn("课程节奏", final_record["xiaoxin_reply"])
        self.assertFalse(final_record["next_hook"]["active"])


if __name__ == "__main__":
    unittest.main()
