"""Persistent relationship state for Xiaoxin's light companion loop.

v2: adds followups system for tracking user concerns/decisions/events across conversations.
"""

from __future__ import annotations

import copy
import json
import hashlib
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

_FOLLOWUP_KINDS = ("concern", "decision", "event")
_FOLLOWUP_STATUSES = ("active", "resolved", "archived")
_MAX_ACTIVE_FOLLOWUPS = 8
_MAX_FOLLOWUP_AGE_DAYS = 60  # 超过 60 天自动 archive


PET_STATE_DEFAULTS = {
    "mood": "calm",
    "energy": 70,
    "bond": 0,
    "relationship_stage": "first_meet",
    "presence_mode": "idle",
    "last_seen_at": None,
}

_PET_MOODS = {"calm", "happy", "worried", "sleepy", "excited", "lonely_light"}
_PRESENCE_MODES = {"idle", "listening", "caring", "celebrating", "resting", "reunion"}


def default_state() -> dict[str, Any]:
    return {
        "user_stage": "prospective",
        "relationship_level": 1,
        "recent_mood": "unknown",
        "recent_topic": "general_checkin",
        "core_concern": "",
        "growth_intent": "",
        "next_hook": None,
        "followups": [],
        "growth_timeline": [],
        "pet_state": copy.deepcopy(PET_STATE_DEFAULTS),
        "last_active_at": None,
        "last_greeting_date": None,
    }


def _relationship_stage_for(bond: int, growth_count: int, active_followup_count: int) -> str:
    if bond >= 60 and growth_count >= 3:
        return "old_friend"
    if bond >= 28 or growth_count >= 2:
        return "companion"
    if bond >= 8 or active_followup_count > 0 or growth_count >= 1:
        return "familiar"
    return "first_meet"


def normalize_pet_state(pet_state: dict[str, Any] | None, state: dict[str, Any] | None = None) -> dict[str, Any]:
    normalized = copy.deepcopy(PET_STATE_DEFAULTS)
    if isinstance(pet_state, dict):
        normalized.update({k: v for k, v in pet_state.items() if k in normalized})

    if normalized["mood"] not in _PET_MOODS:
        normalized["mood"] = "calm"
    if normalized["presence_mode"] not in _PRESENCE_MODES:
        normalized["presence_mode"] = "idle"

    try:
        normalized["energy"] = max(0, min(100, int(normalized.get("energy", 70))))
    except (TypeError, ValueError):
        normalized["energy"] = 70
    try:
        normalized["bond"] = max(0, min(100, int(normalized.get("bond", 0))))
    except (TypeError, ValueError):
        normalized["bond"] = 0

    growth_count = 0
    active_followup_count = 0
    if isinstance(state, dict):
        growth_count = len(state.get("growth_timeline") or [])
        active_followup_count = len([f for f in state.get("followups", []) if f.get("status") == "active"])
    normalized["relationship_stage"] = _relationship_stage_for(
        normalized["bond"], growth_count, active_followup_count
    )
    return normalized


def normalize_state(state: dict[str, Any] | None) -> dict[str, Any]:
    normalized = copy.deepcopy(default_state())
    if isinstance(state, dict):
        normalized.update(copy.deepcopy(state))
    if not isinstance(normalized.get("followups"), list):
        normalized["followups"] = []
    if not isinstance(normalized.get("growth_timeline"), list):
        normalized["growth_timeline"] = []
    normalized["pet_state"] = normalize_pet_state(normalized.get("pet_state"), normalized)
    return normalized


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
    return normalize_state(saved)


