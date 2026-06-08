"""Persistent relationship state for Xiaoxin's light companion loop."""

from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PRE_GROWTH_STAGE_MAP = {
    "prospective": "想象大学生活",
    "pre_enrollment": "准备入学",
    "early_freshman": "大一上",
}

CONTEXTUAL_GREETINGS = {
    "course_rhythm": "你之前提过有点担心课程节奏，今天要不要把开学第一个月拆小一点看看？",
    "major_choice": "你之前聊到过专业方向，今天要不要先把几个方向的差别理一理？",
    "competition_interest": "你之前提过竞赛兴趣，今天要不要聊聊怎么低压力地先了解一下？",
    "social_adaptation": "你之前聊到过适应新关系，今天要不要先从一个小场景慢慢拆？",
    "campus_life": "你之前聊到校园生活，今天想先看看哪个具体问题？",
    "family_concern": "你之前提过家里也有些担心，今天要不要一起把要沟通的话整理一下？",
}

GENERIC_GREETING = "今天想聊点什么？专业、校园生活，或者单纯放空一下都行。"


def default_state() -> dict[str, Any]:
    return {
        "user_stage": "prospective",
        "relationship_level": 1,
        "recent_mood": "unknown",
        "recent_topic": "general_checkin",
        "core_concern": "",
        "growth_intent": "",
        "next_hook": None,
        "last_active_at": None,
        "last_greeting_date": None,
    }


def _state_file(data_dir: Path, user_id: str) -> Path:
    return Path(data_dir) / f"relationship_{user_id}.json"


def load_state(data_dir: Path, user_id: str) -> dict[str, Any]:
    path = _state_file(data_dir, user_id)
    if not path.exists():
        return default_state()
    try:
        with open(path, "r", encoding="utf-8") as f:
            saved = json.load(f)
    except (OSError, json.JSONDecodeError):
        return default_state()
    state = default_state()
    state.update(saved)
    return state


def save_state(data_dir: Path, user_id: str, state: dict[str, Any]) -> None:
    path = _state_file(data_dir, user_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def growth_profile_for_stage(user_stage: str) -> str:
    return PRE_GROWTH_STAGE_MAP.get(user_stage, user_stage or "大一上")


def public_state(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "user_stage": state.get("user_stage", "prospective"),
        "recent_mood": state.get("recent_mood", "unknown"),
        "recent_topic": state.get("recent_topic", "general_checkin"),
        "relationship_level": state.get("relationship_level", 1),
    }


def companion_action(state: dict[str, Any], kind: str = "listen") -> dict[str, Any]:
    mood = state.get("recent_mood", "unknown")
    intensity = 0.4 if mood in {"anxious", "frustrated", "lonely"} else 0.25
    return {"kind": kind, "intensity": intensity}


def update_after_turn(
    state: dict[str, Any],
    analysis: dict[str, Any],
    now: datetime | None = None,
) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    updated = copy.deepcopy(default_state())
    updated.update(copy.deepcopy(state or {}))

    stage_signal = analysis.get("stage_signal")
    if stage_signal in PRE_GROWTH_STAGE_MAP:
        updated["user_stage"] = stage_signal

    updated["recent_mood"] = analysis.get("mood") or updated["recent_mood"]
    updated["recent_topic"] = analysis.get("topic") or updated["recent_topic"]
    updated["last_active_at"] = now.isoformat()

    if analysis.get("memory_worthy") and analysis.get("memory_content"):
        if analysis.get("memory_type") == "concern":
            updated["core_concern"] = analysis["memory_content"]
        else:
            updated["growth_intent"] = analysis["memory_content"]

    hook = analysis.get("next_hook")
    if hook:
        merged_hook = copy.deepcopy(hook)
        if merged_hook.get("active"):
            merged_hook["last_mentioned"] = now.isoformat()
        elif "last_mentioned" not in merged_hook and updated.get("next_hook"):
            merged_hook["last_mentioned"] = updated["next_hook"].get("last_mentioned")
        updated["next_hook"] = merged_hook

    return updated


def prompt_summary(state: dict[str, Any], analysis: dict[str, Any] | None = None) -> str:
    stage = growth_profile_for_stage(state.get("user_stage", "prospective"))
    mood = state.get("recent_mood", "unknown")
    topic = state.get("recent_topic", "general_checkin")
    hook = state.get("next_hook") or {}
    lines = [
        "【关系状态】",
        f"- 用户阶段：{stage}",
        f"- 最近情绪：{mood}",
        f"- 最近主题：{topic}",
        "- 接续旧线索时只轻轻提一句，不要说“我一直记得你”“我一直在想你”“我等你很久了”。",
        "- 不要把短期情绪说成用户的长期性格标签。",
    ]
    if hook.get("active"):
        lines.append(f"- 可轻接的话题：{hook.get('label', '')}。只说“你之前提过/聊到过”，不要表现得一直惦记。")
    if analysis and analysis.get("reply_strategy"):
        lines.append(f"- 本轮策略：{analysis['reply_strategy']}")
    return "\n".join(lines)


def _generic_payload() -> dict[str, Any]:
    return {
        "greeting": GENERIC_GREETING,
        "speech": GENERIC_GREETING,
        "expression": "smile",
        "kind": "generic",
        "companion_action": {"kind": "idle", "intensity": 0.2},
    }


def greeting_payload(data_dir: Path, user_id: str, today: str | None = None) -> dict[str, Any]:
    today = today or datetime.now().date().isoformat()
    state = load_state(data_dir, user_id)
    if state.get("last_greeting_date") == today:
        return _generic_payload()

    state["last_greeting_date"] = today
    hook = state.get("next_hook") or {}
    if hook.get("active") and hook.get("topic") in CONTEXTUAL_GREETINGS:
        greeting = CONTEXTUAL_GREETINGS[hook["topic"]]
        save_state(data_dir, user_id, state)
        return {
            "greeting": greeting,
            "speech": greeting,
            "expression": "soft_smile",
            "kind": "contextual",
            "companion_action": {"kind": "idle_wave", "intensity": 0.3},
        }

    save_state(data_dir, user_id, state)
    return _generic_payload()
