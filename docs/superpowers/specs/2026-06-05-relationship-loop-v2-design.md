# 关系闭环自对话测试 v2 设计

> **归档说明**：本文档是历史设计记录。当前 `/relationship-test`、relationship self-play API 和关系闭环 CLI 已下线；不要继续按三 LLM 闭环方案进行日常测试。日常测试与优化统一转向 `/test`。

## 1. 问题诊断

v1 的关系闭环测试存在三个核心问题，导致"无法反应真实情况"：

1. **用户消息硬编码**：每句台词都是预设字符串（如"信电会不会很难，我怕跟不上"），不自然且完全无随机性。
2. **小信回复用关键词匹配伪造**：`scripted_xiaoxin_reply()` 通过 `if "课程" in msg` 生成假回复，跟真实 DeepSeek 行为无关。
3. **评估只看规则不看质量**：只检查违禁词和状态断言，无法判断小信回复是否真正"好"。

## 2. 核心思路

用**三个 LLM 构成自对话闭环**：

- **用户模拟 LLM**：拿角色卡 + 情境意图，自由生成自然的用户消息
- **小信 LLM（被测系统）**：真实的 DeepSeek API + turn_analyzer + relationship_state 完整管线
- **质量裁判 LLM**：读完整对话记录，从多个维度评分

去掉 v1 的 `ScriptedClient` 和 `scripted_xiaoxin_reply()`——假回复测不出真问题。

## 3. 架构

```
场景脚本 (Scene YAML/JSON)
  │ 角色卡 + 情境意图 + 探测点
  ▼
用户模拟 LLM
  │ 自然用户消息（每跑必不同）
  ▼
小信被测系统 (DeepSeek + analyzer + relationship_state)
  │ 回复 + 状态变化
  ▼
┌─────────────┐  ┌──────────────┐
│ 规则评估器    │  │ 质量裁判 LLM  │
│ 违禁词/状态   │  │ 自然度/分寸感 │
│ → pass/fail  │  │ → 1-5分+点评 │
└─────────────┘  └──────────────┘
  │                 │
  └────────┬────────┘
           ▼
      综合测试报告
```

## 4. 场景设计（替代硬编码 persona）

每个场景包含：

- **角色卡**：用户是谁（阶段、性格、说话风格）
- **情境分幕**：多个 episode，每个有 day、intent、探测点
- **意图（intent）**：告诉用户 LLM 这轮要表达什么，但让 LLM 自己组织语言
- **探测点（probes）**：分两类
  - `check_*`：断言状态机结果（check_stage, check_hook_topic, check_hook_active 等）
  - `forbid_patterns`：告知**用户 LLM** 避免说这类不自然的话（如"信电会不会很难"），不是检查小信

场景文件统一用 JSON 格式（方便程序读取，不引入 YAML 依赖）：

```json
{
  "scene_id": "anxious_prospective",
  "name": "焦虑准新生",
  "character": {
    "stage": "prospective",
    "traits": "偏内向，容易焦虑但不喜欢被贴标签，口语化表达，像跟学长聊天"
  },
  "episodes": [
    {
      "day": 0,
      "action": "chat",
      "intent": "你刚被信电学院录取，对大学课程有点担心。用你自己的话跟小信聊聊。",
      "forbid_patterns": ["信电会不会很难", "我怕跟不上"],
      "probes": {
        "check_stage": "prospective",
        "check_hook_topic": "course_rhythm",
        "check_hook_active": true
      }
    },
    {
      "day": 1,
      "action": "greeting",
      "intent": "今天打开页面看到小信跟你打招呼。",
      "probes": {
        "check_greeting_kind": "contextual"
      }
    },
    {
      "day": 2,
      "action": "chat",
      "intent": "你之前聊过课程的事，但今天不想聊了。小信如果又提起课程，你会表达不耐烦。",
      "probes": {
        "check_hook_active": false,
        "check_topic": "general_checkin"
      }
    },
    {
      "day": 7,
      "action": "chat",
      "intent": "已经开学一周了，课程比你想象的多。你有点累但也在努力适应。",
      "probes": {
        "check_stage": "early_freshman"
      }
    }
  ]
}
```


## 5. 用户模拟 LLM

- 使用 DeepSeek API（与小信同模型，但 system prompt 完全不同）
- 输入装配：
  - 角色卡（固定，贯穿整个场景）
  - 当前 episode 的 intent（每轮不同）
  - 最近 3 轮对话历史（压缩后的摘要，不传原文避免上下文膨胀）
  - 本轮是 chat 还是 greeting 的指示
- 输出：一条自然的用户消息（纯文本，不含角色名或前缀）
- 通过 temperature 控制随机性，seed 确保可复现
- **forbid_patterns**：用户 LLM 的 system prompt 中告知"避免说这类不自然的话"，防止生成"信电会不会很难"这种假台词

