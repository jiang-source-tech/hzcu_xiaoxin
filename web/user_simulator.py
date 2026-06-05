"""User simulator LLM for relationship self-play v2.

Given a character card + situational intent, generates natural user messages
via DeepSeek API. Each call produces a different message (controlled by
temperature and seed).
"""

from __future__ import annotations

import os
import random
from typing import Any

from openai import OpenAI


_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
_USER_MAX_TOKENS = int(os.getenv("STUDENT_MAX_TOKENS", "300"))


def _build_client() -> OpenAI:
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
        f"你是小信的测试用户，用来模拟真实新生与小信对话。\n\n"
        f"【你的角色设定】\n{character['traits']}\n\n"
        f"【本轮任务】{intent}{forbidden}\n"
        f"{history_block}\n\n"
        f"请用你自己的话，自然地发一条消息给小信。只输出消息本身，不要带任何前缀、"
        f"标签或角色名。像真实聊天一样，1-2句话。"
    )

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": "（按设定生成你的下一条消息）"},
    ]


def _call_api(messages: list[dict[str, str]], seed: int) -> str:
    client = _build_client()
    response = client.chat.completions.create(
        model=_MODEL,
        messages=messages,
        temperature=0.9,
        max_tokens=_USER_MAX_TOKENS,
        seed=seed,
    )
    return response.choices[0].message.content.strip()


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

    raw = _call_api(messages, seed)
    # Drop any accidental role prefix
    for prefix in ("新生:", "新生：", "学生:", "学生：", "用户:", "用户："):
        if raw.startswith(prefix):
            raw = raw[len(prefix):].strip()
    return raw
