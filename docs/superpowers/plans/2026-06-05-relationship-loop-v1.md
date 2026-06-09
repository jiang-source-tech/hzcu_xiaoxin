# Relationship Loop v1 Implementation Plan

> **Archived / do not execute:** This historical plan predates the current cost-control decision. Relationship self-play Web/API/CLI tests are disabled; use `/test` for daily Xiaoxin review and optimization.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a light, testable relationship loop so Xiaoxin can remember one important user concern, greet users once per day with restraint, and migrate from prospective-student chat into early-freshman support.

**Architecture:** Add deterministic relationship logic beside the existing memory and growth tools. `turn_analyzer.py` classifies each user turn into stage, mood, topic, and a structured `next_hook`; `relationship_state.py` persists and updates the state; `app.py` injects that state into prompts, returns it in API payloads, and exposes `/api/greeting`.

**Tech Stack:** Python 3, Flask, `unittest`, JSON files under `skills/xiaoxin-senior/data`, existing DeepSeek/OpenAI-compatible client.

---

## File Structure

- Create `web/turn_analyzer.py`
  - Pure deterministic classifier for stage signals, mood, topic, memory-worthy content, and structured `next_hook`.
  - No file IO, no Flask, no LLM calls.

- Create `web/relationship_state.py`
  - JSON persistence for `relationship_{user_id}.json`.
  - State update helpers, greeting payload generation, prompt summary generation, and public API state formatting.
  - No Flask imports and no LLM calls.

- Create `web/tests/test_relationship.py`
  - `unittest` coverage for turn analysis, state persistence, stage migration, greeting frequency, hook deactivation, prompt constraints, route payloads, and forbidden clingy wording.

- Modify `web/app.py`
  - Import `relationship_state` and `turn_analyzer`.
  - Extend `build_system_prompt()` to accept relationship context.
  - Extend `record_chat_reply()` payload with `state`, `next_hook`, and `companion_action`.
  - Update `/api/chat` to analyze turns and persist relationship state.
  - Add `GET /api/greeting`.
  - Extend expression parsing to accept `soft_smile`.

- Modify `web/static/index.html`
  - Add `soft_smile` display mapping.
  - Fetch `/api/greeting` once when the page loads and render Xiaoxin's opening line.

---

### Task 1: Deterministic Turn Analyzer

**Files:**
- Create: `web/turn_analyzer.py`
- Test: `web/tests/test_relationship.py`

- [ ] **Step 1: Write failing analyzer tests**

Add this initial content to `web/tests/test_relationship.py`:

```python
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import turn_analyzer


class TurnAnalyzerTest(unittest.TestCase):
    def test_prospective_anxiety_about_course_rhythm_gets_light_hook(self):
        result = turn_analyzer.analyze("信电会不会很难，我怕跟不上。")

        self.assertEqual(result["stage_signal"], "prospective")
        self.assertEqual(result["mood"], "anxious")
        self.assertEqual(result["topic"], "course_rhythm")
        self.assertTrue(result["memory_worthy"])
        self.assertEqual(result["memory_type"], "concern")
        self.assertEqual(result["memory_content"], "担心信电课程跟不上")
        self.assertEqual(result["next_hook"], {
            "topic": "course_rhythm",
            "label": "课程节奏",
            "active": True,
        })
        self.assertNotIn("下次", str(result["next_hook"]))

    def test_early_freshman_stage_signal_when_user_says_school_started(self):
        result = turn_analyzer.analyze("我已经开学了，第一周课好多，有点顶不住。")

        self.assertEqual(result["stage_signal"], "early_freshman")
        self.assertEqual(result["mood"], "anxious")
        self.assertEqual(result["topic"], "course_rhythm")

    def test_refusing_topic_deactivates_current_hook(self):
        current_state = {
            "next_hook": {
                "topic": "course_rhythm",
                "label": "课程节奏",
                "active": True,
            }
        }

        result = turn_analyzer.analyze("别聊课程了，烦。", current_state)

        self.assertEqual(result["mood"], "frustrated")
        self.assertEqual(result["topic"], "general_checkin")
        self.assertFalse(result["next_hook"]["active"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run analyzer tests and verify they fail**

Run:

```powershell
python -m unittest web.tests.test_relationship.TurnAnalyzerTest -v
```

Expected: FAIL or ERROR because `web/turn_analyzer.py` does not exist.

- [ ] **Step 3: Implement `web/turn_analyzer.py`**

Create `web/turn_analyzer.py`:

```python
"""Deterministic relationship-turn analysis for Xiaoxin.

This module keeps relationship continuity controllable. It returns structured
tags only; user-facing wording belongs in prompts, templates, or the LLM reply.
"""

