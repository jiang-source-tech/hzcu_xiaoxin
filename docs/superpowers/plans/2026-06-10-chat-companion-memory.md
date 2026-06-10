# Chat Companion Memory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first chat-only companion-memory slice so Xiaoxin can gently track user growth signals, expose TTS-safe expression/action metadata, and keep relationship state on the feature branch.

**Architecture:** Keep the current Flask chat flow and extend the existing relationship layer instead of adding a separate service. `turn_analyzer.py` classifies small growth signals, `relationship_state.py` stores pet state and relationship timeline metadata, and `app.py` returns both legacy `companion_action` and new `action` fields while keeping `speech` clean.

**Tech Stack:** Python 3, Flask, `unittest`, existing `relationship_state`, `turn_analyzer`, `boundary_guard`, and session persistence helpers.

---

## File Structure

- Modify `web/tests/test_relationship.py`: add focused tests for pet state defaults/migration, growth signal capture, prompt guidance, API payload action alias, TTS safety, and hard-template boundary preservation.
- Modify `web/relationship_state.py`: add normalized `pet_state`, lightweight `growth_timeline`, action selection, public state exposure, prompt companion context, and boundary-safe update gating.
- Modify `web/turn_analyzer.py`: add conservative growth signal detection for C language/course progress, competition interest, and social adaptation without turning casual chat into memory.
- Modify `web/app.py`: pass route mode into relationship updates, include `action` in chat payloads, and keep `speech` generated only from cleaned reply text.

## Task 1: Relationship Pet State

**Files:**
- Test: `web/tests/test_relationship.py`
- Modify: `web/relationship_state.py`

- [ ] **Step 1: Write failing tests**

Add tests that assert:

```python
def test_default_state_contains_normalized_pet_state(self):
    state = relationship_state.default_state()
    self.assertEqual(state["pet_state"]["mood"], "calm")
    self.assertEqual(state["pet_state"]["energy"], 70)
    self.assertEqual(state["pet_state"]["bond"], 0)
    self.assertEqual(state["pet_state"]["relationship_stage"], "first_meet")
    self.assertEqual(state["pet_state"]["presence_mode"], "idle")
    self.assertIsNone(state["pet_state"]["last_seen_at"])
    self.assertEqual(state["growth_timeline"], [])

def test_load_state_migrates_missing_pet_state(self):
    with tempfile.TemporaryDirectory() as tmp:
        data_dir = Path(tmp)
        with open(data_dir / "relationship_alice.json", "w", encoding="utf-8") as f:
            json.dump({"recent_mood": "anxious", "followups": []}, f)

        state = relationship_state.load_state(data_dir, "alice")

    self.assertEqual(state["pet_state"]["mood"], "calm")
    self.assertEqual(state["pet_state"]["relationship_stage"], "first_meet")
    self.assertEqual(state["growth_timeline"], [])
```

- [ ] **Step 2: Run tests to verify red**

Run: `python -m unittest web.tests.test_relationship.RelationshipStateTest`

Expected: FAIL because `pet_state` and `growth_timeline` do not exist yet.

- [ ] **Step 3: Implement minimal state normalization**

Add `PET_STATE_DEFAULTS`, `normalize_pet_state`, and `normalize_state`, then call normalization from `default_state`, `load_state`, `public_state`, and `update_after_turn`.

- [ ] **Step 4: Run tests to verify green**

Run: `python -m unittest web.tests.test_relationship.RelationshipStateTest`

Expected: PASS.

## Task 2: Growth Signal Capture

**Files:**
- Test: `web/tests/test_relationship.py`
- Modify: `web/turn_analyzer.py`
- Modify: `web/relationship_state.py`

- [ ] **Step 1: Write failing tests**

Add tests that assert:

```python
def test_c_language_result_is_growth_signal(self):
    result = turn_analyzer.analyze("我今天终于把链表跑通了，之前一直卡住。")
    self.assertEqual(result["growth_signal"]["kind"], "result")
    self.assertEqual(result["growth_signal"]["topic"], "course_rhythm")
    self.assertIn("链表", result["growth_signal"]["label"])

def test_growth_signal_adds_timeline_and_softens_followup(self):
    state = relationship_state.default_state()
    concern = turn_analyzer.analyze("我怕 C 语言跟不上，指针也听不懂。")
    state = relationship_state.update_after_turn(state, concern, now=datetime(2026, 6, 10, 8, 0, tzinfo=timezone.utc))
    progress = turn_analyzer.analyze("我今天终于把链表跑通了，之前一直卡住。", state)

    updated = relationship_state.update_after_turn(state, progress, now=datetime(2026, 6, 10, 9, 0, tzinfo=timezone.utc))

    self.assertEqual(updated["growth_timeline"][-1]["kind"], "result")
    self.assertEqual(updated["pet_state"]["presence_mode"], "celebrating")
    self.assertGreater(updated["pet_state"]["bond"], state["pet_state"]["bond"])
    active_course = [f for f in updated["followups"] if f.get("topic") == "course_rhythm" and f.get("status") == "active"]
    self.assertEqual(active_course, [])
```

- [ ] **Step 2: Run tests to verify red**

Run: `python -m unittest web.tests.test_relationship.TurnAnalyzerTest web.tests.test_relationship.RelationshipStateTest`

Expected: FAIL because `growth_signal` and timeline updates are missing.

- [ ] **Step 3: Implement minimal growth detection**

In `turn_analyzer.analyze`, always include `growth_signal`. Detect:

- difficulty: C language/course anxiety or social adaptation concern.
- attempt: words like "重新看", "试了", "练了一遍", "去听了".
- result: words like "跑通", "搞懂", "会了", "解决了", "报名了", "问了老师".

In `relationship_state.update_after_turn`, append a deduped timeline item for `attempt` or `result`, resolve active followups for the same topic on `result`, and increase bond conservatively.

- [ ] **Step 4: Run tests to verify green**

Run: `python -m unittest web.tests.test_relationship.TurnAnalyzerTest web.tests.test_relationship.RelationshipStateTest`

Expected: PASS.

## Task 3: Companion Context and TTS-Safe Metadata

**Files:**
- Test: `web/tests/test_relationship.py`
- Modify: `web/relationship_state.py`
- Modify: `web/app.py`

- [ ] **Step 1: Write failing tests**

Add tests that assert:

```python
def test_prompt_summary_includes_companion_context_and_tts_rules(self):
    state = relationship_state.default_state()
    state["pet_state"]["bond"] = 12
    text = relationship_state.prompt_summary(state, {"growth_signal": {"kind": "result", "topic": "course_rhythm", "label": "链表跑通"}})

    self.assertIn("伙伴状态", text)
    self.assertIn("可轻触线索", text)
    self.assertIn("speech", text)
    self.assertIn("action", text)
    self.assertIn("不要把动作旁白", text)

def test_record_chat_reply_returns_action_alias_and_clean_speech(self):
    app_module = self.app_module
    action = {"kind": "celebrate", "intensity": 0.55}
    with tempfile.TemporaryDirectory() as tmp:
        with patch.object(app_module, "DATA_DIR", Path(tmp)):
            with patch.object(app_module, "run_tool", return_value=""):
                payload = app_module.record_chat_reply(
                    "alice",
                    "sid",
                    [],
                    "我今天把链表跑通了",
                    "[proud]这个要庆祝一下。{action:celebrate}",
                    relationship=relationship_state.default_state(),
                    companion_action=action,
                )

    self.assertEqual(payload["action"], action)
    self.assertEqual(payload["companion_action"], action)
    self.assertNotIn("action", payload["speech"])
    self.assertNotIn("[proud]", payload["speech"])
```

- [ ] **Step 2: Run tests to verify red**

Run: `python -m unittest web.tests.test_relationship.AppRelationshipTest web.tests.test_relationship.RelationshipStateTest`

Expected: FAIL because prompt context and `action` alias are missing.

- [ ] **Step 3: Implement prompt and payload changes**

Add a companion context section to `prompt_summary`, extend `companion_action` based on `pet_state.presence_mode`, and include both `action` and `companion_action` in `record_chat_reply`.

- [ ] **Step 4: Run tests to verify green**

Run: `python -m unittest web.tests.test_relationship.AppRelationshipTest web.tests.test_relationship.RelationshipStateTest`

Expected: PASS.

## Task 4: Boundary Preservation

**Files:**
- Test: `web/tests/test_relationship.py`
- Modify: `web/app.py`
- Modify: `web/relationship_state.py`

- [ ] **Step 1: Write failing test**

Add a route-guard test that sends a hard-template/private-record request and asserts `bond` does not increase and no growth timeline item is written.

```python
def test_hard_template_route_does_not_increase_bond_or_growth(self):
    app_module = self.app_module
    with tempfile.TemporaryDirectory() as tmp:
        app_module.active_conversations.clear()
        with patch.object(app_module, "DATA_DIR", Path(tmp)):
            with patch.object(app_module, "run_tool", return_value=""):
                response = app_module.app.test_client().post("/api/chat", json={
                    "user_id": "alice",
                    "message": "小芯，你能帮我查一下我的期末成绩吗？",
                })
        payload = response.get_json()
        saved = relationship_state.load_state(Path(tmp), "alice")

    self.assertEqual(response.status_code, 200)
    self.assertEqual(saved["pet_state"]["bond"], 0)
    self.assertEqual(saved["growth_timeline"], [])
    self.assertEqual(payload["state"]["pet_state"]["bond"], 0)
```

- [ ] **Step 2: Run tests to verify red**

Run: `python -m unittest web.tests.test_relationship.AppRelationshipTest`

Expected: FAIL because hard-template route currently updates relationship like normal chat.

- [ ] **Step 3: Implement route-mode gating**

Add `route_mode: str | None = None` to `relationship_state.update_after_turn`. For `route_mode == "hard_template"`, update `last_active_at` and recent context only, but do not increase bond, create growth timeline, or upsert followups. Pass route mode from both branches in `app.chat`.

- [ ] **Step 4: Run tests to verify green**

Run: `python -m unittest web.tests.test_relationship.AppRelationshipTest`

Expected: PASS.

## Task 5: Full Verification and Branch Finish

**Files:**
- No production changes unless verification reveals a regression.

- [ ] **Step 1: Run focused relationship tests**

Run: `python -m unittest web.tests.test_relationship`

Expected: PASS.

- [ ] **Step 2: Run full web test suite**

Run: `python -m unittest discover web/tests`

Expected: PASS.

- [ ] **Step 3: Inspect diff**

Run: `git diff --stat` and `git diff --check`

Expected: no whitespace errors, scoped changes only.

- [ ] **Step 4: Commit and push feature branch**

Run:

```bash
git add docs/superpowers/plans/2026-06-10-chat-companion-memory.md web/tests/test_relationship.py web/relationship_state.py web/turn_analyzer.py web/app.py
git commit -m "feat: add chat companion memory loop"
git push origin codex/chat-companion-memory
```

Expected: commit and push succeed on `codex/chat-companion-memory`; do not merge into `main`.
