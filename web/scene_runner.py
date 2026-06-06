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


def summarize_conversation(records: list[dict[str, Any]]) -> str:
    """Build a short summary of the conversation so far for the user LLM."""
    if not records:
        return ""
    lines = []
    for r in records[-6:]:  # Last 6 turns max
        if r["action"] == "greeting":
            lines.append(f"小信(问候): {r['xiaoxin_reply']}")
        else:
            lines.append(f"新生: {r.get('user_message', '')}")
            lines.append(f"小信: {r['xiaoxin_reply']}")
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
        stage = (r.get("state") or {}).get("user_stage")
        if prev_stage is not None and stage != prev_stage:
            stage_events.append(f"Day {r['day']}: {prev_stage} → {stage}")
        prev_stage = stage

    # Hook changes
    hook_events = []
    prev_hook = None
    for r in records:
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


def run_episode_chat(
    client,
    scene: dict[str, Any],
    episode: dict[str, Any],
    user_id: str,
    records: list[dict[str, Any]],
    seed: int,
    data_dir: Path,
) -> dict[str, Any]:
    """Run a chat-type episode: user LLM -> /api/chat -> record."""
    character = scene["character"]
    intent = episode["intent"]
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
        "user_message": user_msg,
        "xiaoxin_reply": reply_text,
        "speech": payload.get("speech", ""),
        "expression": payload.get("expression", ""),
        "companion_action": payload.get("companion_action"),
        "state": relationship_state.public_state(state),
        "next_hook": next_hook,
        "violations": violations,
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
        "user_message": None,
        "xiaoxin_reply": reply_text,
        "speech": payload.get("speech", ""),
        "expression": payload.get("expression", ""),
        "companion_action": payload.get("companion_action"),
        "state": relationship_state.public_state(state),
        "next_hook": next_hook,
        "violations": violations,
    }


def run_scene_streaming(
    scene_id: str = "all",
    seed: int | None = None,
    skip_quality_judge: bool = False,
    max_days: int | None = None,
    mode: str = "regression",
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

        for i, episode in enumerate(scene["episodes"]):
            if max_days is not None and episode["day"] > max_days:
                continue

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
                    "user_message": None, "xiaoxin_reply": reply_text,
                    "speech": payload.get("speech", ""),
                    "expression": payload.get("expression", ""),
                    "companion_action": payload.get("companion_action"),
                    "state": relationship_state.public_state(state),
                    "next_hook": next_hook, "violations": violations,
                }
            else:
                # Chat episode: 用户 LLM 生成消息 → 小信回复
                character = scene["character"]
                intent = episode["intent"]
                forbid = episode.get("forbid_patterns", [])
                conv_summary = summarize_conversation(records)
                user_msg = user_simulator.generate_user_message(
                    character=character, intent=intent,
                    conversation_summary=conv_summary,
                    forbid_patterns=forbid, seed=ep_seed,
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
                    "user_message": user_msg, "xiaoxin_reply": reply_text,
                    "speech": payload.get("speech", ""),
                    "expression": payload.get("expression", ""),
                    "companion_action": payload.get("companion_action"),
                    "state": relationship_state.public_state(state),
                    "next_hook": next_hook, "violations": violations,
                }

            records.append(record)
            all_violations.extend(violations)
            yield {"event": "episode", "data": record}

        # 质量裁判
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

        for i, episode in enumerate(scene["episodes"]):
            # Filter by max_days
            if max_days is not None and episode["day"] > max_days:
                continue

            ep_seed = episode_seed + i

            if episode["action"] == "greeting":
                record = run_episode_greeting(
                    client, episode, user_id, data_dir, base_date=base_date,
                )
            else:
                record = run_episode_chat(
                    client, scene, episode, user_id, records, ep_seed, data_dir,
                )

            records.append(record)
            all_violations.extend(record["violations"])

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
