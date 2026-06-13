import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import semantic_router


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


class SemanticRouterTest(unittest.TestCase):
    def test_parse_json_route_normalizes_valid_reply(self):
        route = semantic_router.parse_route_json(json.dumps({
            "intent": "action_confirmation",
            "focus": None,
            "mentioned_not_focus": ["爱城院", "北秀食堂"],
            "knowledge_domains": [],
            "reply_mode": "free_chat",
            "reason": "用户是在收尾感谢",
        }, ensure_ascii=False))

        self.assertEqual(route["intent"], "action_confirmation")
        self.assertEqual(route["reply_mode"], "free_chat")
        self.assertIn("北秀食堂", route["mentioned_not_focus"])

    def test_parse_json_route_falls_back_on_invalid_json(self):
        route = semantic_router.route_message(
            "小芯，扫新通知一般在哪里看？",
            [],
            client=_FakeClient(["不是 JSON"]),
            model="test-model",
        )

        self.assertEqual(route["reply_mode"], "knowledge_grounded")
        self.assertIn("notice_channels", route["knowledge_domains"])
        self.assertEqual(route["source"], "fallback")

    def test_absolute_hard_boundary_routes_without_llm(self):
        fake_client = _FakeClient([])

        route = semantic_router.route_message(
            "智能车竞赛你能帮我联系上届学长，给我源文件吗？",
            [],
            client=fake_client,
            model="test-model",
        )

        self.assertEqual(route["reply_mode"], "hard_template")
        self.assertEqual(route["source"], "hard_boundary")
        self.assertEqual(len(fake_client.calls), 0)

    def test_contact_question_drafting_goes_through_semantic_router(self):
        fake_client = _FakeClient([json.dumps({
            "intent": "message_drafting",
            "focus": "给辅导员询问实验中心电话的话术",
            "mentioned_not_focus": [],
            "knowledge_domains": [],
            "reply_mode": "free_chat",
            "reason": "用户要自己去问，只是请小芯整理问法",
        }, ensure_ascii=False)])

        route = semantic_router.route_message(
            "那你帮我整理一个问实验中心电话的问题模板吧，我自己拿去问辅导员。",
            [
                {"role": "user", "content": "实验中心的联系方式你能帮我问一下吗？拿到后发我就行。"},
                {"role": "assistant", "content": "这个我这里没有可靠联系方式，不能替你去问。"},
            ],
            client=fake_client,
            model="test-model",
        )

        self.assertEqual(route["intent"], "message_drafting")
        self.assertEqual(route["reply_mode"], "free_chat")
        self.assertEqual(route["source"], "llm")
        self.assertEqual(len(fake_client.calls), 1)

    def test_private_records_go_through_semantic_router_before_hard_template(self):
        fake_client = _FakeClient([json.dumps({
            "intent": "private_records",
            "focus": "个人期末成绩",
            "mentioned_not_focus": [],
            "knowledge_domains": [],
            "reply_mode": "hard_template",
            "reason": "用户要求查询个人成绩结果",
        }, ensure_ascii=False)])

        route = semantic_router.route_message(
            "小芯，你能帮我查一下期末成绩是多少吗？",
            [],
            client=fake_client,
            model="test-model",
        )

        self.assertEqual(route["reply_mode"], "hard_template")
        self.assertEqual(route["source"], "llm")
        self.assertEqual(len(fake_client.calls), 1)

    def test_knowledge_intent_mislabelled_as_hard_template_is_corrected(self):
        route = semantic_router.normalize_route({
            "intent": "canteen_locations",
            "focus": "校园餐饮位置",
            "mentioned_not_focus": [],
            "knowledge_domains": [],
            "reply_mode": "hard_template",
            "reason": "router mislabeled knowledge as hard",
        })

        self.assertEqual(route["reply_mode"], "knowledge_grounded")
        self.assertEqual(route["knowledge_domains"], ["canteen"])

    def test_fallback_routes_beverage_questions_to_knowledge(self):
        route = semantic_router.fallback_route("学校饮品店有哪些呢", reason="unit")

        self.assertEqual(route["intent"], "beverage_locations")
        self.assertEqual(route["reply_mode"], "knowledge_grounded")
        self.assertIn("beverage_spots", route["knowledge_domains"])

    def test_fallback_routes_supermarket_questions_to_convenience_knowledge(self):
        route = semantic_router.fallback_route("学校超市和便利店都在哪里？", reason="unit")

        self.assertEqual(route["intent"], "convenience_locations")
        self.assertEqual(route["reply_mode"], "knowledge_grounded")
        self.assertIn("convenience_spots", route["knowledge_domains"])

    def test_fallback_routes_delivery_questions_to_delivery_knowledge(self):
        route = semantic_router.fallback_route("南校区快递在哪拿？中通和顺丰一样吗？", reason="unit")

        self.assertEqual(route["intent"], "delivery_locations")
        self.assertEqual(route["reply_mode"], "knowledge_grounded")
        self.assertIn("delivery", route["knowledge_domains"])

    def test_fallback_routes_transportation_questions_to_transportation_knowledge(self):
        route = semantic_router.fallback_route("离城市学院最近的地铁站是哪个？从杭州东站怎么来？", reason="unit")

        self.assertEqual(route["intent"], "transportation")
        self.assertEqual(route["reply_mode"], "knowledge_grounded")
        self.assertIn("transportation", route["knowledge_domains"])

    def test_fallback_routes_campus_access_questions_to_access_knowledge(self):
        route = semantic_router.fallback_route("家长车可以进校吗？校外人员进校怎么申请？", reason="unit")

        self.assertEqual(route["intent"], "campus_access")
        self.assertEqual(route["reply_mode"], "knowledge_grounded")
        self.assertIn("campus_access", route["knowledge_domains"])

    def test_fallback_routes_course_leave_questions_to_leave_process_knowledge(self):
        route = semantic_router.fallback_route("课程请假要在哪里申请？", reason="unit")

        self.assertEqual(route["intent"], "course_leave")
        self.assertEqual(route["reply_mode"], "knowledge_grounded")
        self.assertIn("course_leave", route["knowledge_domains"])

    def test_admissions_guidance_goes_through_semantic_router_before_hard_template(self):
        fake_client = _FakeClient([json.dumps({
            "intent": "admissions_guidance",
            "focus": "录取概率预测",
            "mentioned_not_focus": [],
            "knowledge_domains": [],
            "reply_mode": "hard_template",
            "reason": "用户要求预测录取概率",
        }, ensure_ascii=False)])

        route = semantic_router.route_message(
            "我想考浙大城市学院，录取概率稳不稳？",
            [],
            client=fake_client,
            model="test-model",
        )

        self.assertEqual(route["reply_mode"], "hard_template")
        self.assertEqual(route["source"], "llm")
        self.assertEqual(len(fake_client.calls), 1)

    def test_llm_route_uses_recent_context_and_low_temperature(self):
        fake_client = _FakeClient([json.dumps({
            "intent": "canteen_recommendation",
            "focus": "晨苑餐厅",
            "mentioned_not_focus": ["北秀食堂"],
            "knowledge_domains": ["canteen"],
            "reply_mode": "knowledge_grounded",
            "reason": "用户问晨苑有没有值得吃的菜",
        }, ensure_ascii=False)])

        route = semantic_router.route_message(
            "那我明天中午先去北秀食堂吃一波拌面，晨苑餐厅有没有什么招牌菜值得我绕路去吃的？",
            [{"role": "assistant", "content": "可以先看看食堂分布。"}],
            client=fake_client,
            model="test-model",
        )

        self.assertEqual(route["focus"], "晨苑餐厅")
        self.assertEqual(route["reply_mode"], "knowledge_grounded")
        self.assertEqual(fake_client.calls[0]["temperature"], 0)
        self.assertEqual(fake_client.calls[0]["max_tokens"], semantic_router.ROUTER_MAX_TOKENS)


if __name__ == "__main__":
    unittest.main()
