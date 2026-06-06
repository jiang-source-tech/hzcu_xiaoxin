import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DEEPSEEK_API_KEY", "test-key")

import user_simulator


class UserSimulatorTest(unittest.TestCase):
    def setUp(self):
        self.character = {
            "stage": "prospective",
            "traits": "偏内向，口语化表达，每次1-2句话。",
        }

    def test_build_user_simulator_messages_includes_character_and_intent(self):
        messages = user_simulator.build_user_messages(
            character=self.character,
            intent="你对大学课程有点担心，跟小芯聊聊。",
            conversation_summary="",
            forbid_patterns=["信电会不会很难"],
        )

        system = messages[0]["content"]
        self.assertIn("偏内向", system)
        self.assertIn("对大学课程有点担心", system)
        self.assertIn("信电会不会很难", system)

    def test_build_user_messages_includes_conversation_summary(self):
        messages = user_simulator.build_user_messages(
            character=self.character,
            intent="继续聊课程的事。",
            conversation_summary="新生: 大学课程难吗\n小芯: 慢慢适应就好",
            forbid_patterns=[],
        )

        system = messages[0]["content"]
        self.assertIn("新生:", system)

    def test_generate_user_message_returns_string(self):
        with patch("user_simulator._call_api", return_value="大学课程会不会很吃力啊"):
            result = user_simulator.generate_user_message(
                character=self.character,
                intent="你对课程有点担心。",
                conversation_summary="",
                forbid_patterns=[],
            )
            self.assertIsInstance(result, str)
            self.assertGreater(len(result), 0)

    def test_generate_user_message_drops_role_prefix(self):
        with patch("user_simulator._call_api", return_value="新生: 课程好难啊"):
            result = user_simulator.generate_user_message(
                character=self.character,
                intent="聊聊课程。",
                conversation_summary="",
                forbid_patterns=[],
            )
            self.assertNotIn("新生:", result)


    def test_generate_user_message_handles_none_forbid_patterns(self):
        with patch("user_simulator._call_api", return_value="测试消息"):
            result = user_simulator.generate_user_message(
                character=self.character,
                intent="随便聊聊。",
                conversation_summary="",
                forbid_patterns=None,
            )
            self.assertIsInstance(result, str)
            self.assertEqual(result, "测试消息")

class UserSimulatorPressureTest(unittest.TestCase):
    def test_build_pressure_user_messages_includes_goal_state_and_transcript(self):
        messages = user_simulator.build_pressure_user_messages(
            character={"traits": "An anxious prospective student."},
            pressure_goal="Ask whether Xiaoxin remembers yesterday's course anxiety.",
            same_day_transcript="User: I am worried.\nXiaoxin: We can break it down.",
            prior_day_summary="Day 0: talked about course rhythm.",
            relationship_state={"user_stage": "prospective", "recent_topic": "course_rhythm"},
            forbid_patterns=["do not say probe"],
            turn_index=3,
            turn_count=8,
        )

        text = "\n".join(item["content"] for item in messages)
        self.assertIn("An anxious prospective student.", text)
        self.assertIn("Ask whether Xiaoxin remembers", text)
        self.assertIn("course_rhythm", text)
        self.assertIn("turn 3 of 8", text)
        self.assertIn("do not say probe", text)

    def test_generate_pressure_user_message_strips_role_prefix(self):
        with patch("user_simulator._call_api", return_value="User: I am still worried."):
            message = user_simulator.generate_pressure_user_message(
                character={"traits": "An anxious prospective student."},
                pressure_goal="Continue the concern.",
                same_day_transcript="",
                prior_day_summary="",
                relationship_state={},
                forbid_patterns=[],
                seed=11,
                turn_index=1,
                turn_count=4,
            )

        self.assertEqual(message, "I am still worried.")


if __name__ == "__main__":
    unittest.main()
