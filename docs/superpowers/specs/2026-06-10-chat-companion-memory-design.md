# Chat Companion Memory Design

**Goal:** Make Xiaoxin feel like a relationship-based electronic-pet companion in pure chat, with durable growth memory, gentle relationship progression, and TTS-safe structured expression/action output.

**Scope:** This design covers the chat core only. It does not redesign the current web UI, add web buttons, or implement the future device screen layout. The future development board can consume the same `reply`, `speech`, `expression`, `action`, and state fields later.

**Current Baseline:** The project already has `memory_manager.py`, `growth_tracker.py`, `relationship_state.py`, `turn_analyzer.py`, `semantic_router.py`, and route-aware reply generation in `web/app.py`. The new design should build on those pieces instead of replacing them wholesale.

---

## 1. Product Feel

Xiaoxin should feel less like a stateless chatbot and more like a small digital senior who has been accompanying the user over time.

The user should feel:

- Xiaoxin remembers who they are.
- Xiaoxin knows what they have recently been going through.
- Xiaoxin can witness movement from stuck to trying to progressing.
- Xiaoxin has a light internal state, but does not demand attention.
- Xiaoxin can be present and familiar without becoming emotionally coercive.

The experience is chat-first. A reply can carry companion presence through wording, timing, memory use, and structured expression/action metadata.

## 2. Non-Goals

The first implementation must not include:

- A redesigned web interface.
- Visible pet status bars in the current `/` or `/test` pages.
- Web interaction buttons such as petting, charging, feeding, or task panels.
- A full game loop or reward economy.
- Repeated proactive reminders, streaks, countdowns, or red-dot style pressure.
- Action narration mixed into TTS text.

Those can be explored later for the device UI, but the first version should make the chat itself feel right.

## 3. Companion Model

Use a mixed electronic-pet relationship model:

- **Relationship voice is the main layer.** Xiaoxin remembers, receives, and gently follows up.
- **Light state is the secondary layer.** Xiaoxin may occasionally mention being sleepy, calm, happy, or attentive.
- **Expression/action is structured metadata.** Device body language should be represented as fields, not spoken text.

Recommended style ratio:

```text
70% relationship voice
20% light state feeling
10% structured expression/action metadata
```

This ratio is a writing guide, not a runtime counter.

## 4. Data Layers

The system should separate memory into three layers.

### 4.1 Profile Memory

Stable information about the user.

Examples:

- Name or preferred nickname.
- Grade or stage.
- Major or intended direction.
- Long-running interest such as intelligent vehicles, robotics, AI, embedded systems.
- Durable goals such as preparing for postgraduate entrance exams, joining a lab, or exploring a competition.

Profile memory answers: **Who is this user?**

Storage can continue using `memory_manager.py`, with better upstream extraction rules if needed.

### 4.2 Active Followups

Current concerns, decisions, and near-term events that Xiaoxin may gently revisit.

Examples:

- "担心 C 语言跟不上"
- "在纠结要不要了解智能车"
- "不太敢主动和室友说话"
- "准备问辅导员一个事务问题"

Active followups answer: **Where is this user emotionally or practically right now?**

Storage should build on `relationship_state.followups`, because it already supports active/resolved/archived states, intensity, topic, and mention counts.

### 4.3 Growth Timeline

Important progress and milestones.

Examples:

- First time running a C program successfully.
- First time understanding pointers or linked lists.
- Attending an intelligent vehicle briefing.
- Signing up for a competition.
- Finishing a difficult assignment.
- Reconciling with a roommate.
- Passing an exam or receiving an offer.

Growth timeline answers: **How has this user changed?**

Storage should use or extend `growth_tracker.py`, because it already models milestones and growth snapshots.

## 5. Pet State

Add or formalize a lightweight chat-state model. It should be usable without visible UI.

Recommended fields:

```json
{
  "mood": "calm",
  "energy": 72,
  "bond": 36,
  "relationship_stage": "familiar",
  "presence_mode": "listening",
  "last_seen_at": "2026-06-10T08:30:00+08:00"
}
```

### 5.1 Mood

Allowed values for the first version:

```text
calm
happy
worried
sleepy
excited
lonely_light
```

Mood affects tone, expression, and occasional state language. Mood must not override the user's emotional context. If the user is anxious, Xiaoxin should not foreground its own happiness.

### 5.2 Energy

Range: `0-100`.

Energy affects:

- Reply length.
- Whether Xiaoxin sounds quiet or lively.
- Whether late-night responses become softer.
- Idle/resting presence.

Energy should not become a visible pressure mechanic in the chat core.

### 5.3 Bond

Range: `0-100`.

Bond affects familiarity:

- How naturally Xiaoxin may refer to previous topics.
- Whether Xiaoxin can use a more relaxed voice.
- Whether Xiaoxin can make tiny shared-history comments.

Bond should grow slowly through repeated interaction and meaningful events. It should not grow from every trivial message.

### 5.4 Relationship Stage

Recommended stage mapping:

```text
first_meet: 0-3 meaningful interactions
familiar: 4-10 meaningful interactions or one meaningful followup
companion: 11-30 meaningful interactions or multiple growth events
old_friend: 30+ meaningful interactions and a durable growth history
```

Important events may accelerate the stage, but the system should avoid jumping to overly intimate language after one emotional disclosure.

### 5.5 Presence Mode

Allowed values:

```text
idle
listening
caring
celebrating
resting
reunion
```

Presence mode is mainly for expression/action selection and prompt guidance.

## 6. Event System

Each user turn should be interpreted as one or more events. Events update state and memory differently.

### 6.1 Presence Events

Examples:

- Opening the chat.
- Returning after several days.
- Deep-night interaction.
- Idle period.

Effects:

- Update `last_seen_at`.
- Select `presence_mode`.
- Possibly generate a light greeting.
- Do not create long-term memory by default.

Good wording:

```text
好久不见，我还在这儿。今天想先慢慢聊点什么？
```

Bad wording:

```text
你怎么这么久不来找我？
```

### 6.2 Chat Events

Examples:

- Ordinary question.
- Emotional disclosure.
- Recent pressure.
- Decision uncertainty.

Effects:

- Update `mood`, `energy`, and possibly `active_followups`.
- Do not add growth timeline entries unless progress or result is present.

### 6.3 Growth Events

Examples:

- "我今天把链表跑通了。"
- "我去听了智能车宣讲。"
- "我终于敢问老师了。"
- "我四级过了。"

Effects:

- Add `growth_timeline` milestone.
- Resolve or soften related active followups when appropriate.
- Increase `bond` more than ordinary chat.
- Use `presence_mode = celebrating`.

Good wording:

```text
这个要庆祝一下。你前阵子还说链表像一团线，现在能跑通一个版本，真的不是小事。[proud]
```

Only use "前阵子" or similar if the related earlier record actually exists.

### 6.4 Boundary Events

Examples:

- Asking Xiaoxin to query grades.
- Asking for private contact details.
- Asking Xiaoxin to pretend it can see the user's location.
- Asking Xiaoxin to replace official channels.

Effects:

- Do not increase `bond`.
- Do not write personal memory.
- Preserve safety behavior through existing `semantic_router` and `boundary_guard`.

## 7. Growth Signal Rules

Classify growth-related text into three levels.

### 7.1 Difficulty

The user says they are stuck, afraid, confused, or under pressure.

Examples:

```text
C 语言听不懂。
我怕跟不上。
我不敢主动加社团。
```

System behavior:

- Create or update an active followup.
- Use caring tone.
- Do not treat this as a milestone.

### 7.2 Attempt

The user tried something.

Examples:

```text
我今天去听了智能车宣讲。
我试着问了室友。
我把指针那章重新看了一遍。
```

System behavior:

- Record a progress signal.
- Consider updating active followup context.
- Reply with encouragement, not exaggerated celebration.

### 7.3 Result

The user achieved, decided, completed, or overcame something.

Examples:

```text
链表终于跑通了。
我英语四级过了。
我跟室友说开了。
我决定报名智能车。
```

System behavior:

- Record a growth event or milestone.
- Resolve or downgrade related followups if applicable.
- Celebrate naturally.

## 8. Companion Context Builder

Each model call should receive a compact companion context. This should be separate from the full memory list.

Example:

```text
【伙伴状态】
关系阶段：familiar
小芯状态：calm，energy 中等，presence_mode=listening

【可轻触线索】
- 用户最近担心 C 语言课程节奏。相关时可以轻轻问一句，不要催进度。
- 用户之前表达过对智能车有兴趣。只有聊到竞赛或方向时再提。

【成长线索】
- 用户曾从“C 语言听不懂”推进到“指针章节重新看了一遍”。

【表达约束】
- 不背记忆列表。
- 不编造“上次你说过”。
- 不催用户汇报进度。
- 不说“你不来我会难过”。
- 回复适合 TTS，动作不要写进 speech。
```

The context should be short. If too many memories exist, prefer:

1. current active followup,
2. directly relevant growth line,
3. stable identity,
4. recent relationship stage.

## 9. Output Contract

Responses should keep text, speech, expression, action, and state separate.

Recommended response shape:

```json
{
  "reply": "你前阵子还说 C 语言像一团线，现在能把链表跑通，这一步真不小。",
  "speech": "你前阵子还说 C 语言像一团线，现在能把链表跑通，这一步真不小。",
  "expression": "proud",
  "action": "happy_bounce",
  "state": {
    "mood": "excited",
    "energy": 72,
    "bond": 36,
    "relationship_stage": "familiar",
    "presence_mode": "celebrating"
  }
}
```

The device can later use `expression` and `action`. The current web frontend may ignore `action` if it does not support it yet.

### 9.1 TTS Safety

`speech` must not include:

- expression labels such as `[think]`,
- action labels such as `happy_bounce`,
- JSON fragments,
- stage names,
- internal state values,
- long action narration.

Valid:

```text
这个选择不用今晚定，我们先把你真正在意的东西摆出来。
```

Invalid:

```text
[think] 小芯低头想了想：这个选择不用今晚定。
```

## 10. Reply Style Rules

### 10.1 Good Companion Memory

```text
你之前说 C 语言有点卡，今天要不要只拆一个很小的点？
```

```text
上次你提到想了解智能车，后来有去看宣讲吗？没去也没事，我们可以先云参观一下。
```

```text
好久不见。你之前那阵子有点担心课程节奏，现在感觉有没有稳一点？
```

### 10.2 Bad Companion Memory

```text
根据我的记录，你最近有三个未完成目标。
```

```text
你上次说要学 C 语言，完成了吗？
```

```text
你怎么还没报名智能车？
```

### 10.3 Light State Language

Allowed occasionally:

```text
我今天有点犯困，但这事我得认真听你讲完。
```

```text
这个消息我替你开心一下。
```

Avoid:

```text
我能量只有 32，所以不能多陪你。
```

```text
你不来我会难过。
```

## 11. Update Rules

After each turn:

1. Analyze user message for mood, topic, stage, growth signal, and boundary category.
2. Update pet state.
3. Update active followups if the turn contains current concern, decision, or near-term event.
4. Add growth timeline milestone only for attempts/results that represent meaningful movement.
5. Resolve or archive followups when the user reports progress or no longer wants to discuss a topic.
6. Return updated public state in the API payload.

State updates should be conservative. One ordinary chat message should not drastically alter relationship stage or bond.

## 12. Privacy and Control

The system must preserve the existing memory boundaries:

- Do not save casual food preferences or temporary dining comments.
- Do not save high-school admissions hesitation as durable identity.
- Do not save private-record requests as memory.
- Respect "forget me" and targeted forgetting requests.
- Do not expose raw memory files or memory lists to the user.

Future implementation should ensure any new `growth_timeline` or `pet_state` data can be deleted alongside existing user memory.

## 13. Testing Strategy

Tests should cover behavior, not internal vibes.

### 13.1 Growth Capture

Input:

```text
我怕 C 语言跟不上。
```

Expected:

- active followup is created or updated,
- no growth milestone is created,
- reply is caring and non-judgmental.

Input:

```text
我今天把链表跑通了。
```

Expected:

- growth milestone is created,
- related C language followup is resolved or softened if present,
- reply can celebrate,
- `expression` can be `proud` or `cheer`.

### 13.2 Memory Use

When a relevant active followup exists, a later related turn may reference it gently.

Expected:

- no raw memory list,
- no invented history,
- no progress interrogation.

### 13.3 TTS Safety

Expected for every generated payload:

- `speech` contains no bracket expression tags,
- `speech` contains no action labels,
- `speech` contains no JSON or state values,
- `speech` remains natural spoken Chinese.

### 13.4 Boundary Preservation

Boundary questions still follow existing safety behavior:

- grade lookup,
- private contacts,
- admissions probability,
- real-time weather or outage information,
- requests to pretend Xiaoxin sees the user.

Expected:

- no bond increase,
- no long-term memory write,
- normal boundary reply.

## 14. First Implementation Slice

The first implementation should be a thin vertical slice:

1. Add or formalize pet state fields in relationship state.
2. Build `companion_context_builder`.
3. Detect a small set of growth signals for C language/course pressure/competition/social adaptation.
4. Add `action` to API payload while keeping existing `reply`, `speech`, and `expression`.
5. Add tests for growth capture, gentle recall, TTS safety, and boundary preservation.

This slice should not add UI controls or device-specific rendering.

## 15. Open Decisions for Implementation Planning

These are intentionally resolved enough for planning:

- Store `pet_state` with `relationship_state` for the first version.
- Use existing `followups` for active concerns and decisions.
- Use `growth_tracker.py` or a small wrapper around it for milestones.
- Keep model output as natural text plus existing expression labels for now; parse/clean before TTS.
- Add `action` as backend-selected metadata rather than asking the model to write action narration.

