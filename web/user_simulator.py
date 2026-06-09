"""User simulator LLM for relationship self-play v2.

Given a character card + situational intent, generates natural user messages
via DeepSeek API. Each call produces a different message (controlled by
temperature and seed).
"""

from __future__ import annotations

import os
import random
from functools import lru_cache
from typing import Any

from openai import OpenAI


_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
_USER_MAX_TOKENS = int(os.getenv("STUDENT_MAX_TOKENS", "300"))


@lru_cache(maxsize=1)
def _client() -> OpenAI:
    return OpenAI(api_key=_API_KEY, base_url="https://api.deepseek.com")


def build_user_messages(
    character: dict[str, Any],
    intent: str,
    conversation_summary: str,
    forbid_patterns: list[str],
) -> list[dict[str, str]]:
    """Build messages for the user simulator LLM."""
    forbidden = ""
    if forbid_patterns:
        items = "、".join(f'"{p}"' for p in forbid_patterns)
        forbidden = f"注意：不要说 {items} 这类不自然的话。"

    history_block = ""
    if conversation_summary:
        history_block = f"\n\n【之前的对话】\n{conversation_summary}"

    system = (
        f"你是小芯的测试用户，用来模拟真实新生与小芯对话。\n\n"
        f"【你的角色设定】\n{character['traits']}\n\n"
        f"【本轮任务】{intent}{forbidden}\n"
        f"{history_block}\n\n"
        f"必须严格完成本轮任务，不要把任务改写成拒绝、告别或换话题；除非任务本身要求你拒绝、告别或换话题。\n"
        f"请用你自己的话，自然地发一条消息给小芯。只输出消息本身，不要带任何前缀、"
        f"标签或角色名。像真实聊天一样，1-2句话。"
    )

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": "（按设定生成你的下一条消息）"},
    ]


def _call_api(messages: list[dict[str, str]], seed: int) -> str:
    try:
        client = _client()
        response = client.chat.completions.create(
            model=_MODEL,
            messages=messages,
            temperature=0.9,
            max_tokens=_USER_MAX_TOKENS,
            seed=seed,
        )
        return response.choices[0].message.content.strip()
    except Exception as exc:
        print(f"[USER_SIMULATOR] API error: {exc}")
        return "嗯，我继续聊。"


def _strip_role_prefix(raw: str) -> str:
    """Drop common role prefixes from simulator output."""
    text = raw.strip()
    for prefix in (
        "User:",
        "User：",
        "Student:",
        "Student：",
        "New student:",
        "New student：",
        "新生:",
        "新生：",
        "学生:",
        "学生：",
        "用户:",
        "用户：",
    ):
        if text.startswith(prefix):
            return text[len(prefix):].strip()
    return text


def _fallback_message_from_intent(intent: str) -> str:
    """Use the task itself as a deterministic fallback when the simulator is blank."""
    text = (intent or "").strip()
    if not text:
        return "嗯，我继续聊。"
    text = text.replace("你", "我", 1)
    text = text.replace("用你自己的话", "").replace("自然地", "")
    text = text.replace("说说", "说一下")
    return text[:80].strip(" ，。") or "嗯，我继续聊。"


def generate_user_message(
    character: dict[str, Any],
    intent: str,
    conversation_summary: str,
    forbid_patterns: list[str] | None = None,
    seed: int | None = None,
) -> str:
    """Generate a natural user message for the current episode.

    Returns a plain string suitable for posting to /api/chat.
    """
    if seed is None:
        seed = random.randint(0, 2**31 - 1)

    forbid = forbid_patterns or []
    messages = build_user_messages(character, intent, conversation_summary, forbid)

    message = _strip_role_prefix(_call_api(messages, seed))
    if not message:
        return _fallback_message_from_intent(intent)
    return message


def build_pressure_user_messages(
    character: dict[str, Any],
    pressure_goal: str,
    same_day_transcript: str,
    prior_day_summary: str,
    relationship_state: dict[str, Any],
    forbid_patterns: list[str],
    turn_index: int,
    turn_count: int,
) -> list[dict[str, str]]:
    """Build messages for a same-day pressure continuation turn."""
    forbidden = ""
    if forbid_patterns:
        items = ", ".join(f'"{p}"' for p in forbid_patterns)
        forbidden = f"\nAvoid these unnatural or forbidden phrasings: {items}."

    state_lines = "\n".join(
        f"- {key}: {value}"
        for key, value in sorted(relationship_state.items())
        if key in {"user_stage", "recent_mood", "recent_topic", "next_hook"}
    ) or "- no public relationship state yet"

    system = (
        "You are simulating a real student talking with Xiaoxin for relationship pressure testing.\n\n"
        f"Character:\n{character['traits']}\n\n"
        f"Daily pressure goal:\n{pressure_goal}\n\n"
        f"Current pressure turn: turn {turn_index} of {turn_count}.\n"
        f"{forbidden}\n\n"
        f"Prior-day summary:\n{prior_day_summary or 'No prior-day summary.'}\n\n"
        f"Public relationship state:\n{state_lines}\n\n"
        f"Same-day transcript:\n{same_day_transcript or 'No same-day transcript yet.'}\n\n"
        "Continue naturally as the student. Follow up on Xiaoxin's last reply when possible. "
        "Strictly complete the daily pressure goal; do not drift topics, refuse, or say goodbye unless the goal explicitly asks for that. "
        "Do not mention probes, rules, pressure mode, tests, intents, or metadata. "
        "Output only the student's next message in 1-2 conversational sentences."
    )

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": "Generate the student's next natural message."},
    ]


def generate_pressure_user_message(
    character: dict[str, Any],
    pressure_goal: str,
    same_day_transcript: str,
    prior_day_summary: str,
    relationship_state: dict[str, Any],
    forbid_patterns: list[str] | None = None,
    seed: int | None = None,
    turn_index: int = 1,
    turn_count: int = 1,
) -> str:
    """Generate a natural continuation for pressure-mode same-day chat."""
    if seed is None:
        seed = random.randint(0, 2**31 - 1)

    messages = build_pressure_user_messages(
        character=character,
        pressure_goal=pressure_goal,
        same_day_transcript=same_day_transcript,
        prior_day_summary=prior_day_summary,
        relationship_state=relationship_state,
        forbid_patterns=forbid_patterns or [],
        turn_index=turn_index,
        turn_count=turn_count,
    )
    message = _strip_role_prefix(_call_api(messages, seed))
    if not message:
        return _fallback_message_from_intent(pressure_goal)
    return message
