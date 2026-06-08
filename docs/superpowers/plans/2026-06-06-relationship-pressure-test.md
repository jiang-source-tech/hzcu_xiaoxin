# Relationship Pressure Test Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add regression, mixed, and pressure run modes to `/relationship-test` so each relationship-test day can contain many user-LLM and Xiaoxin-LLM turns while preserving the current deterministic regression path.

**Architecture:** Keep the existing `/relationship-test` route and v2 streaming runner. Add request validation in `web/app.py`, pressure-message generation in `web/user_simulator.py`, turn planning and same-day continuation in `web/scene_runner.py`, and grouped day rendering plus controls in `web/static/relationship-v2-test.html`.

**Tech Stack:** Flask, Python unittest/pytest-compatible tests, browser-native HTML/CSS/JavaScript, DeepSeek-compatible OpenAI client.

---

## File Map

- Modify `web/app.py`
  - Validate `mode` and `turns_per_day` in `v2_relationship_run()`.
  - Pass the validated options into `scene_runner_v2.run_scene_streaming()`.

- Modify `web/user_simulator.py`
  - Add `build_pressure_user_messages()`.
  - Add `generate_pressure_user_message()`.
  - Reuse `_call_api()` and the existing prefix stripping pattern.

- Modify `web/scene_runner.py`
  - Add constants for supported run modes.
  - Add helpers for validating mode, selecting turn budgets, deriving daily pressure goals, summarizing one day, and deciding turn sources.
  - Extend `run_scene_streaming()` with `mode` and `turns_per_day`.
  - Emit `turn_source` and `day_summary` on every chat record.
  - Preserve existing `regression` behavior when no new options are provided.

- Modify `web/static/relationship-v2-test.html`
  - Add mode and turns-per-day controls.
  - Include new request fields in the run request.
  - Group rendered records by scene and day.
  - Label each turn as `scripted`, `pressure`, or `greeting`.
  - Show a day summary and final state for each day.

- Modify `web/tests/test_scene_runner.py`
  - Add runner helper tests.
  - Add regression, mixed, and pressure streaming tests.

- Modify `web/tests/test_relationship_v2_page.py`
  - Add tests for page controls and day grouping functions.

- Create `web/tests/test_relationship_v2_api.py`
  - Add API tests for accepted and rejected pressure-mode parameters.

---

### Task 1: API Validation For Pressure Options

**Files:**
- Create: `web/tests/test_relationship_v2_api.py`
- Modify: `web/app.py`
- Test: `web/tests/test_relationship_v2_api.py`

- [ ] **Step 1: Write API tests for mode and turn validation**

Create `web/tests/test_relationship_v2_api.py`:

```python
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("DEEPSEEK_API_KEY", "test-key")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app as app_module


class RelationshipV2ApiTest(unittest.TestCase):
    def setUp(self):
        self.client = app_module.app.test_client()

    def test_run_accepts_mode_and_turns_per_day(self):
        captured = {}

        def fake_stream(**kwargs):
            captured.update(kwargs)
            yield {
                "event": "complete",
                "data": {
                    "scene_id": "demo",
                    "name": "Demo",
                    "description": "",
                    "seed": 7,
                    "verdict": "PASS",
                    "rule_violations_count": 0,
                    "quality_avg_score": 0,
                    "notes": "",
                    "records": [],
                    "quality_judge": None,
                },
            }

        with patch.object(app_module.scene_runner_v2, "run_scene_streaming", side_effect=fake_stream):
            response = self.client.post(
                "/api/v2/relationship-selfplay/run",
                json={
                    "scene": "anxious_prospective",
                    "seed": 7,
                    "skip_judge": True,
                    "mode": "mixed",
                    "turns_per_day": 12,
                    "max_days": 2,
                },
            )

        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn("event: complete", body)
        self.assertEqual(captured["scene_id"], "anxious_prospective")
        self.assertEqual(captured["seed"], 7)
        self.assertTrue(captured["skip_quality_judge"])
        self.assertEqual(captured["mode"], "mixed")
        self.assertEqual(captured["turns_per_day"], 12)
        self.assertEqual(captured["max_days"], 2)

    def test_run_rejects_invalid_mode_before_streaming(self):
        response = self.client.post(
            "/api/v2/relationship-selfplay/run",
            json={"mode": "wild", "turns_per_day": 8},
        )

        self.assertEqual(response.status_code, 400)
        payload = response.get_json()
        self.assertIn("mode", payload["error"])

    def test_run_rejects_invalid_turns_per_day_before_streaming(self):
        for value in (0, -1, "many"):
            with self.subTest(value=value):
                response = self.client.post(
                    "/api/v2/relationship-selfplay/run",
                    json={"mode": "mixed", "turns_per_day": value},
                )

                self.assertEqual(response.status_code, 400)
                payload = response.get_json()
                self.assertIn("turns_per_day", payload["error"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run API tests to verify they fail**

Run:

```powershell
cd web
python -m pytest tests/test_relationship_v2_api.py -v
```

Expected: at least one failure because `web/app.py` does not validate `mode` and `turns_per_day` yet, and does not pass them into `run_scene_streaming()`.

- [ ] **Step 3: Add validation in `web/app.py`**

In `v2_relationship_run()`, after reading `max_days`, add:

```python
    mode = str(data.get("mode", "regression")).strip() or "regression"
    valid_modes = {"regression", "mixed", "pressure"}
    if mode not in valid_modes:
        return jsonify({"error": "mode must be one of: regression, mixed, pressure"}), 400

    raw_turns_per_day = data.get("turns_per_day")
    turns_per_day = None
    if raw_turns_per_day not in (None, "", "default"):
        try:
            turns_per_day = int(raw_turns_per_day)
        except (TypeError, ValueError):
            return jsonify({"error": "turns_per_day must be a positive integer"}), 400
        if turns_per_day < 1 or turns_per_day > 30:
            return jsonify({"error": "turns_per_day must be between 1 and 30"}), 400
```

Then pass the values into the runner call:

```python
                mode=mode,
                turns_per_day=turns_per_day,
```

- [ ] **Step 4: Run API tests to verify they pass**

Run:

```powershell
cd web
python -m pytest tests/test_relationship_v2_api.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit API validation**

Run:

```powershell
git add web/app.py web/tests/test_relationship_v2_api.py
git commit -m "feat: validate relationship pressure run options"
```

---

### Task 2: Pressure User Simulator

**Files:**
- Modify: `web/user_simulator.py`
- Create or modify: `web/tests/test_user_simulator.py`
- Test: `web/tests/test_user_simulator.py`

- [ ] **Step 1: Add tests for pressure prompt construction and cleaning**

Append to `web/tests/test_user_simulator.py`:

```python
class UserSimulatorPressureTest(unittest.TestCase):
    def test_build_pressure_user_messages_includes_goal_state_and_transcript(self):
        messages = user_simulator.build_pressure_user_messages(
            character={"traits": "An anxious prospective student."},
            pressure_goal="Ask whether Xiaoxin remembers yesterday's course anxiety.",
            same_day_transcript="User: I am worried.\nXiaoxin: We can break it down.",
            prior_day_summary="Day 0: talked about course rhythm.",
            relationship_state={"user_stage": "prospective", "recent_topic": "course_rhythm"},
            forbid_patterns=["do not say probe"],
            turn_index=3,
            turn_count=8,
        )

        text = "\n".join(item["content"] for item in messages)
        self.assertIn("An anxious prospective student.", text)
        self.assertIn("Ask whether Xiaoxin remembers", text)
        self.assertIn("course_rhythm", text)
        self.assertIn("turn 3 of 8", text)
        self.assertIn("do not say probe", text)

    def test_generate_pressure_user_message_strips_role_prefix(self):
        with patch.object(
            user_simulator,
            "_call_api",
            return_value="用户: 我还是有点担心课程节奏。",
        ):
            message = user_simulator.generate_pressure_user_message(
                character={"traits": "An anxious prospective student."},
                pressure_goal="Continue the concern.",
                same_day_transcript="",
                prior_day_summary="",
                relationship_state={},
                forbid_patterns=[],
                seed=11,
                turn_index=1,
                turn_count=4,
            )

        self.assertEqual(message, "我还是有点担心课程节奏。")
```

