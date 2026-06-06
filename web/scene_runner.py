"""Scene runner for relationship self-play v2.

Orchestrates: load scene -> for each episode -> user LLM generates message
-> post to Xiaoxin API -> read state -> rule checks -> quality judge -> report.
"""

from __future__ import annotations

import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Generator

import relationship_state
import rule_evaluator
import user_simulator


DEFAULT_BASE_DATE = datetime(2026, 6, 5)
RUN_MODES = {"regression", "mixed", "pressure"}
DEFAULT_MODE = "regression"
MAX_TURNS_PER_DAY = 30


SCENE_DIR = Path(__file__).resolve().parent / "scenes"


def load_scene(path: Path) -> dict[str, Any]:
    """Load a single scene JSON file."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_all_scenes() -> list[dict[str, Any]]:
    """Load all scene JSON files from the scenes directory."""
    scenes = []
    for path in sorted(SCENE_DIR.glob("*.json")):
        scenes.append(load_scene(path))
    return scenes


def resolve_episode_days(episodes: list[dict[str, Any]], seed: int) -> list[dict[str, Any]]:
    """Resolve day=[min, max] ranges into deterministic integers.

    - day as int → kept as-is
    - day as [min, max] → resolved with seed to a random integer in range
    - Ensures non-decreasing order (later episodes >= previous day)
    - Returns a deep copy; original data is not mutated.
    """
    import copy as _copy
    resolved = _copy.deepcopy(episodes)
    prev_day = -1

    for i, ep in enumerate(resolved):
        raw = ep.get("day")
        if isinstance(raw, list) and len(raw) == 2:
            lo, hi = int(raw[0]), int(raw[1])
            if i == 0:
                # Anchor: first episode always uses the min value
                day = lo
            else:
                lo = max(lo, prev_day)
                hi = max(hi, lo)
                if lo == hi:
                    day = lo
                else:
                    rng = random.Random(seed + i)
                    day = rng.randint(lo, hi)
            ep["day"] = day
        elif isinstance(raw, (int, float)):
            ep["day"] = int(raw)

        # Enforce non-decreasing order
        if ep["day"] < prev_day:
            ep["day"] = prev_day
        prev_day = ep["day"]

    return resolved


def summarize_conversation(records: list[dict[str, Any]]) -> str:
    """Build a short summary of the conversation so far for the user LLM."""
    if not records:
        return ""
    lines = []
    for r in records[-6:]:  # Last 6 turns max
        if r["action"] == "idle_gap":
            lines.append(f"{r.get('label', 'Idle gap')}: no user interaction")
        elif r["action"] == "greeting":
            lines.append(f"小芯(问候): {r['xiaoxin_reply']}")
        else:
            lines.append(f"新生: {r.get('user_message', '')}")
            lines.append(f"小芯: {r['xiaoxin_reply']}")
    return "\n".join(lines)


def compute_overall_result(
    rule_violations: list[dict[str, str]],
    quality_scores: dict[str, int | None],
) -> dict[str, Any]:
    """Compute final verdict from rule and quality results."""
    has_rule_failure = len(rule_violations) > 0

    valid_scores = [s for s in quality_scores.values() if s is not None]
    avg_score = sum(valid_scores) / len(valid_scores) if valid_scores else 0

    if has_rule_failure:
        verdict = "FAIL"
    elif avg_score >= 3.5:
        verdict = "PASS"
    elif avg_score >= 2.5:
        verdict = "WARN"
    else:
        verdict = "FAIL"

    return {
        "verdict": verdict,
        "rule_violations_count": len(rule_violations),
        "quality_avg_score": round(avg_score, 2),
        "rule_violations": rule_violations,
        "quality_scores": quality_scores,
    }


def _generate_notes(
    overall: dict[str, Any],
    records: list[dict[str, Any]],
) -> str:
    """Generate human-readable notes for the report."""
    parts = []

    # Stage migrations
    stage_events = []
    prev_stage = None
    for r in records:
        if r.get("action") == "idle_gap":
            continue
        stage = (r.get("state") or {}).get("user_stage")
        if prev_stage is not None and stage != prev_stage:
            stage_events.append(f"Day {r['day']}: {prev_stage} → {stage}")
        prev_stage = stage

    # Hook changes
    hook_events = []
    prev_hook = None
    for r in records:
        if r.get("action") == "idle_gap":
            continue
        hook = r.get("next_hook") or {}
        if prev_hook is not None:
            if hook.get("active") and not prev_hook.get("active"):
                hook_events.append(f"Day {r['day']}: hook 激活 ({hook.get('topic')})")
            elif not hook.get("active") and prev_hook.get("active"):
                hook_events.append(f"Day {r['day']}: hook 关闭 ({hook.get('topic')})")
        prev_hook = hook

    if stage_events:
        parts.append("阶段迁移: " + "; ".join(stage_events))
    if hook_events:
        parts.append("Hook 变化: " + "; ".join(hook_events))
    if overall["rule_violations_count"] == 0:
        parts.append("规则评估: 无违规")
    else:
        parts.append(f"规则评估: {overall['rule_violations_count']} 项违规")

    verdict = overall["verdict"]
    if verdict == "PASS":
        parts.append("综合判定: 通过")
    elif verdict == "WARN":
        parts.append("综合判定: 可用但需优化")
    else:
        parts.append("综合判定: 未通过")

    return "\n".join(parts)


def build_review_context(
    episode: dict[str, Any],
    user_message: str | None,
    xiaoxin_reply: str,
    intent: str | None = None,
    turn_index: int = 1,
    turn_count: int = 1,
) -> dict[str, Any]:
    """Keep the source intent beside each generated turn for human review."""
    return {
        "action": episode.get("action", ""),
        "intent": intent if intent is not None else episode.get("intent", ""),
        "turn_index": turn_index,
        "turn_count": turn_count,
        "probes": episode.get("probes", {}),
        "forbid_patterns": episode.get("forbid_patterns", []),
        "audit_targets": {
            "user_message": user_message or "",
            "xiaoxin_reply": xiaoxin_reply,
        },
    }


def episode_chat_intents(episode: dict[str, Any]) -> list[str]:
    """Return the scripted intents for all same-day turns in a chat episode."""
    intents = [str(episode.get("intent", ""))]
    intents.extend(str(item) for item in episode.get("followup_intents", []))
    return [intent for intent in intents if intent.strip()]


def validate_run_mode(mode: str) -> str:
    if mode not in RUN_MODES:
        raise ValueError("mode must be one of: regression, mixed, pressure")
    return mode


def pressure_goal_for_episode(scene: dict[str, Any] | None, episode: dict[str, Any]) -> str:
    if episode.get("pressure_goal"):
        return str(episode["pressure_goal"])
    if episode.get("intent"):
        return str(episode["intent"])
    character = (scene or {}).get("character", {})
    return str(character.get("traits", "Continue a natural student conversation with Xiaoxin."))


def turn_budget_for_episode(
    episode: dict[str, Any],
    turns_per_day: int | None,
    scripted_count: int,
) -> int:
    raw = episode.get("pressure_turns", turns_per_day)
    if raw in (None, "", "default"):
        return max(1, scripted_count)
    budget = int(raw)
    return max(1, min(MAX_TURNS_PER_DAY, budget))


def plan_chat_turns(
    episode: dict[str, Any],
    mode: str = DEFAULT_MODE,
    turns_per_day: int | None = None,
    scene: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    mode = validate_run_mode(mode)
    scripted = episode_chat_intents(episode)
    goal = pressure_goal_for_episode(scene, episode)

    if mode == "regression":
        return [{"source": "scripted", "intent": intent} for intent in scripted]

    budget = turn_budget_for_episode(episode, turns_per_day, len(scripted))
    if mode == "pressure":
        return [{"source": "pressure", "intent": goal} for _ in range(budget)]

    turns = [{"source": "scripted", "intent": intent} for intent in scripted[:budget]]
    while len(turns) < budget:
        turns.append({"source": "pressure", "intent": goal})
    return turns


def summarize_day(records: list[dict[str, Any]], day: int) -> str:
    day_records = [
        r for r in records
        if r.get("day") == day and r.get("action") != "idle_gap"
    ]
    if not day_records:
        return f"Day {day}: no interaction"

    last = day_records[-1]
    state = last.get("state") or {}
    hook = last.get("next_hook") or {}
    violations = sum(len(r.get("violations") or []) for r in day_records)
    user_messages = [r.get("user_message") for r in day_records if r.get("user_message")]
    last_user = user_messages[-1] if user_messages else "no user message"
    violation_label = "1 violation" if violations == 1 else f"{violations} violations"
    return (
        f"Day {day}: {len(day_records)} interaction(s); "
        f"stage={state.get('user_stage', '?')}; "
        f"topic={state.get('recent_topic', '?')}; "
        f"hook={hook.get('topic', 'none')} active={bool(hook.get('active'))}; "
        f"{violation_label}; last_user={last_user}"
    )


def build_idle_gap_record(
    scene: dict[str, Any],
    previous_day: int | None,
    next_day: int,
) -> dict[str, Any] | None:
    """Create a visible timeline record for days with no user interaction."""
    if previous_day is None or next_day - previous_day <= 1:
        return None

    from_day = previous_day + 1
    to_day = next_day - 1
    label = f"Day {from_day}" if from_day == to_day else f"Day {from_day}-{to_day}"
    gap_days = to_day - from_day + 1
    return {
        "scene_id": scene["scene_id"],
        "scene_name": scene.get("name", scene["scene_id"]),
        "day": from_day,
        "action": "idle_gap",
        "from_day": from_day,
        "to_day": to_day,
        "gap_days": gap_days,
        "label": label,
        "message": f"{label}: user had no recorded interaction for {gap_days} day(s).",
        "turn_index": 0,
        "turn_count": 0,
        "turn_source": "idle_gap",
        "day_summary": "",
        "user_message": None,
        "xiaoxin_reply": "",
        "violations": [],
    }


def run_episode_chat(
    client,
    scene: dict[str, Any],
    episode: dict[str, Any],
    user_id: str,
    records: list[dict[str, Any]],
    seed: int,
    data_dir: Path,
    intent: str | None = None,
    turn_index: int = 1,
    turn_count: int = 1,
) -> dict[str, Any]:
    """Run a chat-type episode: user LLM -> /api/chat -> record."""
    character = scene["character"]
    intent = intent if intent is not None else episode["intent"]
    forbid = episode.get("forbid_patterns", [])
    probes = episode.get("probes", {})

    # Generate user message via LLM
    conv_summary = summarize_conversation(records)
    user_msg = user_simulator.generate_user_message(
        character=character,
        intent=intent,
        conversation_summary=conv_summary,
        forbid_patterns=forbid,
        seed=seed,
    )

    # Post to Xiaoxin
    response = client.post("/api/chat", json={
        "user_id": user_id,
        "message": user_msg,
    })
    payload = response.get_json() or {}
    if response.status_code != 200:
        payload = {
            "reply": f"API错误: HTTP {response.status_code}",
            "expression": "sad",
        }

    # Read updated state
    state = relationship_state.load_state(data_dir, user_id)
    next_hook = state.get("next_hook") or {}
    reply_text = str(payload.get("reply") or payload.get("greeting") or "")

    # Rule evaluation
    violations = rule_evaluator.evaluate_episode(
        probes=probes,
        state=state,
        next_hook=next_hook,
        reply_text=reply_text,
        payload_kind=payload.get("kind"),
        user_msg=user_msg,
    )

    return {
        "day": episode["day"],
        "action": "chat",
        "turn_index": turn_index,
        "turn_count": turn_count,
        "user_message": user_msg,
        "xiaoxin_reply": reply_text,
        "speech": payload.get("speech", ""),
        "expression": payload.get("expression", ""),
        "companion_action": payload.get("companion_action"),
        "state": relationship_state.public_state(state),
        "next_hook": next_hook,
        "violations": violations,
        "review_context": build_review_context(
            episode, user_msg, reply_text, intent, turn_index, turn_count
        ),
    }


def run_episode_greeting(
    client,
    episode: dict[str, Any],
    user_id: str,
    data_dir: Path,
    base_date: datetime | None = None,
) -> dict[str, Any]:
    """Run a greeting-type episode: GET /api/greeting -> record."""
    probes = episode.get("probes", {})

    # Compute today from day offset
    day_offset = episode["day"]
    base = base_date or DEFAULT_BASE_DATE
    target = base + timedelta(days=day_offset)
    today = target.date().isoformat()

    response = client.get(f"/api/greeting?user_id={user_id}&today={today}")
    payload = response.get_json() or {}

    state = relationship_state.load_state(data_dir, user_id)
    next_hook = state.get("next_hook") or {}
    reply_text = str(payload.get("greeting") or "")

    violations = rule_evaluator.evaluate_episode(
        probes=probes,
        state=state,
        next_hook=next_hook,
        reply_text=reply_text,
        payload_kind=payload.get("kind"),
    )

    return {
        "day": episode["day"],
        "action": "greeting",
        "turn_index": 1,
        "turn_count": 1,
        "user_message": None,
        "xiaoxin_reply": reply_text,
        "speech": payload.get("speech", ""),
        "expression": payload.get("expression", ""),
        "companion_action": payload.get("companion_action"),
        "state": relationship_state.public_state(state),
        "next_hook": next_hook,
        "violations": violations,
        "review_context": build_review_context(episode, None, reply_text),
    }


def run_scene_streaming(
    scene_id: str = "all",
    seed: int | None = None,
    skip_quality_judge: bool = False,
    max_days: int | None = None,
    mode: str = DEFAULT_MODE,
    turns_per_day: int | None = None,
    chat_fn: Callable[[str, str, str], dict[str, Any]] | None = None,
    greeting_fn: Callable[[str, str, str], dict[str, Any]] | None = None,
    base_date: datetime | None = None,
) -> Generator[dict[str, Any], None, None]:
    """逐 episode 产出 SSE 事件。供 web API 使用。

    chat_fn(user_id, message, data_dir) -> reply_dict
    greeting_fn(user_id, today, data_dir) -> greeting_dict

    产出事件格式: {"event": "episode"|"quality_judge"|"complete"|"error", "data": ...}
    """
    import os
    import tempfile

    import quality_judge

    if seed is None:
        seed = random.randint(0, 2**31 - 1)
    mode = validate_run_mode(mode)
    if turns_per_day is not None:
        turns_per_day = max(1, min(MAX_TURNS_PER_DAY, int(turns_per_day)))

    # 加载场景
    scenes = load_all_scenes()
    if scene_id != "all":
        scenes = [s for s in scenes if s["scene_id"] == scene_id]
        if not scenes:
            raise ValueError(f"未知场景: {scene_id}")

    # 默认回调：用 Flask test client
    if chat_fn is None or greeting_fn is None:
        import app as app_module

        if chat_fn is None:
            def chat_fn(uid, msg, dd):
                old = app_module.DATA_DIR
                app_module.DATA_DIR = Path(dd)
                app_module.active_conversations.clear()
                try:
                    return app_module.chat_core(uid, msg, dd)
                finally:
                    app_module.DATA_DIR = old

        if greeting_fn is None:
            def greeting_fn(uid, today, dd):
                old = app_module.DATA_DIR
                app_module.DATA_DIR = Path(dd)
                try:
                    return relationship_state.greeting_payload(Path(dd), uid, today=today)
                finally:
                    app_module.DATA_DIR = old

    data_dir = Path(tempfile.mkdtemp(prefix="xiaoxin_rel_v2_"))

    for scene in scenes:
        scene_name = scene["scene_id"]
        user_id = f"rel_v2_{scene_name}"

        # 清理旧状态
        for prefix in ("relationship", "sessions", "memory", "growth"):
            path = data_dir / f"{prefix}_{user_id}.json"
            if path.exists():
                path.unlink()

        base = base_date or DEFAULT_BASE_DATE
        records = []
        all_violations = []
        episode_seed = seed
        previous_interaction_day = None

        resolved_episodes = resolve_episode_days(scene["episodes"], seed)

        for i, episode in enumerate(resolved_episodes):
            if max_days is not None and episode["day"] > max_days:
                continue

            gap_record = build_idle_gap_record(
                scene, previous_interaction_day, episode["day"]
            )
            if gap_record:
                records.append(gap_record)
                yield {"event": "episode", "data": gap_record}

            ep_seed = episode_seed + i
            probes = episode.get("probes", {})

            if episode["action"] == "greeting":
                target = base + timedelta(days=episode["day"])
                today = target.date().isoformat()
                payload = greeting_fn(user_id, today, str(data_dir))

                state = relationship_state.load_state(data_dir, user_id)
                next_hook = state.get("next_hook") or {}
                reply_text = str(payload.get("greeting") or payload.get("reply") or "")

                violations = rule_evaluator.evaluate_episode(
                    probes=probes, state=state, next_hook=next_hook,
                    reply_text=reply_text, payload_kind=payload.get("kind"),
                )

                record = {
                    "scene_id": scene_name,
                    "scene_name": scene.get("name", scene_name),
                    "day": episode["day"], "action": "greeting",
                    "turn_index": 1, "turn_count": 1,
                    "turn_source": "greeting",
                    "user_message": None, "xiaoxin_reply": reply_text,
                    "speech": payload.get("speech", ""),
                    "expression": payload.get("expression", ""),
                    "companion_action": payload.get("companion_action"),
                    "state": relationship_state.public_state(state),
                    "next_hook": next_hook, "violations": violations,
                    "review_context": build_review_context(episode, None, reply_text),
                }
                record["day_summary"] = summarize_day([*records, record], episode["day"])
            else:
                # Chat episode: 用户 LLM 生成消息 → 小芯回复
                character = scene["character"]
                forbid = episode.get("forbid_patterns", [])
                planned_turns = plan_chat_turns(
                    episode,
                    mode=mode,
                    turns_per_day=turns_per_day,
                    scene=scene,
                )
                turn_count = len(planned_turns)
                same_day_records: list[dict[str, Any]] = []
                prior_days = sorted({
                    r.get("day")
                    for r in records
                    if isinstance(r.get("day"), int) and r.get("day") < episode["day"]
                })[-3:]
                prior_day_summary = "\n".join(
                    summarize_day(records, day) for day in prior_days
                )

                for turn_offset, planned in enumerate(planned_turns):
                    turn_index = turn_offset + 1
                    intent = planned["intent"]
                    turn_source = planned["source"]
                    if turn_source == "pressure":
                        current_state = relationship_state.public_state(
                            relationship_state.load_state(data_dir, user_id)
                        )
                        user_msg = user_simulator.generate_pressure_user_message(
                            character=character,
                            pressure_goal=intent,
                            same_day_transcript=summarize_conversation(same_day_records),
                            prior_day_summary=prior_day_summary,
                            relationship_state=current_state,
                            forbid_patterns=forbid,
                            seed=ep_seed + turn_offset,
                            turn_index=turn_index,
                            turn_count=turn_count,
                        )
                    else:
                        conv_summary = summarize_conversation(records)
                        user_msg = user_simulator.generate_user_message(
                            character=character, intent=intent,
                            conversation_summary=conv_summary,
                            forbid_patterns=forbid, seed=ep_seed + turn_offset,
                        )

                    payload = chat_fn(user_id, user_msg, str(data_dir))
                    state = relationship_state.load_state(data_dir, user_id)
                    next_hook = state.get("next_hook") or {}
                    reply_text = str(payload.get("reply") or payload.get("greeting") or "")

                    violations = rule_evaluator.evaluate_episode(
                        probes=probes, state=state, next_hook=next_hook,
                        reply_text=reply_text, payload_kind=payload.get("kind"),
                        user_msg=user_msg,
                    )

                    record = {
                        "scene_id": scene_name,
                        "scene_name": scene.get("name", scene_name),
                        "day": episode["day"], "action": "chat",
                        "turn_index": turn_index, "turn_count": turn_count,
                        "turn_source": turn_source,
                        "user_message": user_msg, "xiaoxin_reply": reply_text,
                        "speech": payload.get("speech", ""),
                        "expression": payload.get("expression", ""),
                        "companion_action": payload.get("companion_action"),
                        "state": relationship_state.public_state(state),
                        "next_hook": next_hook, "violations": violations,
                        "review_context": build_review_context(
                            episode, user_msg, reply_text, intent, turn_index, turn_count
                        ),
                    }
                    record["day_summary"] = summarize_day(
                        [*records, *same_day_records, record], episode["day"]
                    )

                    same_day_records.append(record)
                    records.append(record)
                    all_violations.extend(violations)
                    yield {"event": "episode", "data": record}

            if episode["action"] == "greeting":
                records.append(record)
                all_violations.extend(violations)
                yield {"event": "episode", "data": record}

        # 质量裁判
            previous_interaction_day = episode["day"]

        quality_result = None
        if not skip_quality_judge and records:
            quality_result = quality_judge.evaluate(
                scene_name=scene.get("name", scene_name), records=records)
            yield {"event": "quality_judge", "data": quality_result}

        quality_scores = quality_result["scores"] if quality_result else {}
        overall = compute_overall_result(all_violations, quality_scores)

        yield {
            "event": "complete",
            "data": {
                "scene_id": scene_name,
                "name": scene.get("name", scene_name),
                "description": scene.get("description", ""),
                "seed": seed,
                "verdict": overall["verdict"],
                "rule_violations_count": overall["rule_violations_count"],
                "quality_avg_score": overall["quality_avg_score"],
                "notes": _generate_notes(overall, records),
                "records": records,
                "quality_judge": quality_result,
            },
        }


def run_scene(
    scene: dict[str, Any],
    data_dir: Path,
    seed: int | None = None,
    skip_quality_judge: bool = False,
    max_days: int | None = None,
    base_date: datetime | None = None,
) -> dict[str, Any]:
    """Run all episodes of one scene and return the full report."""
    import quality_judge

    if seed is None:
        seed = random.randint(0, 2**31 - 1)

    scene_id = scene["scene_id"]
    user_id = f"rel_v2_{scene_id}"

    # Clean up old state files for this user
    for prefix in ("relationship", "sessions", "memory", "growth"):
        path = Path(data_dir) / f"{prefix}_{user_id}.json"
        if path.exists():
            path.unlink()

    # Use Flask test client (real API, not scripted)
    import app as app_module
    old_data_dir = app_module.DATA_DIR
    app_module.DATA_DIR = Path(data_dir)
    app_module.active_conversations.clear()

    try:
        client = app_module.app.test_client()
        records = []
        all_violations = []
        episode_seed = seed
        previous_interaction_day = None

        resolved_episodes = resolve_episode_days(scene["episodes"], seed)

        for i, episode in enumerate(resolved_episodes):
            # Filter by max_days
            if max_days is not None and episode["day"] > max_days:
                continue

            gap_record = build_idle_gap_record(
                scene, previous_interaction_day, episode["day"]
            )
            if gap_record:
                records.append(gap_record)

            ep_seed = episode_seed + i

            if episode["action"] == "greeting":
                record = run_episode_greeting(
                    client, episode, user_id, data_dir, base_date=base_date,
                )
                records.append(record)
                all_violations.extend(record["violations"])
            else:
                intents = episode_chat_intents(episode)
                turn_count = len(intents)
                for turn_offset, intent in enumerate(intents):
                    record = run_episode_chat(
                        client,
                        scene,
                        episode,
                        user_id,
                        records,
                        ep_seed + turn_offset,
                        data_dir,
                        intent=intent,
                        turn_index=turn_offset + 1,
                        turn_count=turn_count,
                    )
                    records.append(record)
                    all_violations.extend(record["violations"])

            previous_interaction_day = episode["day"]

        # Quality judge evaluation
        quality_result = None
        if not skip_quality_judge and records:
            quality_result = quality_judge.evaluate(
                scene_name=scene.get("name", scene_id),
                records=records,
            )

        quality_scores = quality_result["scores"] if quality_result else {}
        overall = compute_overall_result(all_violations, quality_scores)

        return {
            "scene_id": scene_id,
            "name": scene.get("name", scene_id),
            "description": scene.get("description", ""),
            "seed": seed,
            "records": records,
            "quality_judge": quality_result,
            **overall,
            "notes": _generate_notes(overall, records),
        }
    finally:
        app_module.DATA_DIR = old_data_dir
        app_module.active_conversations.clear()


def run_suite(
    scene_id: str = "all",
    data_dir: Path | None = None,
    seed: int | None = None,
    skip_quality_judge: bool = False,
    max_days: int | None = None,
) -> dict[str, Any]:
    """Run all (or a specific) scenes and return the suite report."""
    import tempfile

    scenes = load_all_scenes()
    if scene_id != "all":
        scenes = [s for s in scenes if s["scene_id"] == scene_id]
        if not scenes:
            raise ValueError(f"未知场景: {scene_id}")

    if data_dir is None:
        tmp = tempfile.mkdtemp(prefix="xiaoxin_rel_v2_")
        data_dir = Path(tmp)

    results = []
    for scene in scenes:
        result = run_scene(
            scene,
            data_dir=data_dir,
            seed=seed,
            skip_quality_judge=skip_quality_judge,
            max_days=max_days,
        )
        results.append(result)

    passed = sum(1 for r in results if r["verdict"] == "PASS")
    warned = sum(1 for r in results if r["verdict"] == "WARN")
    failed = sum(1 for r in results if r["verdict"] == "FAIL")

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "total": len(results),
        "passed": passed,
        "warned": warned,
        "failed": failed,
        "seed": seed,
        "results": results,
    }
