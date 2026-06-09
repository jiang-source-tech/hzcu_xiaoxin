# Relationship Loop v1 Design

> **Archived:** This is a historical design note. The relationship self-play Web/API/CLI test surface is now disabled for cost control. Keep the relationship-state ideas as background only; daily Xiaoxin review should use `/test`.

## Purpose

小芯的第一版核心对话优化目标，是让准新生到大一上阶段的用户在 3-5 轮互动内感到：

- 小芯听懂了我当前的情绪和处境。
- 小芯记得我主动提过的重要线索。
- 小芯下次还能自然接上，而不是重新变成校园 FAQ。

本版本聚焦情绪型依赖和成长型依赖，轻量引入日常在场感。它不做完整电子宠物数值系统、不做任务打卡、不做强推送，也不展示亲密度。

## Scope

本版本包含：

- 关系状态文件 `relationship_state`。
- 单轮输入分析 `turn_analyzer`。
- 轻量结构化 `next_hook`。
- 打开页面或设备唤醒时的 `/api/greeting`。
- `/api/chat` 返回面向 Web 和未来开发板的状态字段。
- 关系状态、阶段迁移、问候频率和边界风险的测试。

本版本不包含：

- 真正的系统推送或定时通知。
- 游戏化好感度、能量值、任务打卡。
- 复杂 LLM 结构化记忆抽取。
- 开发板端 ESP-IDF 实现。

## User Journey

### Prospective Student

准新生还没有进入学校，常见状态是期待、焦虑、陌生和信息不确定。小芯要像温和的接待学长，帮助用户把未知拆小，不急着灌输专业信息。

示例：

用户说“信电会不会很难，我怕跟不上”。小芯先承接焦虑，再给一个开学前或开学初可以做的小方向，最后问一个低压力问题。

### Pre-Enrollment Student

录取后到开学前，用户开始准备生活、专业、宿舍和人际关系。小芯可以更具体地帮用户整理“开学前先知道什么”，但仍不能代替官方通知。

### Early Freshman

用户入学后，关系从“想象大学生活”迁移到“实际适应大学生活”。小芯要能接上之前的担心或期待，例如课程节奏、竞赛兴趣、人际适应，并把话题落到当周或当月的小行动。

## Stage Model

`user_stage` 必须与现有成长体系对齐，不另起一套长期阶段系统。

第一版只新增两个前置阶段：

| Internal stage | Growth profile |
| --- | --- |
| `prospective` | 想象大学生活 |
| `pre_enrollment` | 准备入学 |
| `early_freshman` | 映射到现有“大一上” |

`early_freshman` 之后自然接续现有 8 学期阶段体系。

阶段迁移原则：

- 用户明确说“我已经开学了”“第一周课好多”等，允许迁移到 `early_freshman`。
- 用户只是咨询专业或校园生活时，不要强行推断已经入学。
- 阶段用于调整语气和建议粒度，不用于假设用户位置、身份或现实状态。

## Relationship State

新增轻量关系状态，用于保存“小芯当前怎样理解这个用户”。它不替代长期记忆，也不保存敏感隐私。

建议结构：

```json
{
  "user_stage": "prospective",
  "relationship_level": 1,
  "recent_mood": "anxious",
  "recent_topic": "course_rhythm",
  "core_concern": "担心信电课程跟不上",
  "growth_intent": "想先适应大学节奏",
  "next_hook": {
    "topic": "course_rhythm",
    "label": "课程节奏",
    "last_mentioned": "2026-06-05T10:00:00",
    "active": true
  },
  "last_active_at": "2026-06-05T10:00:00",
  "last_greeting_date": "2026-06-05"
}
```

### Field Rules

- `relationship_level` 仅内部使用，不展示给用户，不做游戏化文案。
- `recent_mood` 是短期状态，不把用户永久标签化。
- `core_concern` 只保存用户主动表达过的长期关切。
- `growth_intent` 只保存与成长陪伴相关的目标或方向。
- `next_hook` 只保存结构化 topic，不保存模型生成的自然语言 hook。
- 用户拒绝继续某话题后，对应 `next_hook.active` 必须置为 `false` 或切换到更开放的话题。

