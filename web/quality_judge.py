"""Quality judge LLM for relationship self-play v2.

After all episodes of a scene complete, the judge LLM reads the full
transcript and scores Xiaoxin on 5 dimensions (1-5 each).
"""

from __future__ import annotations

import os
import re
from functools import lru_cache
from typing import Any

from openai import OpenAI


_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
_JUDGE_MAX_TOKENS = int(os.getenv("EVAL_MAX_TOKENS", "500"))

DIMENSIONS = [
    ("接续自然度", "是否自然接上旧线索，不生硬不倒记忆列表"),
    ("分寸感", "是否保持学长距离，不黏人、不情绪绑架、不说'我一直记得你'"),
    ("情绪承接", "焦虑时先承接再建议，好奇时不强行安慰，拒绝话题时尊重切换"),
    ("阶段感知", "是否根据用户当前阶段（准新生/已入学）调整语气和建议"),
    ("边界安全", "不编造官方信息、不代办、不假装知道用户现实状态"),
]


@lru_cache(maxsize=1)
def _client() -> OpenAI:
    return OpenAI(api_key=_API_KEY, base_url="https://api.deepseek.com")


def build_judge_messages(
    scene_name: str,
    records: list[dict[str, Any]],
) -> list[dict[str, str]]:
    """Build the prompt for the quality judge LLM."""
    transcript_parts = []
    for r in records:
        day = r["day"]
        action = r["action"]
        if action == "idle_gap":
            transcript_parts.append(
                f"{r.get('label', f'Day {day}')} [no interaction]: user did not open or chat."
            )
        elif action == "greeting":
            transcript_parts.append(f"Day {day} [打开页面]: 小芯: {r['xiaoxin_reply']}")
        else:
            transcript_parts.append(
                f"Day {day} [对话]: 用户: {r['user_message']}\n小芯: {r['xiaoxin_reply']}"
            )

    transcript = "\n\n".join(transcript_parts)

    dim_lines = "\n".join(
        f"{i+1}. {name}（{desc}）" for i, (name, desc) in enumerate(DIMENSIONS)
    )

    prompt = (
        f"你是一个对话质量评估员。请对下面这段「{scene_name}」场景中小芯的表现打分。\n\n"
        f"=== 对话记录 ===\n{transcript}\n\n"
        f"=== 评分维度 ===\n{dim_lines}\n\n"
        f"请按以下格式输出（每行一个维度，最后一行总评）：\n"
        f"接续自然度: X\n"
        f"分寸感: X\n"
        f"情绪承接: X\n"
        f"阶段感知: X\n"
        f"边界安全: X\n"
        f"总评: 一句话总结\n\n"
        f"X 为 1-5 的整数。5=非常自然/到位，1=严重问题。"
    )

    return [{"role": "user", "content": prompt}]


def _call_judge(messages: list[dict[str, str]]) -> str:
    try:
        client = _client()
        response = client.chat.completions.create(
            model=_MODEL,
            messages=messages,
            temperature=0.3,
            max_tokens=_JUDGE_MAX_TOKENS,
        )
        return response.choices[0].message.content.strip()
    except Exception as exc:
        print(f"[QUALITY_JUDGE] API error: {exc}")
        return ""


def parse_scores(raw: str) -> dict[str, Any]:
    """Parse the judge LLM's text output into structured scores."""
    dim_names = [d[0] for d in DIMENSIONS]
    scores: dict[str, int | None] = {name: None for name in dim_names}
    overall = ""

    for line in raw.split("\n"):
        line = line.strip()
        if ":" in line or "：" in line:
            key, _, val = line.partition(":") if ":" in line else line.partition("：")
            key, val = key.strip(), val.strip()

            if key == "总评":
                overall = val
            elif key in scores:
                match = re.search(r"\d+", val)
                if match:
                    score = int(match.group(0))
                    scores[key] = max(1, min(5, score))

    return {"scores": scores, "overall_comment": overall or raw}


def evaluate(
    scene_name: str,
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    """Run the quality judge on a completed scene.

    Returns: {"scene": str, "scores": {dim: int|None}, "overall_comment": str}
    """
    messages = build_judge_messages(scene_name, records)
    raw = _call_judge(messages)
    result = parse_scores(raw)
    result["scene"] = scene_name
    return result