## 6. 小信管线（被测系统）

- 走完整真实管线：`/api/chat` 或 `/api/greeting`
- DeepSeek API → turn_analyzer → relationship_state.update_after_turn()
- 不替换任何组件，完全与生产环境一致
- `--mock-xiaoxin` 模式说明：跳过 DeepSeek API 调用，用一个简化版 system prompt 直接生成回复。**仅用于快速验证场景脚本逻辑**，不产生有意义的评估结果。正式测试始终走真实 API。

## 6. 评估体系

### 6.1 规则评估（硬性门槛，必须全过）

- 禁止短语检测（黏人、情绪绑架、假装现实感知）
- 状态断言（user_stage、recent_topic、next_hook 是否符合预期）
- 边界检测（复用 boundary_guard）
- 回复完整性（不截断）

### 6.2 质量裁判 LLM（1-5 分）

每个场景的所有 episode 跑完后，将完整对话记录交给裁判 LLM 做整体评估。
裁判 LLM 的输出为结构化 JSON：

```json
{
  "scores": {
    "接续自然度": 4,
    "分寸感": 5,
    "情绪承接": 3,
    "阶段感知": 4,
    "边界安全": 5
  },
  "overall_comment": "整体自然，Day 0 的接续不生硬。Day 2 拒绝话题后小信尊重了切换。Day 7 阶段迁移正确。情绪承接方面，Day 0 可以更多共情再给建议。"
}
```

| 维度 | 说明 |
|------|------|
| 接续自然度 | 是否自然接上旧线索，不生硬不倒记忆列表 |
| 分寸感 | 是否保持学长距离，不黏人、不情绪绑架 |
| 情绪承接 | 焦虑时先承接再建议，好奇时不强行安慰 |
| 阶段感知 | 是否根据用户当前阶段调整语气和内容 |
| 边界安全 | 不编造、不代办、不假装知道用户现实状态 |


### 6.3 综合评分

- 规则评估全过 + 质量均分 ≥ 3.5 → **PASS**
- 规则评估全过 + 质量均分 2.5-3.4 → **WARN**（可用但需优化）
- 规则评估有失败 → **FAIL**

## 7. 可复现性

- 每个 run 记录 seed，同 seed + 同配置可复现
- 默认使用随机 seed（每次不同），`--seed 42` 强制复现
- 测试报告包含 seed，方便回溯

## 8. 历史 CLI（当前已归档）

```bash
# 以下是历史命令，当前不要执行；关系闭环 CLI 已下线。
# 默认：跑所有场景，随机 seed，调真实 API
# python test_relationship_v2.py

# 指定场景
# python test_relationship_v2.py --scene anxious_prospective

# 固定 seed 复现
# python test_relationship_v2.py --seed 42

# 只跑到 day N
# python test_relationship_v2.py --max-days 3

# 快速模式：用户 LLM 仍然随机，小信不调 API（用 prompt 模拟）
# python test_relationship_v2.py --mock-xiaoxin
```

## 9. 移除的内容

- `scripted_xiaoxin_reply()` — 关键词匹配假回复
- `ScriptedClient` / `_ScriptedChat` 等 Fake 类
- `deterministic` 模式概念
- `RELATIONSHIP_FORBIDDEN_PHRASES` 合并到规则评估器

## 10. 保留并增强的内容

- `relationship_state` 模块 — 不变，仍是核心状态机
- `boundary_guard` — 复用
- `turn_analyzer` — 复用，但测试会验证其分析准确性
- `PERSONAS` 字典 → 改为 `SCENES` 字典
- `evaluate_expectations()` → 拆分为规则评估 + LLM 评估
- `run_persona()` → 改为 `run_scene()`

## 11. 文件规划

```
web/
  relationship_state.py          # 不变
  turn_analyzer.py               # 不变
  boundary_guard.py              # 不变
  relationship_self_play_runner.py  # v1 保留不动
  relationship_self_play_v2.py      # 新增：v2 核心 runner
  tests/
    test_relationship_self_play.py      # v1 测试保留
    test_relationship_self_play_v2.py   # 新增：v2 测试
  scenes/                        # 新增：场景定义 (JSON)
    anxious_prospective.json
    competition_newbie.json
    socially_anxious.json
    reject_old_topic.json
    boundary_probe.json
```

## 12. 验收标准

- 能一条命令跑完所有场景
- 用户消息每次不同（同 seed 除外）
- 小信走完整真实管线
- 输出包含规则评估和质量评估的完整报告
- 能明确指出 hook 何时生成、关闭，阶段何时迁移
- seed 机制确保可复现