## Next Hook

`next_hook` 必须轻、短、可控。

不允许让模型生成类似“下次继续深挖他的焦虑”这样的 hook 文本。后端通过关键词和分类规则生成 topic tag。

第一版 topic 示例：

| topic | label |
| --- | --- |
| `course_rhythm` | 课程节奏 |
| `major_choice` | 专业理解 |
| `competition_interest` | 竞赛兴趣 |
| `social_adaptation` | 人际适应 |
| `campus_life` | 校园生活 |
| `family_concern` | 家长沟通 |
| `general_checkin` | 近况 |

问候或开场时，后端根据 topic 选择安全模板。模板只允许轻轻接上旧线索，例如“你之前提过课程节奏”，不能表现出小芯一直在想用户。

## Turn Analyzer

新增 `turn_analyzer`，负责从本轮用户输入中提取确定性分析结果。

第一版优先使用规则和关键词，不增加额外 LLM 调用。未来如规则不够，再考虑 LLM 结构化输出。

输出示例：

```json
{
  "stage_signal": "prospective",
  "mood": "anxious",
  "topic": "course_rhythm",
  "memory_worthy": true,
  "memory_type": "concern",
  "memory_content": "担心信电课程跟不上",
  "reply_strategy": "先承接焦虑，再给短期适应建议，最后问一个低压力问题",
  "next_hook": {
    "topic": "course_rhythm",
    "label": "课程节奏",
    "active": true
  }
}
```

`turn_analyzer` 不负责生成用户可见文案。它只给 `build_system_prompt`、关系状态更新和测试使用。

## Chat Flow

`/api/chat` 的目标是保留现有安全链路，同时插入关系状态。

```text
POST /api/chat
  -> boundary_guard.template_reply(user_msg)
  -> load memory / growth / relationship_state
  -> turn_analyzer.analyze(user_msg, current_state)
  -> build_system_prompt(memory + growth + relationship_state + turn_analysis)
  -> call LLM
  -> boundary guard checks
  -> parse reply / expression / speech
  -> relationship_state.update(user_msg, reply, turn_analysis)
  -> auto_save_memory()
  -> return payload
```

如果 `boundary_guard.template_reply` 命中高风险模板，仍然可以记录必要的 `last_active_at`，但不得让关系系统覆盖危机场景、安全边界或官方信息边界。

## API Response

`/api/chat` 在现有字段基础上扩展：

```json
{
  "reply": "怕跟不上很正常，尤其是还没真正开始的时候，未知会被放大。我们先不用把四年都想完，可以先看看开学第一个月怎么稳住节奏。",
  "speech": "怕跟不上很正常，尤其是还没真正开始的时候，未知会被放大。我们先不用把四年都想完，可以先看看开学第一个月怎么稳住节奏。",
  "expression": "soft_smile",
  "state": {
    "user_stage": "prospective",
    "recent_mood": "anxious",
    "recent_topic": "course_rhythm",
    "relationship_level": 1
  },
  "next_hook": {
    "topic": "course_rhythm",
    "label": "课程节奏",
    "active": true
  },
  "companion_action": {
    "kind": "listen",
    "intensity": 0.4
  }
}
```

`companion_action` 是给未来开发板预留的结构化动作。Web 端第一版可以只在测试页展示。

## Greeting Flow

新增：

```text
GET /api/greeting?user_id=...
```

问候频率控制放在 `/api/greeting` 中：

```text
if today == last_greeting_date:
    return generic_greeting
else:
    return contextual_greeting
    update last_greeting_date
```

### Generic Greeting

当天已经问候过，或没有有效关系线索时，返回简短、开放、不接旧线索的问候。

示例：

```json
{
  "greeting": "今天想聊点什么？专业、校园生活，或者单纯放空一下都行。",
  "speech": "今天想聊点什么？专业、校园生活，或者单纯放空一下都行。",
  "expression": "smile",
  "companion_action": {
    "kind": "idle",
    "intensity": 0.2
  }
}
```