from __future__ import annotations

import re
from typing import Any


TOPIC_LABELS = {
    "course_rhythm": "课程节奏",
    "major_choice": "专业理解",
    "competition_interest": "竞赛兴趣",
    "social_adaptation": "人际适应",
    "campus_life": "校园生活",
    "family_concern": "家长沟通",
    "general_checkin": "近况",
}


def _contains(text: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(pattern, text) for pattern in patterns)


def _stage_signal(text: str) -> str:
    if _contains(text, (r"已经开学", r"开学了", r"第一周", r"上课", r"课程表", r"入学后")):
        return "early_freshman"
    if _contains(text, (r"录取", r"通知书", r"报到", r"开学前", r"入学准备", r"新生群")):
        return "pre_enrollment"
    return "prospective"


def _mood(text: str) -> str:
    if _contains(text, (r"撑不住", r"活着没意思", r"不想活", r"自杀", r"伤害自己")):
        return "crisis"
    if _contains(text, (r"别聊", r"不想聊", r"烦", r"算了", r"别问")):
        return "frustrated"
    if _contains(text, (r"怕", r"担心", r"焦虑", r"慌", r"跟不上", r"顶不住", r"压力")):
        return "anxious"
    if _contains(text, (r"孤独", r"没人", r"社恐", r"融不进去", r"不敢说话")):
        return "lonely"
    if _contains(text, (r"开心", r"期待", r"想去", r"感兴趣", r"好奇")):
        return "curious"
    return "relaxed"


def _topic(text: str) -> str:
    if _contains(text, (r"跟不上", r"课程", r"课好多", r"高数", r"C语言", r"学习节奏", r"节奏")):
        return "course_rhythm"
    if _contains(text, (r"专业", r"电子信息", r"自动化", r"人工智能", r"通信", r"方向")):
        return "major_choice"
    if _contains(text, (r"竞赛", r"智能车", r"电赛", r"机器人", r"实验室")):
        return "competition_interest"
    if _contains(text, (r"朋友", r"室友", r"同学", r"社恐", r"融入", r"人际")):
        return "social_adaptation"
    if _contains(text, (r"宿舍", r"食堂", r"快递", r"校园", r"报到")):
        return "campus_life"
    if _contains(text, (r"爸妈", r"父母", r"家长", r"我妈", r"我爸")):
        return "family_concern"
    return "general_checkin"


def _memory_content(topic: str, mood: str) -> str:
    if topic == "course_rhythm" and mood in {"anxious", "frustrated"}:
        return "担心信电课程跟不上"
    if topic == "major_choice":
        return "正在理解信电专业方向"
    if topic == "competition_interest":
        return "对信电竞赛或实验室感兴趣"
    if topic == "social_adaptation":
        return "正在适应大学人际关系"
    if topic == "family_concern":
        return "在处理家长沟通带来的压力"
    return ""


def _is_refusal(text: str) -> bool:
    return _contains(text, (r"别聊", r"不想聊", r"别问", r"换个话题", r"先不说这个"))


def analyze(user_msg: str, current_state: dict[str, Any] | None = None) -> dict[str, Any]:
    text = (user_msg or "").strip()
    current_state = current_state or {}
    mood = _mood(text)

    if _is_refusal(text):
        hook = dict(current_state.get("next_hook") or {})
        if not hook:
            hook = {"topic": "general_checkin", "label": TOPIC_LABELS["general_checkin"]}
        hook["active"] = False
        return {
            "stage_signal": current_state.get("user_stage", "prospective"),
            "mood": mood,
            "topic": "general_checkin",
            "memory_worthy": False,
            "memory_type": "",
            "memory_content": "",
            "reply_strategy": "尊重用户不想继续的话题，轻轻切换到开放陪伴。",
            "next_hook": hook,
        }

    stage = _stage_signal(text)
    topic = _topic(text)
    content = _memory_content(topic, mood)
    memory_worthy = bool(content and mood != "crisis")
    hook = {
        "topic": topic,
        "label": TOPIC_LABELS.get(topic, TOPIC_LABELS["general_checkin"]),
        "active": topic != "general_checkin",
    }

    return {
        "stage_signal": stage,
        "mood": mood,
        "topic": topic,
        "memory_worthy": memory_worthy,
        "memory_type": "concern" if memory_worthy else "",
        "memory_content": content,
        "reply_strategy": "先承接情绪，再给一个短期方向，最后问一个低压力问题。",
        "next_hook": hook,
    }
