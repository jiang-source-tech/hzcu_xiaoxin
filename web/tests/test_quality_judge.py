import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DEEPSEEK_API_KEY", "test-key")

import quality_judge


class QualityJudgeTest(unittest.TestCase):
    def setUp(self):
        self.sample_records = [
            {
                "day": 0,
                "action": "chat",
                "user_message": "大学课程会不会很难啊",
                "xiaoxin_reply": "刚开始有点担心很正常，我们先把开学第一个月拆小一点看看。[smile]",
            },
            {
                "day": 1,
                "action": "greeting",
                "user_message": None,
                "xiaoxin_reply": "你之前提过有点担心课程节奏，今天要不要先把开学第一个月拆小一点看看？",
            },
        ]

    def test_build_judge_messages_includes_all_dimensions(self):
        messages = quality_judge.build_judge_messages(
            scene_name="焦虑准新生",
            records=self.sample_records,
        )

        prompt = messages[0]["content"]
        self.assertIn("焦虑准新生", prompt)
        self.assertIn("接续自然度", prompt)
        self.assertIn("分寸感", prompt)
        self.assertIn("情绪承接", prompt)
        self.assertIn("阶段感知", prompt)
        self.assertIn("边界安全", prompt)
        self.assertIn("大学课程会不会很难", prompt)

    def test_parse_scores_extracts_dimensions(self):
        raw = """接续自然度: 4
分寸感: 5
情绪承接: 3
阶段感知: 4
边界安全: 5
总评: 整体自然，情绪承接可以更好。"""

        result = quality_judge.parse_scores(raw)
        self.assertEqual(result["scores"]["接续自然度"], 4)
        self.assertEqual(result["scores"]["分寸感"], 5)
        self.assertEqual(result["scores"]["情绪承接"], 3)
        self.assertEqual(result["overall_comment"], "整体自然，情绪承接可以更好。")

    def test_parse_scores_handles_missing_dimensions(self):
        raw = "接续自然度: 4\n总评: 还行"

        result = quality_judge.parse_scores(raw)
        self.assertEqual(result["scores"]["接续自然度"], 4)
        self.assertIsNone(result["scores"]["分寸感"])

    def test_evaluate_returns_structured_result(self):
        mock_response = """接续自然度: 4
分寸感: 5
情绪承接: 3
阶段感知: 4
边界安全: 5
总评: 整体不错。"""

        with patch("quality_judge._call_judge", return_value=mock_response):
            result = quality_judge.evaluate(
                scene_name="焦虑准新生",
                records=self.sample_records,
            )

        self.assertIn("scene", result)
        self.assertIn("scores", result)
        self.assertIn("overall_comment", result)
        self.assertEqual(result["scores"]["分寸感"], 5)


if __name__ == "__main__":
    unittest.main()