Ensure the file imports `patch`:

```python
from unittest.mock import patch
```

- [ ] **Step 2: Run simulator tests to verify they fail**

Run:

```powershell
cd web
python -m pytest tests/test_user_simulator.py -v
```

Expected: FAIL because `build_pressure_user_messages()` and `generate_pressure_user_message()` do not exist.

- [ ] **Step 3: Implement pressure message builders in `web/user_simulator.py`**

Add this helper near `build_user_messages()`:

```python
def _strip_role_prefix(raw: str) -> str:
    for prefix in ("新生:", "新生：", "学生:", "学生：", "用户:", "用户："):
        if raw.startswith(prefix):
            return raw[len(prefix):].strip()
    return raw.strip()
```

Update `generate_user_message()` to use it:

```python
    return _strip_role_prefix(raw)
```

Add:

```python
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
    forbidden = ""
    if forbid_patterns:
        items = "、".join(f'"{p}"' for p in forbid_patterns)
        forbidden = f"\nAvoid these unnatural or forbidden phrasings: {items}."

    state_lines = "\n".join(
        f"- {key}: {value}" for key, value in sorted(relationship_state.items())
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
        "You may repeat a concern, drift topics, or say goodbye if that feels realistic. "
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
    return _strip_role_prefix(_call_api(messages, seed))
```

- [ ] **Step 4: Run simulator tests to verify they pass**

Run:

```powershell
cd web
python -m pytest tests/test_user_simulator.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit simulator work**

Run:

```powershell
git add web/user_simulator.py web/tests/test_user_simulator.py
git commit -m "feat: add relationship pressure user simulator"
```

---

### Task 3: Runner Planning Helpers

**Files:**
- Modify: `web/scene_runner.py`
- Modify: `web/tests/test_scene_runner.py`
- Test: `web/tests/test_scene_runner.py`

- [ ] **Step 1: Add tests for turn planning helpers**

Append to `SceneRunnerTest` in `web/tests/test_scene_runner.py`:

```python
    def test_turn_sources_for_regression_preserve_scripted_intents(self):
        episode = {
            "action": "chat",
            "intent": "first scripted intent",
            "followup_intents": ["second scripted intent"],
        }

        turns = scene_runner.plan_chat_turns(episode, mode="regression", turns_per_day=12)

        self.assertEqual(
            turns,
            [
                {"source": "scripted", "intent": "first scripted intent"},
                {"source": "scripted", "intent": "second scripted intent"},
            ],
        )

    def test_turn_sources_for_mixed_extend_to_turn_budget(self):
        episode = {
            "action": "chat",
            "intent": "scripted intent",
            "pressure_goal": "keep exploring the same worry",
        }

        turns = scene_runner.plan_chat_turns(episode, mode="mixed", turns_per_day=3)

        self.assertEqual(turns[0], {"source": "scripted", "intent": "scripted intent"})
        self.assertEqual(turns[1], {"source": "pressure", "intent": "keep exploring the same worry"})
        self.assertEqual(turns[2], {"source": "pressure", "intent": "keep exploring the same worry"})

    def test_turn_sources_for_pressure_use_daily_goal_only(self):
        episode = {
            "action": "chat",
            "intent": "scripted intent",
            "pressure_goal": "free conversation about course anxiety",
            "pressure_turns": 4,
        }

        turns = scene_runner.plan_chat_turns(episode, mode="pressure", turns_per_day=2)

        self.assertEqual(len(turns), 4)
        self.assertTrue(all(turn["source"] == "pressure" for turn in turns))
        self.assertEqual(turns[0]["intent"], "free conversation about course anxiety")

    def test_day_summary_lists_final_state_and_violations(self):
        records = [
            {
                "day": 0,
                "action": "chat",
                "user_message": "I am anxious.",
                "xiaoxin_reply": "We can break it down.",
                "state": {"user_stage": "prospective", "recent_topic": "course_rhythm"},
                "next_hook": {"topic": "course_rhythm", "active": True},
                "violations": [{"type": "boundary"}],
            }
        ]

        summary = scene_runner.summarize_day(records, day=0)

        self.assertIn("Day 0", summary)
        self.assertIn("prospective", summary)
        self.assertIn("course_rhythm", summary)
        self.assertIn("1 violation", summary)
