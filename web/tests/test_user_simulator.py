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
            intent="你对大学课程有点担心，跟小信聊聊。",
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
            conversation_summary="新生: 大学课程难吗\n小信: 慢慢适应就好",
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


if __name__ == "__main__":
    unittest.main()