def save_state(data_dir: Path, user_id: str, state: dict[str, Any]) -> None:
    path = _state_file(data_dir, user_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def growth_profile_for_stage(user_stage: str) -> str:
    return PRE_GROWTH_STAGE_MAP.get(user_stage, user_stage or "大一上")


def public_state(state: dict[str, Any]) -> dict[str, Any]:
    state = normalize_state(state)
    return {
        "user_stage": state.get("user_stage", "prospective"),
        "recent_mood": state.get("recent_mood", "unknown"),
        "recent_topic": state.get("recent_topic", "general_checkin"),
        "relationship_level": state.get("relationship_level", 1),
        "active_followups": len([f for f in state.get("followups", []) if f.get("status") == "active"]),
        "pet_state": state.get("pet_state", copy.deepcopy(PET_STATE_DEFAULTS)),
        "growth_count": len(state.get("growth_timeline", [])),
    }


def companion_action(state: dict[str, Any], kind: str = "listen") -> dict[str, Any]:
    state = normalize_state(state)
    pet_state = state.get("pet_state", {})
    mode = pet_state.get("presence_mode")
    if mode == "celebrating":
        return {"kind": "celebrate", "intensity": 0.55}
    if mode == "caring":
        return {"kind": "lean_in", "intensity": 0.45}
    if mode == "reunion":
        return {"kind": "idle_wave", "intensity": 0.35}
    mood = state.get("recent_mood", "unknown")
    intensity = 0.4 if mood in {"anxious", "frustrated", "lonely"} else 0.25
    return {"kind": kind, "intensity": intensity}


# ─── Followups ──────────────────────────────────────────────────────────


def _followup_id(label: str) -> str:
    digest = hashlib.md5(label.encode()).hexdigest()[:8]
    return f"fw_{digest}"


def upsert_followup(
    state: dict[str, Any],
    kind: str,
    label: str,
    context: str = "",
    intensity: str = "medium",
    topic: str = "general_checkin",
) -> dict[str, Any]:
    """创建或更新一个 followup。相同 label 会自动去重合并。"""
    now = datetime.now(timezone.utc).isoformat()
    fid = _followup_id(label)
    followups = state.get("followups", [])

    # 查找已有的同 id followup
    for fw in followups:
        if fw.get("id") == fid:
            fw["last_updated"] = now
            fw["mention_count"] = fw.get("mention_count", 1) + 1
            fw["context"] = context or fw.get("context", "")
            fw["status"] = "active"  # re-activate if it was resolved
            # 提升 intensity: low→medium→high
            if intensity == "high" or fw.get("mention_count", 0) >= 3:
                fw["intensity"] = "high"
            elif intensity == "medium" or fw.get("mention_count", 0) >= 2:
                fw["intensity"] = max(
                    fw.get("intensity", "low"),
                    intensity,
                    key=lambda x: {"low": 0, "medium": 1, "high": 2}.get(x, 0),
                )
            state["followups"] = followups
            return state

    # 新建 followup
    if kind not in _FOLLOWUP_KINDS:
        kind = "concern"
    new_fw = {
        "id": fid,
        "kind": kind,
        "label": label,
        "context": context,
        "intensity": intensity,
        "topic": topic,
        "first_seen": now,
        "last_updated": now,
        "mention_count": 1,
        "status": "active",
    }
    followups.append(new_fw)

    # 限制数量：超过时移除最旧的 inactive
    active_count = sum(1 for f in followups if f.get("status") == "active")
    if active_count > _MAX_ACTIVE_FOLLOWUPS:
        # archive oldest low-intensity followups
        candidates = sorted(
            [f for f in followups if f.get("status") == "active" and f.get("intensity") == "low"],
            key=lambda f: f.get("last_updated", ""),
        )
        for c in candidates[: active_count - _MAX_ACTIVE_FOLLOWUPS]:
            c["status"] = "archived"

    state["followups"] = followups
    return state


def resolve_followup(state: dict[str, Any], label: str) -> dict[str, Any]:
    """标记一个 followup 为已解决。"""
    fid = _followup_id(label)
    followups = state.get("followups", [])
    for fw in followups:
        if fw.get("id") == fid:
            fw["status"] = "resolved"
            fw["last_updated"] = datetime.now(timezone.utc).isoformat()
            break
    state["followups"] = followups
    return state


def _archive_stale_followups(state: dict[str, Any]):
    """自动归档过期的 followups。"""
    now = datetime.now(timezone.utc)
    followups = state.get("followups", [])
    for fw in followups:
        if fw.get("status") != "active":
            continue
        last = fw.get("last_updated", fw.get("first_seen", ""))
        try:
            last_dt = datetime.fromisoformat(last)
            if (now - last_dt).days > _MAX_FOLLOWUP_AGE_DAYS:
                fw["status"] = "archived"
        except (ValueError, TypeError):
            pass
    state["followups"] = followups


def _archive_followups_for_topic(state: dict[str, Any], topic: str | None, now: datetime):
    if not topic or topic == "general_checkin":
        return
    followups = state.get("followups", [])
    changed = False
    for fw in followups:
        if fw.get("status") == "active" and fw.get("topic") == topic:
            fw["status"] = "resolved"
            fw["resolved_at"] = now.isoformat()
            changed = True
    if changed:
        state["followups"] = followups


def _growth_id(signal: dict[str, Any]) -> str:
    topic = signal.get("topic", "general_checkin")
    kind = signal.get("kind", "progress")
    label = signal.get("label", "")
    digest = hashlib.md5(f"{topic}:{kind}:{label}".encode()).hexdigest()[:8]
    return f"gr_{digest}"


def _append_growth_signal(state: dict[str, Any], signal: dict[str, Any], now: datetime) -> bool:
    if not isinstance(signal, dict):
        return False
    kind = signal.get("kind")
    if kind not in {"attempt", "result"}:
        return False

    timeline = state.get("growth_timeline", [])
    item_id = _growth_id(signal)
    if any(item.get("id") == item_id for item in timeline):
        return False

    timeline.append({
        "id": item_id,
        "kind": kind,
        "topic": signal.get("topic", "general_checkin"),
        "label": signal.get("label", ""),
        "evidence": signal.get("evidence", "")[:120],
        "created_at": now.isoformat(),
    })
    state["growth_timeline"] = timeline[-50:]
    return True


def _resolve_active_followups_for_topic(state: dict[str, Any], topic: str | None, now: datetime) -> None:
    if not topic:
        return
    for fw in state.get("followups", []):
        if fw.get("status") == "active" and fw.get("topic") == topic:
            fw["status"] = "resolved"
            fw["resolved_at"] = now.isoformat()


def _pet_mood_for_turn(user_mood: str, growth_signal: dict[str, Any] | None) -> str:
    if isinstance(growth_signal, dict) and growth_signal.get("kind") == "result":
        return "excited"
    if user_mood in {"anxious", "frustrated", "crisis"}:
        return "worried"
    if user_mood == "lonely":
        return "lonely_light"
    if user_mood == "curious":
        return "happy"
    return "calm"


def _presence_for_turn(user_mood: str, growth_signal: dict[str, Any] | None) -> str:
    if isinstance(growth_signal, dict) and growth_signal.get("kind") == "result":
        return "celebrating"
    if user_mood in {"anxious", "frustrated", "lonely", "crisis"}:
        return "caring"
    return "listening"


def _update_pet_state_after_turn(
    state: dict[str, Any],
    analysis: dict[str, Any],
    now: datetime,
    *,
    meaningful: bool,
) -> None:
    pet_state = normalize_pet_state(state.get("pet_state"), state)
    signal = analysis.get("growth_signal")
    user_mood = analysis.get("mood", "unknown")
    pet_state["last_seen_at"] = now.isoformat()
    pet_state["mood"] = _pet_mood_for_turn(user_mood, signal if meaningful else None)
    pet_state["presence_mode"] = _presence_for_turn(user_mood, signal if meaningful else None)
    pet_state["energy"] = max(20, min(100, pet_state.get("energy", 70) - 1))

    if meaningful:
        delta = 0
        if isinstance(signal, dict) and signal.get("kind") == "result":
            delta = 5
        elif isinstance(signal, dict) and signal.get("kind") == "attempt":
            delta = 3
        elif analysis.get("followup_upsert") or analysis.get("memory_worthy"):
            delta = 1
        pet_state["bond"] = max(0, min(100, pet_state.get("bond", 0) + delta))

    state["pet_state"] = normalize_pet_state(pet_state, state)


def followups_prompt(state: dict[str, Any]) -> str:
    """将活跃 followups 转换为关心的 prompt 片段。"""
    _archive_stale_followups(state)
    followups = state.get("followups", [])
    active = [f for f in followups if f.get("status") == "active" and not f.get("last_greeted_at")]
    has_greeted_active_followups = any(
        f.get("status") == "active" and f.get("last_greeted_at")
        for f in followups
    )
    if not active:
        return ""

    # 按 intensity 排序：high > medium > low
    intensity_order = {"high": 0, "medium": 1, "low": 2}
    active.sort(key=lambda f: intensity_order.get(f.get("intensity", "low"), 3))

    lines = ["\n【关心的线索（轻触即走，不要沉重）】"]
    for fw in active[:5]:  # 最多注入 5 条
        label = fw.get("label", "")
        context = fw.get("context", "")
        kind = fw.get("kind", "concern")
        intensity = fw.get("intensity", "medium")
        count = fw.get("mention_count", 1)

        if kind == "concern":
            if intensity == "high" and count >= 3:
                hint = f"用户多次提到{label}有困难，可以偶尔问一句进展"
            else:
                hint = f"用户提到过{label}的困难，相关话题时可以轻轻带一句"
        elif kind == "decision":
            hint = f"用户在选择{label}，聊到未来方向时可以问问想法有没有变化"
        elif kind == "event":
            hint = f"用户有{label}，时间过了可以问问结果"
        else:
            hint = f"可以偶尔关心一下{label}"

        if context:
            hint += f"（上下文：{context[:80]}）"
        lines.append(f"- {hint}")

    return "\n".join(lines)


def _sync_next_hook_from_followups(state: dict[str, Any]):
    """从 followups 中同步 next_hook（向后兼容）。

    只在当前 hook 未显式失活时更新。如果 analysis 已经设置了
    inactive 的 hook（例如用户拒绝了话题），则不覆盖。
    """
    existing = state.get("next_hook") or {}
    # 尊重 analysis 层的显式失活
    if isinstance(existing, dict) and existing.get("active") is False:
        return

    followups = state.get("followups", [])
    active = [f for f in followups if f.get("status") == "active" and not f.get("last_greeted_at")]
    has_greeted_active_followups = any(
        f.get("status") == "active" and f.get("last_greeted_at")
        for f in followups
    )
    if not active:
        # 如果没有活跃 followup，保持之前的 hook 或设为 neutral
        if not existing:
            state["next_hook"] = {"topic": "general_checkin", "label": "近况", "active": False}
        return

    # 取最高 intensity 的
    intensity_order = {"high": 3, "medium": 2, "low": 1}
    top = max(active, key=lambda f: intensity_order.get(f.get("intensity", "low"), 0))
    state["next_hook"] = {
        "topic": top.get("topic", "general_checkin"),
        "label": top.get("label", ""),
        "active": True,
    }


# ─── Turn Update ────────────────────────────────────────────────────────


def update_after_turn(
    state: dict[str, Any],
    analysis: dict[str, Any],
    now: datetime | None = None,
    route_mode: str | None = None,
) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    updated = normalize_state(state)

    stage_signal = analysis.get("stage_signal")
    if stage_signal in PRE_GROWTH_STAGE_MAP:
        updated["user_stage"] = stage_signal

    updated["recent_mood"] = analysis.get("mood") or updated["recent_mood"]
    updated["recent_topic"] = analysis.get("topic") or updated["recent_topic"]
    updated["last_active_at"] = now.isoformat()

    if route_mode == "hard_template":
        _update_pet_state_after_turn(updated, analysis, now, meaningful=False)
        return normalize_state(updated)

    if analysis.get("memory_worthy") and analysis.get("memory_content"):
        if analysis.get("memory_type") == "concern":
            updated["core_concern"] = analysis["memory_content"]
        else:
            updated["growth_intent"] = analysis["memory_content"]

    # ── Hook from analysis ──
    hook = analysis.get("next_hook")
    if hook:
        merged_hook = copy.deepcopy(hook)
        if merged_hook.get("active"):
            merged_hook["last_mentioned"] = now.isoformat()
        elif "last_mentioned" not in merged_hook and updated.get("next_hook"):
            merged_hook["last_mentioned"] = updated["next_hook"].get("last_mentioned")
        updated["next_hook"] = merged_hook
        if merged_hook.get("active") is False:
            _archive_followups_for_topic(updated, merged_hook.get("topic"), now)

    # ── Followups: upsert ──
    followup_upsert = analysis.get("followup_upsert")
    if followup_upsert:
        upsert_followup(
            updated,
            kind=followup_upsert.get("kind", "concern"),
            label=followup_upsert.get("label", ""),
            context=followup_upsert.get("context", ""),
            intensity=followup_upsert.get("intensity", "medium"),
            topic=analysis.get("topic", "general_checkin"),
        )

    # ── Followups: resolve ──
    followup_resolve = analysis.get("followup_resolve")
    if followup_resolve:
        resolve_followup(updated, followup_resolve)

    growth_signal = analysis.get("growth_signal")
    added_growth = _append_growth_signal(updated, growth_signal, now)
    if added_growth and growth_signal.get("kind") == "result":
        _resolve_active_followups_for_topic(updated, growth_signal.get("topic"), now)

    _update_pet_state_after_turn(
        updated,
        analysis,
        now,
        meaningful=bool(added_growth or followup_upsert or analysis.get("memory_worthy")),
    )

    # ── Sync next_hook ──
    _sync_next_hook_from_followups(updated)

    return normalize_state(updated)


# ─── Prompt ─────────────────────────────────────────────────────────────


def prompt_summary(state: dict[str, Any], analysis: dict[str, Any] | None = None) -> str:
    state = normalize_state(state)
    stage = growth_profile_for_stage(state.get("user_stage", "prospective"))
    mood = state.get("recent_mood", "unknown")
    topic = state.get("recent_topic", "general_checkin")
    hook = state.get("next_hook") or {}
    pet_state = state.get("pet_state", {})
    timeline = state.get("growth_timeline", [])
    lines = [
        "【关系状态】",
        f"- 用户阶段：{stage}",
        f"- 最近情绪：{mood}",
        f"- 最近主题：{topic}",
        '- 接续旧线索时只轻轻提一句，不要说"我一直记得你""我一直在想你""我等你很久了"。',
        "- 不要把短期情绪说成用户的长期性格标签。",
    ]
    if hook.get("active"):
        lines.append(f'- 可轻接的话题：{hook.get("label", "")}。只说"你之前提过/聊到过"，不要表现得一直惦记。')
    if analysis and analysis.get("reply_strategy"):
        lines.append(f"- 本轮策略：{analysis['reply_strategy']}")

    lines.extend([
        "",
        "【伙伴状态】",
        f"- 小芯状态：mood={pet_state.get('mood')}, energy={pet_state.get('energy')}, bond={pet_state.get('bond')}, stage={pet_state.get('relationship_stage')}, presence={pet_state.get('presence_mode')}",
        "- 这些状态只用于调整语气和动作，不要像报数值一样说给用户听。",
        "【可轻触线索】",
    ])
    if hook.get("active"):
        lines.append(f"- 当前可轻触：{hook.get('label', '')}。只在自然相关时提一句。")
    if timeline:
        last = timeline[-1]
        lines.append(f"- 最近成长：{last.get('label', '')}。可以用见证式语气轻轻承接。")
    if analysis and analysis.get("growth_signal"):
        signal = analysis["growth_signal"]
        lines.append(f"- 本轮成长信号：{signal.get('kind')} / {signal.get('label')}。")
    lines.extend([
        "- 没有自然入口时，不要硬提旧线索。",
        "【结构化输出约束】",
        "- reply 可以带一个表情标记，如 [smile] 或 [proud]。",
        "- speech 必须是干净可朗读文本，不要包含 JSON、状态值、表情标签或 action 字段。",
        "- action 是给开发板屏幕/动作系统的结构化字段，不要把动作旁白写进用户会听到的话里。",
    ])

    # 关心线索
    fw_prompt = followups_prompt(state)
    if fw_prompt:
        lines.append(fw_prompt)

    return "\n".join(lines)


# ─── Greeting ───────────────────────────────────────────────────────────


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

    # 优先用 followups 中的高 intensity 项生成问候
    followups = state.get("followups", [])
    active = [f for f in followups if f.get("status") == "active" and not f.get("last_greeted_at")]
    has_greeted_active_followups = any(
        f.get("status") == "active" and f.get("last_greeted_at")
        for f in followups
    )
    intensity_order = {"high": 3, "medium": 2, "low": 1}
    active.sort(key=lambda f: intensity_order.get(f.get("intensity", "low"), 0), reverse=True)

    if active:
        top = active[0]
        topic = top.get("topic", "general_checkin")
        label = top.get("label", "")
        kind = top.get("kind", "concern")

        # 尝试用 topic 映射找到预设问候
        if topic in CONTEXTUAL_GREETINGS:
            greeting = CONTEXTUAL_GREETINGS[topic]
        elif kind == "concern":
            greeting = f"之前你提过{label}，最近有新的进展吗？"
        elif kind == "decision":
            greeting = f"上次聊到{label}，最近想法有变化吗？"
        elif kind == "event":
            greeting = f"上次你说的{label}，后来怎么样了？"
        else:
            greeting = f"上次聊到{label}，今天想接着聊吗？还是换个话题？"

        top["last_greeted_at"] = today
        state["followups"] = followups
        save_state(data_dir, user_id, state)
        return {
            "greeting": greeting,
            "speech": greeting,
            "expression": "soft_smile",
            "kind": "contextual",
            "companion_action": {"kind": "idle_wave", "intensity": 0.3},
        }

    if has_greeted_active_followups:
        save_state(data_dir, user_id, state)
        return _generic_payload()

    # fallback: 用旧的 hook 逻辑
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