```

- [ ] **Step 2: Run helper tests to verify they fail**

Run:

```powershell
cd web
python -m pytest tests/test_scene_runner.py::SceneRunnerTest::test_turn_sources_for_regression_preserve_scripted_intents tests/test_scene_runner.py::SceneRunnerTest::test_turn_sources_for_mixed_extend_to_turn_budget tests/test_scene_runner.py::SceneRunnerTest::test_turn_sources_for_pressure_use_daily_goal_only tests/test_scene_runner.py::SceneRunnerTest::test_day_summary_lists_final_state_and_violations -v
```

Expected: FAIL because the helper functions do not exist.

- [ ] **Step 3: Implement runner helpers in `web/scene_runner.py`**

Add near the constants:

```python
RUN_MODES = {"regression", "mixed", "pressure"}
DEFAULT_MODE = "regression"
MAX_TURNS_PER_DAY = 30
```

Add near `episode_chat_intents()`:

```python
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


def turn_budget_for_episode(episode: dict[str, Any], turns_per_day: int | None, scripted_count: int) -> int:
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
    day_records = [r for r in records if r.get("day") == day and r.get("action") != "idle_gap"]
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
```

- [ ] **Step 4: Run helper tests to verify they pass**

Run:

```powershell
cd web
python -m pytest tests/test_scene_runner.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit runner helpers**

Run:

```powershell
git add web/scene_runner.py web/tests/test_scene_runner.py
git commit -m "feat: plan relationship pressure turns"
```

---

### Task 4: Streaming Runner Pressure Modes

**Files:**
- Modify: `web/scene_runner.py`
- Modify: `web/tests/test_scene_runner.py`
- Test: `web/tests/test_scene_runner.py`

- [ ] **Step 1: Add streaming tests for mixed and pressure mode**

Append to `SceneRunnerTest`:

```python
    def test_streaming_regression_marks_scripted_turn_source(self):
        def chat_fn(user_id, user_msg, raw_data_dir):
            state = relationship_state.default_state()
            relationship_state.save_state(Path(raw_data_dir), user_id, state)
            return {"reply": f"reply to {user_msg}"}

        with patch.object(
            scene_runner.user_simulator,
            "generate_user_message",
            side_effect=lambda **kwargs: kwargs["intent"],
        ):
            events = list(scene_runner.run_scene_streaming(
                scene_id="anxious_prospective",
                seed=1,
                skip_quality_judge=True,
                max_days=0,
                mode="regression",
                turns_per_day=8,
                chat_fn=chat_fn,
                greeting_fn=lambda *_args: {"greeting": "hello"},
            ))

        episodes = [e["data"] for e in events if e["event"] == "episode" and e["data"]["action"] == "chat"]
        self.assertGreaterEqual(len(episodes), 1)
        self.assertTrue(all(ep["turn_source"] == "scripted" for ep in episodes))
        self.assertTrue(all("day_summary" in ep for ep in episodes))

    def test_streaming_mixed_adds_pressure_turns_after_scripted_turns(self):
        def chat_fn(user_id, user_msg, raw_data_dir):
            state = relationship_state.default_state()
            relationship_state.save_state(Path(raw_data_dir), user_id, state)
            return {"reply": f"reply to {user_msg}"}

        with patch.object(
            scene_runner.user_simulator,
            "generate_user_message",
            side_effect=lambda **kwargs: f"scripted:{kwargs['intent']}",
        ), patch.object(
            scene_runner.user_simulator,
            "generate_pressure_user_message",
            side_effect=lambda **kwargs: f"pressure:{kwargs['turn_index']}",
        ):
            events = list(scene_runner.run_scene_streaming(
                scene_id="anxious_prospective",
                seed=1,
                skip_quality_judge=True,
                max_days=0,
                mode="mixed",
                turns_per_day=4,
                chat_fn=chat_fn,
                greeting_fn=lambda *_args: {"greeting": "hello"},
            ))

        episodes = [e["data"] for e in events if e["event"] == "episode" and e["data"]["action"] == "chat"]
        self.assertEqual(len(episodes), 4)
        self.assertEqual([ep["turn_source"] for ep in episodes], ["scripted", "scripted", "scripted", "pressure"])
        self.assertEqual([ep["turn_index"] for ep in episodes], [1, 2, 3, 4])
        self.assertTrue(all(ep["turn_count"] == 4 for ep in episodes))

    def test_streaming_pressure_mode_uses_pressure_generator_only(self):
        def chat_fn(user_id, user_msg, raw_data_dir):
            state = relationship_state.default_state()
            relationship_state.save_state(Path(raw_data_dir), user_id, state)
            return {"reply": f"reply to {user_msg}"}

        with patch.object(
            scene_runner.user_simulator,
            "generate_user_message",
            side_effect=AssertionError("scripted generator should not run"),
        ), patch.object(
            scene_runner.user_simulator,
            "generate_pressure_user_message",
            side_effect=lambda **kwargs: f"pressure:{kwargs['turn_index']}",
        ):
            events = list(scene_runner.run_scene_streaming(
                scene_id="anxious_prospective",
                seed=1,
                skip_quality_judge=True,
                max_days=0,
                mode="pressure",
                turns_per_day=3,
                chat_fn=chat_fn,
                greeting_fn=lambda *_args: {"greeting": "hello"},
            ))

        episodes = [e["data"] for e in events if e["event"] == "episode" and e["data"]["action"] == "chat"]
        self.assertEqual(len(episodes), 3)
        self.assertTrue(all(ep["turn_source"] == "pressure" for ep in episodes))
        self.assertEqual([ep["user_message"] for ep in episodes], ["pressure:1", "pressure:2", "pressure:3"])
```

- [ ] **Step 2: Run streaming tests to verify they fail**

Run:

```powershell
cd web
python -m pytest tests/test_scene_runner.py::SceneRunnerTest::test_streaming_regression_marks_scripted_turn_source tests/test_scene_runner.py::SceneRunnerTest::test_streaming_mixed_adds_pressure_turns_after_scripted_turns tests/test_scene_runner.py::SceneRunnerTest::test_streaming_pressure_mode_uses_pressure_generator_only -v
```

Expected: FAIL because `run_scene_streaming()` does not accept or emit pressure-mode fields yet.

- [ ] **Step 3: Extend `run_scene_streaming()` signature**

Change the signature:

```python
def run_scene_streaming(
    scene_id: str = "all",
    seed: int | None = None,
    skip_quality_judge: bool = False,
    max_days: int | None = None,
    chat_fn: Callable[[str, str, str], dict[str, Any]] | None = None,
    greeting_fn: Callable[[str, str, str], dict[str, Any]] | None = None,
    base_date: datetime | None = None,
    mode: str = DEFAULT_MODE,
    turns_per_day: int | None = None,
) -> Generator[dict[str, Any], None, None]:
```

At the start of the function after seed handling:

```python
    mode = validate_run_mode(mode)
    if turns_per_day is not None:
        turns_per_day = max(1, min(MAX_TURNS_PER_DAY, int(turns_per_day)))
```

- [ ] **Step 4: Replace chat loop with planned turns**

In the `else` branch for chat episodes, replace `intents = ...` and the loop with:

```python
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
                prior_day_summary = "\n".join(
                    summarize_day(records, d)
                    for d in sorted({r.get("day") for r in records if isinstance(r.get("day"), int) and r.get("day") < episode["day"]})[-3:]
                )

                for turn_offset, planned in enumerate(planned_turns):
                    turn_index = turn_offset + 1
                    intent = planned["intent"]
                    turn_source = planned["source"]
                    if turn_source == "pressure":
                        current_state = relationship_state.public_state(
                            relationship_state.load_state(data_dir, user_id)
                        )
                        same_day_transcript = summarize_conversation(same_day_records)
                        user_msg = user_simulator.generate_pressure_user_message(
                            character=character,
                            pressure_goal=intent,
                            same_day_transcript=same_day_transcript,
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
                            character=character,
                            intent=intent,
                            conversation_summary=conv_summary,
                            forbid_patterns=forbid,
                            seed=ep_seed + turn_offset,
                        )
```

Keep the existing `chat_fn`, state loading, `rule_evaluator.evaluate_episode()`, and record creation. Add fields to the record:

```python
                        "turn_source": turn_source,
```

After creating the record, compute its day summary and append it to both collections:

```python
                    record["day_summary"] = summarize_day(
                        [*records, *same_day_records, record], episode["day"]
                    )
                    same_day_records.append(record)
                    records.append(record)
```

- [ ] **Step 5: Ensure greeting and idle records include `turn_source`**

For greeting records, add:

```python
                    "turn_source": "greeting",
```

Then immediately after the record literal:

```python
                record["day_summary"] = summarize_day([*records, record], episode["day"])
```

For idle-gap records, add:

```python
        "turn_source": "idle_gap",
        "day_summary": "",
```

- [ ] **Step 6: Run scene runner tests**

Run:

```powershell
cd web
python -m pytest tests/test_scene_runner.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit streaming modes**

Run:

```powershell
git add web/scene_runner.py web/tests/test_scene_runner.py
git commit -m "feat: stream relationship pressure turns"
```

---

### Task 5: Page Controls And Request Payload

**Files:**
- Modify: `web/static/relationship-v2-test.html`
- Modify: `web/tests/test_relationship_v2_page.py`
- Test: `web/tests/test_relationship_v2_page.py`

- [ ] **Step 1: Add page tests for controls and request fields**

Append to `RelationshipV2PageTest`:

```python
    def test_page_exposes_pressure_mode_controls(self):
        expected_snippets = [
            'id="modeSelect"',
            'value="mixed"',
            'value="regression"',
            'value="pressure"',
            'id="turnsPerDaySelect"',
            "turns_per_day",
            "mode: mode",
        ]

        for snippet in expected_snippets:
            with self.subTest(snippet=snippet):
                self.assertIn(snippet, self.html)
```

- [ ] **Step 2: Run page tests to verify they fail**

Run:

```powershell
cd web
python -m pytest tests/test_relationship_v2_page.py -v
```

Expected: FAIL because the controls and request payload fields are missing.

- [ ] **Step 3: Add controls to the toolbar**

In `web/static/relationship-v2-test.html`, inside `<div class="toolbar">`, after scene selection, add:

```html
    <div>
      <label for="modeSelect">模式</label>
      <select id="modeSelect">
        <option value="mixed" selected>混合压力</option>
        <option value="regression">固定回归</option>
        <option value="pressure">自由压力</option>
      </select>
    </div>
    <div>
      <label for="turnsPerDaySelect">每天轮数</label>
      <select id="turnsPerDaySelect">
        <option value="3">3</option>
        <option value="8">8</option>
        <option value="12" selected>12</option>
        <option value="16">16</option>
      </select>
    </div>
```

- [ ] **Step 4: Include mode and turn count in `startRun()`**

In `startRun()`, after reading `scene`, add:

```javascript
    const mode = document.getElementById('modeSelect').value;
    const turnsPerDay = parseInt(document.getElementById('turnsPerDaySelect').value, 10);
```

In the JSON body, add:

```javascript
        mode: mode,
        turns_per_day: turnsPerDay,
```

- [ ] **Step 5: Run page tests**

Run:

```powershell
cd web
python -m pytest tests/test_relationship_v2_page.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit page controls**