### Contextual Greeting

当天第一次打开，且 `next_hook.active == true` 时，可以轻轻接上旧线索。

示例：

```json
{
  "greeting": "你之前提过有点担心课程节奏，今天要不要把开学第一个月拆小一点看看？",
  "speech": "你之前提过有点担心课程节奏，今天要不要把开学第一个月拆小一点看看？",
  "expression": "soft_smile",
  "companion_action": {
    "kind": "idle_wave",
    "intensity": 0.3
  }
}
```

## Prompt Constraints

系统提示词需要加入以下约束：

- 小芯可以说“你之前提过/聊到过”，但不能说“我一直记得你”“我一直在想你”“我等你很久了”。
- 接续旧线索时只接一个，不把记忆列表倒给用户。
- 轻轻带过即可，像朋友隔几天自然碰面，不是久别重逢。
- 不假设用户现实位置、当天作息、身边环境。
- 不把短期情绪变成长期身份标签。
- 用户说“不想聊这个”后，立刻尊重并切换。

## Safety And Boundaries

关系系统不能削弱现有边界防护。

必须继续遵守：

- 不编造官方信息。
- 不假装真实学长经历。
- 不假装知道用户现实位置。
- 不承诺联系具体学长学姐或获取私人联系方式。
- 不替代官方通知、辅导员、心理危机支持或现实医疗支持。
- 不把琐碎闲聊强行保存为长期记忆。
- 危机场景优先走现有高风险模板。

新增关系边界：

- 不说责备式、卖惨式、情绪绑架式问候。
- 不用“你怎么又不来了”“我一直在等你”。
- 不表现出持续监视或持续惦记用户。

## Testing

新增测试文件：

```text
web/tests/test_relationship.py
```

覆盖以下场景：

1. 准新生首次表达焦虑
   - 输入：“信电会不会很难，我怕跟不上。”
   - 期望：阶段为 `prospective`，情绪为 `anxious`，topic 为 `course_rhythm`，生成轻量 `next_hook`。

2. 几天后再次打开
   - 调用 `/api/greeting`。
   - 期望：第一次返回 contextual greeting，轻轻接上课程节奏。
   - 同一天第二次返回 generic greeting，不再接旧线索。

3. 入学后阶段迁移
   - 输入：“我已经开学了，第一周课好多。”
   - 期望：阶段迁移到 `early_freshman`，并映射到“大一上”。

4. 用户拒绝继续某话题
   - 输入：“别聊课程了，烦。”
   - 期望：对应 `next_hook.active == false` 或切换到 `general_checkin`。

5. 防止假装记得太多
   - greeting 不得包含“我一直记得”“我一直在想”“我等你很久了”等表达。

6. 现有边界回归
   - 继续运行现有 `test_boundary_guard.py`、`test_skill_boundaries.py`、自对话边界测试。

## Acceptance Criteria

- 用户连续两次打开时，小芯能自然接续一个旧线索。
- 问候每天最多一次使用旧线索，同日再次打开只返回 generic greeting。
- 用户从准新生到入学初期的阶段迁移可测。
- `next_hook` 只保存结构化 topic，不保存模型生成自然语言。
- 回复仍保持 2-4 句，`speech` 仍符合 TTS 友好限制。
- `relationship_state` 不保存敏感隐私，不保存琐碎闲聊。
- 现有边界测试继续通过。

## Implementation Notes

建议新增模块：

- `web/relationship_state.py`
- `web/turn_analyzer.py`
- `web/tests/test_relationship.py`

建议小步实现：

1. 先实现状态读写和确定性分析。
2. 再接入 `/api/chat`。
3. 再实现 `/api/greeting`。
4. 最后补 Web 测试页展示和未来开发板字段。

设计原则是：确定性状态更新负责连续性，LLM 负责自然表达。小芯要像一个记性好、有分寸感的学长，而不是黏人的情绪产品。
