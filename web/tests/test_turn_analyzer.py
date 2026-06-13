import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import turn_analyzer


class TurnAnalyzerTest(unittest.TestCase):
    def test_detect_followup_uses_topic_label_instead_of_raw_sentence(self):
        followup = turn_analyzer.detect_followups(
            "小芯，你好，我刚来学校有点紧张。",
            mood="anxious",
            topic="general_checkin",
        )

        self.assertIsNotNone(followup)
        self.assertEqual(followup["label"], "近况")

    def test_detect_followup_keeps_specific_known_label_when_available(self):
        followup = turn_analyzer.detect_followups(
            "我最近有点担心C语言跟不上。",
            mood="anxious",
            topic="course_rhythm",
        )

        self.assertIsNotNone(followup)
        self.assertEqual(followup["label"], "C语言学习")


if __name__ == "__main__":
    unittest.main()
