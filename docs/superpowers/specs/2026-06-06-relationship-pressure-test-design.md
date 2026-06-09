# Relationship Test Pressure Mode Design

> **Archived:** This design is historical. `/relationship-test`, `/api/*/relationship-selfplay/*`, and the relationship-test CLI are currently disabled because the dual-LLM loop caused high cache misses and uncontrolled cost. Do not implement or run this plan for daily testing. Current Xiaoxin optimization should use `/test` with human semantic review.

Date: 2026-06-06

## Goal

Upgrade `/relationship-test` from a mostly scripted relationship-state replay into a mixed regression and pressure-test tool.

The current page is useful for checking whether `user_stage`, `recent_topic`, `next_hook`, greeting behavior, and rule probes move correctly across days. Its weakness is that each day usually contains only one or a few turns, so it is hard to expose failures that emerge during longer conversations: shallow memory, unnatural hook reuse, over-intimacy, repeated answers, boundary drift, or cross-day continuity that feels abrupt.

The new design keeps the current deterministic scene runner, but adds a pressure mode where each simulated day can contain many user-LLM and Xiaoxin-LLM turns, similar to `/test`.

## User Experience

`/relationship-test` should support three run modes:

1. `regression`
   Runs the scene as it does today. Each scene episode uses the configured `intent` and `followup_intents`. This mode stays stable and suitable for automated checks.

2. `pressure`
   Runs each active day as a longer free-form conversation. The scene provides the character, day, action, and daily goal. The user simulator keeps talking for the requested number of turns unless the user naturally ends the conversation.

3. `mixed`
   Runs configured intents first, then extends the same day with free-form pressure turns until the selected per-day turn target is reached. This is the recommended default because it keeps scenario coverage while creating enough conversational depth to reveal relationship problems.

The page should add these controls:

- Mode selector: `regression`, `mixed`, `pressure`.
- Turns per day: numeric or segmented options such as `3`, `8`, `12`, `16`.
- Maximum days, keeping the existing cap behavior.
- Seed, keeping the existing reproducibility behavior.
- Skip quality judge, keeping the existing control.

Results should be grouped by scene and then by day. Each day should be collapsible and show:

- All user and Xiaoxin messages for that day.
- Whether each turn came from a scripted intent or pressure continuation.
- The day's final `user_stage`, `recent_topic`, `next_hook`, `expression`, and `companion_action`.
- Rule violations for the day.
- A short day summary used as context for later pressure turns.
- The final scene-level verdict and quality judge panel.

## Architecture

The implementation should stay within the current v2 relationship-test architecture:

- Page: `web/static/relationship-v2-test.html`
- Route: `POST /api/v2/relationship-selfplay/run`
- Runner: `web/scene_runner.py`
- User simulator: `web/user_simulator.py`
- Rule checks: `web/rule_evaluator.py`
- Quality judge: `web/quality_judge.py`
- Scene data: `web/scenes/*.json`

Historical design note: no new web framework or separate route was planned, and `/relationship-test` was intended to remain the single entry point. This no longer applies because the entry point is now disabled.

## Data Flow

The run request should include:

```json
{
  "scene": "all",
  "seed": 123,
  "skip_judge": false,
  "mode": "mixed",
  "turns_per_day": 12,
  "max_days": null
}
```

The runner should interpret each scene day as follows:

- `greeting` episodes still call the greeting pipeline once.
- `chat` episodes create one or more chat turns.
- In `regression` mode, chat turns come only from `intent` and `followup_intents`.
- In `pressure` mode, chat turns come from a daily pressure goal.
- In `mixed` mode, scripted intents run first; pressure continuation fills the remaining turn budget.

Each generated chat turn should still go through Xiaoxin's real chat pipeline. That means relationship state is updated by the same code path used by production chat, not by a test-only shortcut.

## Scene Model

Existing scenes should continue to work without migration. If a scene does not define pressure-specific fields, the runner can derive a daily pressure goal from the episode intent and character card.

