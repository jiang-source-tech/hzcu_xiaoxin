import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("DEEPSEEK_API_KEY", "test-key")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app as app_module
from app import is_student_farewell


class _FakeMessage:
    def __init__(self, content):
        self.content = content


class _FakeChoice:
    def __init__(self, content):
        self.message = _FakeMessage(content)


class _FakeResponse:
    def __init__(self, content):
        self.choices = [_FakeChoice(content)]


class _FakeCompletions:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return _FakeResponse(self.replies.pop(0))


class _FakeChat:
    def __init__(self, replies):
        self.completions = _FakeCompletions(replies)


class _FakeClient:
    def __init__(self, replies):
        self.chat = _FakeChat(replies)

    @property
    def calls(self):
        return self.chat.completions.calls


class SelfplayEndTest(unittest.TestCase):
    def test_student_farewell_ends_conversation(self):
        farewell_messages = [
            "拜拜，小信，下次再聊！",
            "那我先去吃饭了，下次聊。",
            "今天先到这吧，晚点再聊。",
            "谢谢你，我先走啦。",
        ]

        for message in farewell_messages:
            with self.subTest(message=message):
                self.assertTrue(is_student_farewell(message))

    def test_regular_student_message_keeps_conversation_open(self):
        regular_messages = [
            "听起来挺有意思的，那电子信息主要学什么？",
            "我还想再见识一下智能车比赛。",
            "那我是不是可以先试试 C 语言？",
        ]

        for message in regular_messages:
            with self.subTest(message=message):
                self.assertFalse(is_student_farewell(message))

    def test_selfplay_turn_marks_student_farewell_as_ended(self):
        fake_client = _FakeClient([
            "嗨，听起来你今天聊得差不多啦。[wave]",
            "嗯嗯，谢谢小信，那我先走啦，拜拜！",
        ])

        with patch.object(app_module, "client", fake_client), \
             patch.object(app_module, "build_system_prompt", return_value="你是小信。"):
            response = app_module.app.test_client().post(
                "/api/selfplay/turn",
                json={
                    "persona": "小明",
                    "message": "今天先聊到这里吧。",
                    "turn": 3,
                    "conversation": [
                        {"role": "student", "content": "我想了解一下大学生活。"},
                        {"role": "xiaoxin", "content": "可以呀，我们慢慢聊。"},
                    ],
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["ended"])
        self.assertEqual(payload["end_reason"], "student_farewell")
        self.assertEqual(payload["turn"], 4)

    def test_selfplay_evaluate_returns_numeric_scores(self):
        fake_client = _FakeClient([
            "人设=8\n边界=9\n语音=7\n陪伴=10\n总评=挺自然的一段对话",
        ])

        with patch.object(app_module, "client", fake_client):
            response = app_module.app.test_client().post(
                "/api/selfplay/evaluate",
                json={
                    "scenario": "初次见面",
                    "conversation": [
                        {"role": "student", "content": "你好，小信。"},
                        {"role": "xiaoxin", "content": "嗨，我在。"},
                        {"role": "student", "content": "我想了解专业。"},
                        {"role": "xiaoxin", "content": "可以呀。"},
                    ],
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["人设一致性"], 8)
        self.assertEqual(payload["边界意识"], 9)
        self.assertEqual(payload["语音适配"], 7)
        self.assertEqual(payload["陪伴感"], 10)
        self.assertEqual(payload["整体评价"], "挺自然的一段对话")

    def test_selfplay_evaluate_retries_empty_model_response(self):
        fake_client = _FakeClient([
            "",
            "人设=7\n边界=8\n语音=8\n陪伴=9\n总评=第二次评估正常",
        ])

        with patch.object(app_module, "client", fake_client):
            response = app_module.app.test_client().post(
                "/api/selfplay/evaluate",
                json={
                    "scenario": "小明",
                    "conversation": [
                        {"role": "student", "content": "你好，小信。"},
                        {"role": "xiaoxin", "content": "嗨，我在。"},
                        {"role": "student", "content": "我有点担心高数。"},
                        {"role": "xiaoxin", "content": "这个担心很正常，我们慢慢拆。"},
                    ],
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["人设一致性"], 7)
        self.assertEqual(payload["边界意识"], 8)
        self.assertEqual(payload["语音适配"], 8)
        self.assertEqual(payload["陪伴感"], 9)
        self.assertEqual(payload["整体评价"], "第二次评估正常")
        self.assertEqual(len(fake_client.calls), 2)

    def test_non_xindian_persona_prompt_does_not_force_freshman_identity(self):
        fake_client = _FakeClient([
            "嗨，你好呀。[smile]",
            "我是商学院的，刚好路过看看。",
        ])

        with patch.object(app_module, "client", fake_client), \
             patch.object(app_module, "build_system_prompt", return_value="你是小信。"):
            response = app_module.app.test_client().post(
                "/api/selfplay/turn",
                json={
                    "persona": "非信电学生",
                    "message": "我是商学院的，路过看到你。",
                    "turn": 0,
                    "conversation": [
                        {"role": "student", "content": "我是商学院的，路过看到你。"},
                    ],
                },
            )

        self.assertEqual(response.status_code, 200)
        student_system_prompt = fake_client.calls[1]["messages"][0]["content"]
        self.assertIn("不要自称信电学院学生", student_system_prompt)
        self.assertNotIn("一个真实的大一新生", student_system_prompt)
        student_user_prompt = fake_client.calls[1]["messages"][1]["content"]
        self.assertNotIn("请作为新生", student_user_prompt)

    def test_empty_student_reply_gets_persona_safe_fallback(self):
        fake_client = _FakeClient([
            "嘿！我是小信，信电学院的数字学长。[smile]",
            "",
        ])

        with patch.object(app_module, "client", fake_client), \
             patch.object(app_module, "build_system_prompt", return_value="你是小信。"):
            response = app_module.app.test_client().post(
                "/api/selfplay/turn",
                json={
                    "persona": "非信电学生",
                    "message": "我是商学院的，路过看到你。",
                    "turn": 0,
                    "conversation": [
                        {"role": "student", "content": "我是商学院的，路过看到你。"},
                    ],
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["student"]["content"])
        self.assertIn("商学院", payload["student"]["content"])
        self.assertNotIn("电子信息工程", payload["student"]["content"])

    def test_fragmented_xiaoxin_reply_retries_before_student_turn(self):
        fake_client = _FakeClient([
            "翻",
            "是啊，高数一开始确实像突然加速。先别急，把课本例题和作业题一类一类拆开，慢慢会顺起来的。[think]",
            "嗯嗯，那我先从例题开始补起来。",
        ])

        with patch.object(app_module, "client", fake_client), \
             patch.object(app_module, "build_system_prompt", return_value="你是小信。"):
            response = app_module.app.test_client().post(
                "/api/selfplay/turn",
                json={
                    "persona": "小明",
                    "message": "啊C语言和高数有点慌，听说大学高数难度翻倍。",
                    "turn": 0,
                    "conversation": [
                        {"role": "student", "content": "啊C语言和高数有点慌，听说大学高数难度翻倍。"},
                    ],
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertNotEqual(payload["xiaoxin"]["content"], "翻")
        self.assertIn("高数", payload["xiaoxin"]["content"])
        self.assertEqual(len(fake_client.calls), 3)
        self.assertIn("不完整", fake_client.calls[1]["messages"][-1]["content"])


if __name__ == "__main__":
    unittest.main()