```

- [ ] **Step 4: Run analyzer tests and verify they pass**

Run:

```powershell
python -m unittest web.tests.test_relationship.TurnAnalyzerTest -v
```

Expected: PASS for all 3 tests.

- [ ] **Step 5: Commit analyzer**

Run:

```powershell
git add web\\turn_analyzer.py web\\tests\\test_relationship.py
git commit -m "feat: add relationship turn analyzer"
```

Expected: commit succeeds.

---

### Task 2: Relationship State Store And Greeting Rules

**Files:**
- Create: `web/relationship_state.py`
- Modify: `web/tests/test_relationship.py`

- [ ] **Step 1: Add failing state and greeting tests**

Append these imports and tests to `web/tests/test_relationship.py`:

```python
from datetime import datetime, timezone

import relationship_state


class RelationshipStateTest(unittest.TestCase):
    def test_load_state_creates_default_without_saving(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = relationship_state.load_state(Path(tmp), "alice")

            self.assertEqual(state["user_stage"], "prospective")
            self.assertEqual(state["relationship_level"], 1)
            self.assertIsNone(state["last_greeting_date"])
            self.assertFalse((Path(tmp) / "relationship_alice.json").exists())

    def test_update_after_turn_persists_stage_mood_topic_and_hook(self):
        now = datetime(2026, 6, 5, 10, 0, tzinfo=timezone.utc)
        state = relationship_state.default_state()
        analysis = turn_analyzer.analyze("信电会不会很难，我怕跟不上。")

        updated = relationship_state.update_after_turn(state, analysis, now=now)

        self.assertEqual(updated["user_stage"], "prospective")
        self.assertEqual(updated["recent_mood"], "anxious")
        self.assertEqual(updated["recent_topic"], "course_rhythm")
        self.assertEqual(updated["core_concern"], "担心信电课程跟不上")
        self.assertEqual(updated["next_hook"]["topic"], "course_rhythm")
        self.assertEqual(updated["next_hook"]["last_mentioned"], "2026-06-05T10:00:00+00:00")

    def test_stage_profile_maps_early_freshman_to_existing_growth_profile(self):
        self.assertEqual(relationship_state.growth_profile_for_stage("prospective"), "想象大学生活")
        self.assertEqual(relationship_state.growth_profile_for_stage("pre_enrollment"), "准备入学")
        self.assertEqual(relationship_state.growth_profile_for_stage("early_freshman"), "大一上")

    def test_contextual_greeting_once_per_day_then_generic(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            state = relationship_state.default_state()
            state["next_hook"] = {
                "topic": "course_rhythm",
                "label": "课程节奏",
                "last_mentioned": "2026-06-04T10:00:00+00:00",
                "active": True,
            }
            relationship_state.save_state(data_dir, "alice", state)

            first = relationship_state.greeting_payload(data_dir, "alice", today="2026-06-05")
            second = relationship_state.greeting_payload(data_dir, "alice", today="2026-06-05")

            self.assertIn("课程节奏", first["greeting"])
            self.assertEqual(first["kind"], "contextual")
            self.assertNotIn("课程节奏", second["greeting"])
            self.assertEqual(second["kind"], "generic")

    def test_greeting_avoids_clingy_memory_language(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            state = relationship_state.default_state()
            state["next_hook"] = {
                "topic": "course_rhythm",
                "label": "课程节奏",
                "last_mentioned": "2026-06-04T10:00:00+00:00",
                "active": True,
            }
            relationship_state.save_state(data_dir, "alice", state)

            payload = relationship_state.greeting_payload(data_dir, "alice", today="2026-06-05")

            forbidden = ("我一直记得", "我一直在想", "我等你很久", "你怎么又不来了")
            for phrase in forbidden:
                self.assertNotIn(phrase, payload["greeting"])
```

- [ ] **Step 2: Run state tests and verify they fail**

Run:

```powershell
python -m unittest web.tests.test_relationship.RelationshipStateTest -v
```

Expected: FAIL or ERROR because `web/relationship_state.py` does not exist.

- [ ] **Step 3: Implement `web/relationship_state.py`**

Create `web/relationship_state.py`:

```python
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
    if analysis:
        lines.append(f"- 本轮策略：{analysis.get('reply_strategy', '')}")
    return "\n".join(line for line in lines if line.strip())


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
```

- [ ] **Step 4: Run state tests and verify they pass**

Run:

```powershell
python -m unittest web.tests.test_relationship.RelationshipStateTest -v
```

Expected: PASS for all state tests.

- [ ] **Step 5: Run all relationship tests**

Run:

```powershell
python -m unittest web.tests.test_relationship -v
```

Expected: PASS.

- [ ] **Step 6: Commit relationship state**

Run:

```powershell
git add web\\relationship_state.py web\\tests\\test_relationship.py
git commit -m "feat: add relationship state store"
```

Expected: commit succeeds.

---

### Task 3: Prompt And Payload Integration

**Files:**
- Modify: `web/app.py`
- Modify: `web/tests/test_relationship.py`

- [ ] **Step 1: Add failing prompt and payload tests**

Append these tests to `web/tests/test_relationship.py`:

```python
import importlib
import os
from unittest.mock import patch


class AppPromptPayloadTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("DEEPSEEK_API_KEY", "test-key")
        cls.app_module = importlib.import_module("app")

    def test_build_system_prompt_includes_relationship_constraints(self):
        state = relationship_state.default_state()
        state["recent_mood"] = "anxious"
        state["recent_topic"] = "course_rhythm"
        state["next_hook"] = {
            "topic": "course_rhythm",
            "label": "课程节奏",
            "active": True,
        }
        analysis = turn_analyzer.analyze("信电会不会很难，我怕跟不上。", state)

        with patch.object(self.app_module, "run_tool", return_value=""):
            prompt = self.app_module.build_system_prompt("alice", state, analysis)

        self.assertIn("【关系状态】", prompt)
        self.assertIn("课程节奏", prompt)
        self.assertIn("不要说“我一直记得你”", prompt)

    def test_record_chat_reply_returns_relationship_payload_fields(self):
        app_module = self.app_module
        state = relationship_state.default_state()
        analysis = turn_analyzer.analyze("信电会不会很难，我怕跟不上。", state)
        updated = relationship_state.update_after_turn(state, analysis)

        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(app_module, "DATA_DIR", Path(tmp)):
                with patch.object(app_module, "auto_save_memory", return_value=None):
                    payload = app_module.record_chat_reply(
                        "alice",
                        "sid-1",
                        [],
                        "信电会不会很难，我怕跟不上。",
                        "这份担心挺正常，我们先把开学第一个月拆小一点。[smile]",
                        relationship=updated,
                        next_hook=updated["next_hook"],
                        companion_action=relationship_state.companion_action(updated),
                    )

        self.assertEqual(payload["state"]["recent_mood"], "anxious")
        self.assertEqual(payload["next_hook"]["topic"], "course_rhythm")
        self.assertEqual(payload["companion_action"]["kind"], "listen")
```

- [ ] **Step 2: Run prompt and payload tests and verify they fail**

Run:

```powershell
python -m unittest web.tests.test_relationship.AppPromptPayloadTest -v
```

Expected: FAIL because `build_system_prompt()` and `record_chat_reply()` do not yet accept relationship arguments.

- [ ] **Step 3: Import new modules and extend expression parsing**

In `web/app.py`, add imports under `import boundary_guard as guard`:

```python
import relationship_state
import turn_analyzer
```

In `parse_expression()`, replace the pattern line with:

```python
    pattern = r'\[(smile|soft_smile|cheer|think|proud|wink|wave|surprise|love|sweat|sad)\]'
```

- [ ] **Step 4: Extend `build_system_prompt()`**

Replace the function signature and tail of `build_system_prompt()` with this version:

```python
def build_system_prompt(
    user_id: str,
    relationship: dict | None = None,
    turn_analysis: dict | None = None,
) -> str:
    """构建完整 system prompt = SKILL.md + 记忆 + 成长 + 关系状态"""
    parts = [load_skill_md()]

    mem = run_tool("memory_load", user_id)
    if mem and "没有" not in mem:
        parts.append("\n" + mem)

    growth = run_tool("growth_snapshot", user_id)
    if growth and "一起走过的路" in growth:
        parts.append("\n" + growth)

    if relationship:
        parts.append("\n" + relationship_state.prompt_summary(relationship, turn_analysis))

    parts.append(
        "\n记住：你是小信，不是AI助手。用简短口语回复，每次2-4句话。"
        "带上表情标记。接续旧线索时要轻，不要显得一直惦记用户。"
    )
    return "\n\n".join(parts)
```

- [ ] **Step 5: Extend `record_chat_reply()`**

Replace the function signature:

```python
def record_chat_reply(
    user_id: str,
    sid: str,
    history: list[dict],
    user_msg: str,
    reply: str,
    relationship: dict | None = None,
    next_hook: dict | None = None,
    companion_action: dict | None = None,
) -> dict:
```

Replace the final `return { ... }` block with:

```python
    payload = {
        "reply": clean_reply,
        "speech": guard.to_speech_text(clean_reply),
        "expression": expression,
        "model": MODEL,
        "session_id": sid,
    }

    if relationship is not None:
        payload["state"] = relationship_state.public_state(relationship)
    if next_hook is not None:
        payload["next_hook"] = next_hook
    if companion_action is not None:
        payload["companion_action"] = companion_action

    return payload
```

- [ ] **Step 6: Run prompt and payload tests and verify they pass**

Run:

```powershell
python -m unittest web.tests.test_relationship.AppPromptPayloadTest -v
```

Expected: PASS.

- [ ] **Step 7: Commit prompt and payload integration**

Run:

```powershell
git add web\\app.py web\\tests\\test_relationship.py
git commit -m "feat: include relationship context in chat payloads"
```

Expected: commit succeeds.

---

### Task 4: `/api/chat` Relationship State Updates

**Files:**
- Modify: `web/app.py`
- Modify: `web/tests/test_relationship.py`

- [ ] **Step 1: Add failing `/api/chat` integration test**

Append this test class to `web/tests/test_relationship.py`:

```python
class ChatRelationshipRouteTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("DEEPSEEK_API_KEY", "test-key")
        cls.app_module = importlib.import_module("app")

    def test_chat_updates_relationship_state_and_returns_hook(self):
        app_module = self.app_module

        class FakeMessage:
            content = "怕跟不上很正常，我们先把开学第一个月拆小一点。[smile]"

        class FakeChoice:
            finish_reason = "stop"
            message = FakeMessage()

        class FakeResponse:
            choices = [FakeChoice()]

        class FakeCompletions:
            def create(self, **kwargs):
                return FakeResponse()

        class FakeChat:
            completions = FakeCompletions()

        class FakeClient:
            chat = FakeChat()

        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            app_module.active_conversations.clear()
            with patch.object(app_module, "DATA_DIR", data_dir):
                with patch.object(app_module, "run_tool", return_value=""):
                    with patch.object(app_module, "client", FakeClient()):
                        client = app_module.app.test_client()
                        response = client.post("/api/chat", json={
                            "user_id": "alice",
                            "message": "信电会不会很难，我怕跟不上。",
                        })

            payload = response.get_json()
            saved = relationship_state.load_state(data_dir, "alice")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["state"]["recent_mood"], "anxious")
        self.assertEqual(payload["next_hook"]["topic"], "course_rhythm")
        self.assertEqual(saved["next_hook"]["topic"], "course_rhythm")
        self.assertEqual(saved["core_concern"], "担心信电课程跟不上")
```

- [ ] **Step 2: Run route test and verify it fails**

Run:

```powershell
python -m unittest web.tests.test_relationship.ChatRelationshipRouteTest -v
```

Expected: FAIL because `/api/chat` does not yet update relationship state or return hook fields.

- [ ] **Step 3: Add relationship analysis at the start of `chat()`**

In `web/app.py`, inside `chat()` after the active history line:

```python
    _, history = active_conversations[user_id]

    relationship = relationship_state.load_state(DATA_DIR, user_id)
    turn_analysis = turn_analyzer.analyze(user_msg, relationship)
```

- [ ] **Step 4: Update guarded replies to persist relationship state**

Replace the guarded block in `chat()` with:

```python
    guarded_reply = guard.template_reply(user_msg)
    if guarded_reply:
        relationship = relationship_state.update_after_turn(relationship, turn_analysis)
        relationship_state.save_state(DATA_DIR, user_id, relationship)
        payload = record_chat_reply(
            user_id,
            sid,
            history,
            user_msg,
            guarded_reply,
            relationship=relationship,
            next_hook=relationship.get("next_hook"),
            companion_action=relationship_state.companion_action(relationship),
        )
        print(f"[小信/guard] > {payload['reply']}")
        return jsonify(payload)
```

- [ ] **Step 5: Pass relationship context into prompt construction**

Replace:

```python
    system_prompt = build_system_prompt(user_id)
```

with:

```python
    system_prompt = build_system_prompt(user_id, relationship, turn_analysis)
```

- [ ] **Step 6: Persist state before returning normal model replies**

Replace the final payload creation in `chat()`:

```python
    payload = record_chat_reply(user_id, sid, history, user_msg, reply)
```

with:

```python
    relationship = relationship_state.update_after_turn(relationship, turn_analysis)
    relationship_state.save_state(DATA_DIR, user_id, relationship)
    payload = record_chat_reply(
        user_id,
        sid,
        history,
        user_msg,
        reply,
        relationship=relationship,
        next_hook=relationship.get("next_hook"),
        companion_action=relationship_state.companion_action(relationship),
    )
```

- [ ] **Step 7: Run chat route test and verify it passes**

Run:

```powershell
python -m unittest web.tests.test_relationship.ChatRelationshipRouteTest -v
```

Expected: PASS.

- [ ] **Step 8: Commit chat relationship updates**

Run:

```powershell
git add web\\app.py web\\tests\\test_relationship.py
git commit -m "feat: update relationship state during chat"
```

Expected: commit succeeds.

---

### Task 5: `/api/greeting` Route

**Files:**
- Modify: `web/app.py`
- Modify: `web/tests/test_relationship.py`

- [ ] **Step 1: Add failing greeting route test**

Append this test class to `web/tests/test_relationship.py`:

```python
class GreetingRouteTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("DEEPSEEK_API_KEY", "test-key")
        cls.app_module = importlib.import_module("app")

    def test_greeting_route_uses_context_once_per_day(self):
        app_module = self.app_module
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            state = relationship_state.default_state()
            state["next_hook"] = {
                "topic": "course_rhythm",
                "label": "课程节奏",
                "last_mentioned": "2026-06-04T10:00:00+00:00",
                "active": True,
            }
            relationship_state.save_state(data_dir, "alice", state)

            with patch.object(app_module, "DATA_DIR", data_dir):
                client = app_module.app.test_client()
                first = client.get("/api/greeting?user_id=alice&today=2026-06-05").get_json()
                second = client.get("/api/greeting?user_id=alice&today=2026-06-05").get_json()

        self.assertEqual(first["kind"], "contextual")
        self.assertIn("课程节奏", first["greeting"])
        self.assertEqual(second["kind"], "generic")
        self.assertNotIn("课程节奏", second["greeting"])
```

- [ ] **Step 2: Run greeting route test and verify it fails**

Run:

```powershell
python -m unittest web.tests.test_relationship.GreetingRouteTest -v
```

Expected: FAIL with 404 because `/api/greeting` does not exist.

- [ ] **Step 3: Add `/api/greeting` route to `web/app.py`**

Add this route after `index()` and before `/api/chat`:

```python
@app.route("/api/greeting", methods=["GET"])
def greeting():
    """返回当天打开页面或设备唤醒时的小信轻量问候。"""
    user_id = request.args.get("user_id", "default")
    today = request.args.get("today")
    payload = relationship_state.greeting_payload(DATA_DIR, user_id, today=today)
    return jsonify(payload)
```

- [ ] **Step 4: Run greeting route test and verify it passes**

Run:

```powershell
python -m unittest web.tests.test_relationship.GreetingRouteTest -v
```

Expected: PASS.

- [ ] **Step 5: Commit greeting route**

Run:

```powershell
git add web\\app.py web\\tests\\test_relationship.py
git commit -m "feat: add relationship greeting route"
```

Expected: commit succeeds.

---

### Task 6: Web Greeting Display

**Files:**
- Modify: `web/static/index.html`

- [ ] **Step 1: Add `soft_smile` expression mapping**

In `web/static/index.html`, replace:

```javascript
  smile:'😊',cheer:'💪',think:'🤔',proud:'😎',wink:'😉',wave:'👋',surprise:'😮',love:'🥰',sweat:'😅',sad:'😢'
```

with:

```javascript
  smile:'😊',soft_smile:'😊',cheer:'💪',think:'🤔',proud:'😎',wink:'😉',wave:'👋',surprise:'😮',love:'🥰',sweat:'😅',sad:'😢'
```

- [ ] **Step 2: Add greeting fetch helper**

In `web/static/index.html`, after `function addMessage(role, text, expression) { ... }`, add:

```javascript
async function loadGreeting() {
  try {
    const res = await fetch(`/api/greeting?user_id=${encodeURIComponent(userId)}`);
    const data = await res.json();
    if (data && data.greeting) {
      addMessage('bot', data.greeting, data.expression || 'smile');
    }
  } catch (err) {
    console.warn('greeting unavailable', err);
  }
}
```

- [ ] **Step 3: Call greeting on initial page load only when no session messages are rendered**

Find the existing page-load logic that renders the welcome hint or loads sessions. Add this call after the first empty-state render:

```javascript
loadGreeting();
```

If the file currently adds a static welcome hint before any messages, keep the static hint and let the greeting appear as Xiaoxin's first bot message.

- [ ] **Step 4: Verify no syntax typo in the edited JavaScript**

Run:

```powershell
Select-String -Path web\\static\\index.html -Pattern "soft_smile|loadGreeting|api/greeting"
```

Expected: output includes all three patterns.

- [ ] **Step 5: Commit web greeting display**

Run:

```powershell
git add web\\static\\index.html
git commit -m "feat: show daily relationship greeting in web chat"
```

Expected: commit succeeds.

---

### Task 7: Full Regression And Manual Smoke Test

**Files:**
- Modify only if earlier tests reveal a concrete defect in files changed by this plan.

- [ ] **Step 1: Run relationship tests**

Run:

```powershell
python -m unittest web.tests.test_relationship -v
```

Expected: PASS.

- [ ] **Step 2: Run boundary guard tests**

Run:

```powershell
python -m unittest web.tests.test_boundary_guard -v
```

Expected: PASS.

- [ ] **Step 3: Run skill boundary tests**

Run:

```powershell
python -m unittest web.tests.test_skill_boundaries -v
```

Expected: PASS.

- [ ] **Step 4: Run self-play route/layout tests that do not require live model calls**

Run:

```powershell
python -m unittest web.tests.test_selfplay_layout web.tests.test_selfplay_openings -v
```

Expected: PASS.

- [ ] **Step 5: Run the Flask app for manual smoke testing**

Run:

```powershell
cd web
python app.py
```

Expected: server starts on `http://localhost:5000`. If port 5000 is already occupied, stop the existing local server or set Flask to another port before smoke testing.

- [ ] **Step 6: Smoke test greeting in browser**

Open:

```text
http://localhost:5000
```

Expected:

- On first load for a user with no relationship state, Xiaoxin shows a generic greeting.
- After chatting “信电会不会很难，我怕跟不上。”, the `/api/chat` response includes `state`, `next_hook`, and `companion_action`.
- On the next simulated day through `/api/greeting?user_id=default&today=2026-06-06`, greeting can lightly mention “课程节奏”.
- A second call for the same day returns generic greeting.

- [ ] **Step 7: Check git status**

Run:

```powershell
git status --short
```

Expected: clean working tree after all commits.

---

## Self-Review Checklist

- Spec coverage:
  - Relationship state: Task 2.
  - Structured `next_hook`: Task 1 and Task 2.
  - Stage alignment with existing growth profile: Task 2.
  - `/api/chat` state return: Task 3 and Task 4.
  - `/api/greeting` once-per-day behavior: Task 2 and Task 5.
  - Web validation path: Task 6.
  - Tests in `web/tests/test_relationship.py`: Tasks 1-5.
  - Existing boundary regressions: Task 7.

- Type consistency:
  - `turn_analyzer.analyze(user_msg, current_state=None)` returns `stage_signal`, `mood`, `topic`, `memory_worthy`, `memory_type`, `memory_content`, `reply_strategy`, and `next_hook`.
  - `relationship_state.update_after_turn(state, analysis, now=None)` returns a full state dict.
  - `relationship_state.greeting_payload(data_dir, user_id, today=None)` returns `greeting`, `speech`, `expression`, `kind`, and `companion_action`.
  - `record_chat_reply(..., relationship=None, next_hook=None, companion_action=None)` returns existing fields plus optional relationship fields.

- Scope control:
  - No push notifications.
  - No game-like affection UI.
  - No additional LLM calls for analysis.
  - No development-board implementation.