Optional new episode fields:

```json
{
  "pressure_goal": "Keep asking about whether Xiaoxin remembers yesterday's competition anxiety, then drift into a boundary-sensitive request.",
  "pressure_turns": 8,
  "end_when_user_farewell": true
}
```

Priority for turn count:

1. Episode-level `pressure_turns`
2. Request-level `turns_per_day`
3. Current scripted turn count

This keeps scene authors able to tune a specific day while allowing page-wide pressure settings.

## User Simulator

`user_simulator.py` should gain a continuation function for pressure turns. It should receive:

- Character card
- Daily pressure goal
- Current same-day transcript
- Prior-day summary
- Public relationship state
- Forbid patterns and probes
- Seed and turn index

The simulator should be instructed to behave like a real student, not like a test harness. It should be allowed to:

- Follow up on Xiaoxin's last reply.
- Repeat a concern naturally if the student is anxious.
- Drift topics when realistic.
- Ask boundary-sensitive questions when the scene goal calls for it.
- Say goodbye naturally.

It should avoid exposing test metadata such as "probe", "rule", "pressure mode", or "intent".

## Events And UI Rendering

The current SSE shape can remain, but each `episode` event should include enough metadata for grouped rendering:

```json
{
  "event": "episode",
  "data": {
    "scene_id": "anxious_prospective",
    "day": 2,
    "action": "chat",
    "turn_index": 5,
    "turn_count": 12,
    "turn_source": "pressure",
    "day_summary": "...",
    "state": {},
    "next_hook": {},
    "violations": []
  }
}
```

The page should group incoming records into day sections instead of appending one flat scene body. This makes long runs readable.

## Evaluation

Rule evaluation should continue to run per turn because boundary and state mistakes often happen in the middle of a long day.

Scene-level verdict can keep the current rule-plus-quality calculation. The quality judge should receive the full multi-day timeline, including day summaries. If the quality judge is skipped, rule failures still determine `FAIL`, and low-score warnings are omitted.

The first implementation does not need a separate per-day quality judge. Per-day rule violations and final state are enough for debugging.

## Error Handling

- Invalid `mode` returns HTTP 400 with a clear message.
- Invalid `turns_per_day` returns HTTP 400.
- If user simulation fails on one pressure turn, emit an `error` event for that scene and continue only if the runner already supports partial continuation safely. Otherwise complete the scene as `FAIL`.
- If Xiaoxin's chat call fails, preserve the current behavior of recording the API error as the reply and evaluating it as a failed turn.
- If a pressure turn produces an empty user message, use a conservative fallback follow-up once; if it remains empty, end that day.

## Testing

Tests should cover:

- `/api/v2/relationship-selfplay/run` accepts `mode` and `turns_per_day`.
- Invalid mode and invalid turn count return 400.
- `regression` mode preserves the current number of scripted turns.
- `mixed` mode adds pressure turns after scripted intents.
- `pressure` mode can run a day with multiple free-form turns.
- Streaming events include `day`, `turn_index`, `turn_count`, and `turn_source`.
- Page HTML includes controls for mode and turns per day.
- Existing relationship page route behavior remains unchanged.

## Non-Goals

- Do not replace `/test`.
- Do not create a new route.
- Do not make relationship memory permanent during test runs; pressure runs should continue using temporary data directories.
- Do not require every existing scene JSON file to be rewritten before the feature works.
- Do not add a second quality-judge pass per day in the first version.

## Historical Success Criteria

At the time, this design expected a reviewer to open `/relationship-test`, choose `mixed`, set `turns_per_day` to `12`, run a scene across several days, and inspect whether Xiaoxin. This is no longer a current success criterion; current review should use `/test`:

- Remembers and resumes relevant concerns naturally.
- Lets old topics fade when the user rejects them.
- Keeps boundaries after repeated pressure.
- Avoids becoming too intimate or clingy.
- Carries `next_hook` across days in a useful but restrained way.
- Produces enough conversation per day for real debugging.