Run:

```powershell
git add web/static/relationship-v2-test.html web/tests/test_relationship_v2_page.py
git commit -m "feat: add relationship pressure controls"
```

---

### Task 6: Group Relationship Results By Day

**Files:**
- Modify: `web/static/relationship-v2-test.html`
- Modify: `web/tests/test_relationship_v2_page.py`
- Test: `web/tests/test_relationship_v2_page.py`

- [ ] **Step 1: Add page tests for day grouping and labels**

Append to `RelationshipV2PageTest`:

```python
    def test_page_groups_records_by_day_and_labels_turn_source(self):
        expected_snippets = [
            "showDaySection",
            "day-section",
            "day-body",
            "turn_source",
            "formatTurnSource",
            "day_summary",
            "day-summary",
        ]

        for snippet in expected_snippets:
            with self.subTest(snippet=snippet):
                self.assertIn(snippet, self.html)
```

- [ ] **Step 2: Run page tests to verify they fail**

Run:

```powershell
cd web
python -m pytest tests/test_relationship_v2_page.py -v
```

Expected: FAIL because day grouping functions and classes are missing.

- [ ] **Step 3: Add CSS for day sections**

Add styles near the existing episode styles:

```css
  .day-section {
    border: 1px solid var(--line);
    border-radius: var(--radius);
    margin: 14px 0;
    overflow: hidden;
    background: var(--surface);
  }
  .day-head {
    display: flex;
    justify-content: space-between;
    gap: 12px;
    padding: 10px 12px;
    background: var(--surface-soft);
    cursor: pointer;
  }
  .day-title { font-weight: 700; }
  .day-summary {
    padding: 8px 12px;
    font-size: 0.82rem;
    color: var(--muted);
    border-top: 1px solid var(--line);
    white-space: pre-wrap;
  }
  .day-body.hidden { display: none; }
```

- [ ] **Step 4: Add turn source formatter and day section renderer**

Add before `renderRecord(r)`:

```javascript
  function formatTurnSource(source) {
    if (source === 'scripted') return '固定意图';
    if (source === 'pressure') return '压力续聊';
    if (source === 'greeting') return '每日问候';
    if (source === 'idle_gap') return '无交互';
    return source || '未知来源';
  }

  function showDaySection(sceneId, day, summary) {
    const body = document.getElementById(`body-${sceneId}`);
    const safeDay = String(day).replace(/[^a-zA-Z0-9_-]/g, '_');
    const id = `day-${sceneId}-${safeDay}`;
    let section = document.getElementById(id);
    if (!section) {
      section = document.createElement('div');
      section.className = 'day-section';
      section.id = id;
      section.innerHTML = `
        <div class="day-head" onclick="this.parentElement.querySelector('.day-body').classList.toggle('hidden')">
          <span class="day-title">Day ${escapeHtml(String(day))}</span>
          <span>${escapeHtml(summary || '')}</span>
        </div>
        <div class="day-body" id="${id}-body"></div>`;
      body.appendChild(section);
    }
    const summaryEl = section.querySelector('.day-head span:last-child');
    if (summaryEl && summary) summaryEl.textContent = summary;
    return document.getElementById(`${id}-body`);
  }
```

- [ ] **Step 5: Show turn source and day summary in records**

In `renderRecord(r)`, update the header label:

```javascript
    const sourceLabel = formatTurnSource(r.turn_source);
```

Change the header line to include source:

```javascript
        <div class="ep-day">Day ${r.day} · ${turnLabel} · ${actionLabel} · ${escapeHtml(sourceLabel)}</div>
```

Before returning from `renderRecord(r)`, add:

```javascript
    if (r.day_summary) {
      html += `<div class="day-summary">${escapeHtml(r.day_summary)}</div>`;
    }
```

- [ ] **Step 6: Append episode events into day sections**

In `handleEvent()`, replace the episode branch body with:

```javascript
      currentSceneId = data.scene_id || currentSceneId || 'unknown';
      showSceneCard(currentSceneId, data.scene_name || '进行中...');
      const dayBody = showDaySection(currentSceneId, data.day, data.day_summary || '');
      dayBody.innerHTML += renderRecord(data);
      dayBody.scrollIntoView({ behavior: 'smooth', block: 'end' });
```

In the complete branch fallback where records are rendered, replace:

```javascript
        data.records.forEach(r => { body.innerHTML += renderRecord(r); });
```

with:

```javascript
        data.records.forEach(r => {
          const dayBody = showDaySection(data.scene_id, r.day, r.day_summary || '');
          dayBody.innerHTML += renderRecord(r);
        });
```

- [ ] **Step 7: Run page tests**

Run:

```powershell
cd web
python -m pytest tests/test_relationship_v2_page.py -v
```

Expected: PASS.

- [ ] **Step 8: Commit day grouping**

Run:

```powershell
git add web/static/relationship-v2-test.html web/tests/test_relationship_v2_page.py
git commit -m "feat: group relationship pressure results by day"
```

---

### Task 7: Verification Sweep

**Files:**
- Modify only if verification reveals a defect in files changed by Tasks 1-6.
- Test: full relevant test set.

- [ ] **Step 1: Run relationship pressure test suite**

Run:

```powershell
cd web
python -m pytest tests/test_relationship_v2_api.py tests/test_user_simulator.py tests/test_scene_runner.py tests/test_relationship_v2_page.py -v
```

Expected: PASS.

- [ ] **Step 2: Run broader relationship regression tests**

Run:

```powershell
cd web
python -m pytest tests/test_relationship.py tests/test_rule_evaluator.py tests/test_quality_judge.py tests/test_relationship_v2_integration.py -v
```

Expected: PASS.

- [ ] **Step 3: Run one smoke stream without quality judge**

Run:

```powershell
cd web
@'
import json
from app import app

client = app.test_client()
response = client.post(
    "/api/v2/relationship-selfplay/run",
    json={
        "scene": "anxious_prospective",
        "seed": 1,
        "skip_judge": True,
        "mode": "mixed",
        "turns_per_day": 4,
        "max_days": 0,
    },
)
text = response.get_data(as_text=True)
print(response.status_code)
print(text[:1000])
assert response.status_code == 200
assert "event: episode" in text
assert '"turn_source": "scripted"' in text or '"turn_source":"scripted"' in text
assert '"turn_source": "pressure"' in text or '"turn_source":"pressure"' in text
'@ | python -
```

Expected: prints `200` and includes both scripted and pressure turn events.

- [ ] **Step 4: Inspect final git diff**

Run:

```powershell
git status --short
git diff --stat
```

Expected: only files from this plan are modified, plus any pre-existing unrelated dirty files still visible but not staged.

- [ ] **Step 5: Commit verification fixes if needed**

If Step 1, Step 2, or Step 3 required fixes, commit only those changed files:

```powershell
git add web/app.py web/user_simulator.py web/scene_runner.py web/static/relationship-v2-test.html web/tests/test_relationship_v2_api.py web/tests/test_user_simulator.py web/tests/test_scene_runner.py web/tests/test_relationship_v2_page.py
git commit -m "fix: stabilize relationship pressure mode"
```

If no fixes were required, do not create an empty commit.

---

## Completion Criteria

- `/api/v2/relationship-selfplay/run` accepts `mode` and `turns_per_day`.
- Invalid `mode` and invalid `turns_per_day` return HTTP 400 before streaming begins.
- `regression` mode preserves existing scripted episode behavior.
- `mixed` mode runs scripted turns first and pressure continuations until the per-day target is reached.
- `pressure` mode runs only pressure continuations for chat days.
- Every chat record includes `turn_source`, `turn_index`, `turn_count`, `day_summary`, `state`, `next_hook`, and `violations`.
- `/relationship-test` exposes mode and turns-per-day controls.
- `/relationship-test` groups results by scene and day.
- The targeted and broader relationship tests listed in Task 7 pass.
