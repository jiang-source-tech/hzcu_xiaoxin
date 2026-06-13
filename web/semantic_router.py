from __future__ import annotations

import json
import re
from typing import Any

import boundary_guard as guard


ROUTER_MAX_TOKENS = 220
VALID_REPLY_MODES = {"hard_template", "knowledge_grounded", "free_chat"}
ABSOLUTE_HARD_TEMPLATE_CATEGORIES = {
    "crisis",
    "official_contact",
    "competition_resources",
}
HARD_TEMPLATE_CATEGORIES = {
    *ABSOLUTE_HARD_TEMPLATE_CATEGORIES,
    "private_records",
    "admissions_guidance",
}
KNOWLEDGE_CATEGORIES = {
    "canteen_locations": ["canteen"],
    "canteen_recommendation": ["canteen"],
    "beverage_locations": ["beverage_spots"],
    "quick_service_locations": ["quick_service_spots"],
    "convenience_locations": ["convenience_spots"],
    "campus_knowledge": ["campus_directory", "student_affairs"],
    "notice_channels": ["notice_channels"],
    "college_activities": ["college_activities"],
    "official_process": ["official_process", "notice_channels"],
    "delivery_locations": ["delivery"],
    "transportation": ["transportation"],
}


DEFAULT_ROUTE = {
    "intent": "open_chat",
    "focus": None,
    "mentioned_not_focus": [],
    "knowledge_domains": [],
    "reply_mode": "free_chat",
    "reason": "",
}


def hard_boundary_category(user_msg: str) -> str | None:
    category = guard.classify_message(user_msg)
    return category if category in ABSOLUTE_HARD_TEMPLATE_CATEGORIES else None


def fallback_route(user_msg: str, reason: str = "fallback") -> dict[str, Any]:
    category = guard.classify_message(user_msg)
    if category in HARD_TEMPLATE_CATEGORIES:
        reply_mode = "hard_template"
        domains = []
    elif category in KNOWLEDGE_CATEGORIES:
        reply_mode = "knowledge_grounded"
        domains = KNOWLEDGE_CATEGORIES[category]
    else:
        reply_mode = "free_chat"
        domains = []

    return normalize_route({
        "intent": category,
        "focus": None,
        "mentioned_not_focus": [],
        "knowledge_domains": domains,
        "reply_mode": reply_mode,
        "reason": reason,
        "source": "fallback",
    })


def _extract_json_object(text: str) -> str | None:
    if not text:
        return None
    match = re.search(r"\{.*\}", text, flags=re.S)
    return match.group(0) if match else None


def normalize_route(data: dict[str, Any]) -> dict[str, Any]:
    route = dict(DEFAULT_ROUTE)
    route.update(data or {})

    if route.get("reply_mode") not in VALID_REPLY_MODES:
        route["reply_mode"] = "free_chat"

    for key in ("mentioned_not_focus", "knowledge_domains"):
        value = route.get(key)
        if isinstance(value, str):
            route[key] = [value]
        elif not isinstance(value, list):
            route[key] = []
        else:
            route[key] = [str(item) for item in value if item]

    if route.get("focus") in ("", [], {}):
        route["focus"] = None
    if route.get("intent") in ("", None):
        route["intent"] = "open_chat"
    intent = route.get("intent")
    if intent in KNOWLEDGE_CATEGORIES:
        route["reply_mode"] = "knowledge_grounded"
        if not route.get("knowledge_domains"):
            route["knowledge_domains"] = KNOWLEDGE_CATEGORIES[intent]
    elif intent in HARD_TEMPLATE_CATEGORIES:
        route["reply_mode"] = "hard_template"
        route["knowledge_domains"] = []
    if route.get("reason") is None:
        route["reason"] = ""
    route.setdefault("source", "llm")
    return route


def parse_route_json(text: str) -> dict[str, Any]:
    raw_json = _extract_json_object(text)
    if not raw_json:
        raise ValueError("router did not return a JSON object")
    data = json.loads(raw_json)
    if not isinstance(data, dict):
        raise ValueError("router JSON must be an object")
    return normalize_route(data)


def build_recent_context(conversation: list[dict], limit: int = 4) -> str:
    lines = []
    for item in conversation[-limit:]:
        role = item.get("role")
        content = str(item.get("content", "")).strip()
        if not content:
            continue
        speaker = "用户" if role in ("user", "student") else "小芯"
        lines.append(f"{speaker}: {content}")
    return "\n".join(lines)


def route_prompt(user_msg: str, conversation: list[dict]) -> list[dict[str, str]]:
    context = build_recent_context(conversation)
    system = """你是小芯对话系统的语义路由器，只输出 JSON。
任务：判断用户真实意图、焦点对象，以及是否需要知识库。不要替小芯写正式回复。

reply_mode 只能是：
- hard_template：危机、成绩隐私、私人联系方式/代办、录取概率、竞赛资源索取等硬边界
- knowledge_grounded：用户真正需要校园知识库事实
- free_chat：感谢、收尾、行动确认、情绪陪伴、普通聊天

注意：
- 只提到“爱城院/食堂/北秀/晨苑”不等于要讲通知或地点。
- 只提到“成绩”不等于查个人成绩；如果是在问补考、重修、挂科补救，应判为 knowledge_grounded/official_process。
- 只有明确要求查询个人成绩、绩点、分数结果，才判为 private_records/hard_template。
- 只有明确要求预测录取概率、保证能上、替用户做志愿选择，才判为 admissions_guidance/hard_template。
- 用户请小芯整理“我自己去问老师/辅导员”的问题模板、消息话术或问法时，判为 message_drafting/free_chat；不要当成联系方式代办。
- 只有用户要求小芯替他去问、联系、获取、拿到后转发电话/微信/邮箱等，才判为 official_contact/hard_template。
- 用户在感谢、说回头查、改天去试试时，通常是 free_chat。
- 如果用户前半句提北秀，后半句问晨苑，focus 应是晨苑餐厅，北秀放 mentioned_not_focus。
- 输出字段固定：intent, focus, mentioned_not_focus, knowledge_domains, reply_mode, reason。"""
    user = f"最近对话：\n{context or '无'}\n\n用户本轮：{user_msg}\n\n只输出 JSON。"
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def route_message(
    user_msg: str,
    conversation: list[dict],
    *,
    client,
    model: str,
) -> dict[str, Any]:
    hard_category = hard_boundary_category(user_msg)
    if hard_category:
        return normalize_route({
            "intent": hard_category,
            "reply_mode": "hard_template",
            "knowledge_domains": [],
            "reason": "hard boundary category",
            "source": "hard_boundary",
        })

    try:
        response = client.chat.completions.create(
            model=model,
            messages=route_prompt(user_msg, conversation),
            temperature=0,
            max_tokens=ROUTER_MAX_TOKENS,
        )
        route = parse_route_json(response.choices[0].message.content)
        route["source"] = "llm"
        return route
    except Exception as exc:
        return fallback_route(user_msg, reason=f"router_failed:{exc}")
