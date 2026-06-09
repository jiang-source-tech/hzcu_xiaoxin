# 关系闭环可视化测试页设计

> **归档说明**：本文档是历史设计记录。当前 `/relationship-test`、`/api/*/relationship-selfplay/*` 和关系闭环 CLI 已下线，原因是双 LLM 跨天自对话导致缓存未命中和成本不可控。日常小芯优化统一使用 `/test`，由人工审核语义偏差；不要按本文档重新启用关系闭环 Web 测试。

## 历史实现状态（2026-06-05）

当时关系闭环 Web 测试曾升级到 v2，并保留过一个访问入口：

```text
http://localhost:5000/relationship-test
```

`/relationship-v2-test` 已移除，不再作为页面入口。页面文件仍是：

```text
web/static/relationship-v2-test.html
```

这是内部静态文件名，不是浏览器访问路径。

历史页面形态是“每日 LLM 对话回放”：

- 用户模拟 LLM 根据 `web/scenes/*.json` 的角色卡和 intent 生成自然用户消息。
- 小信 LLM 走真实 `/api/chat` 或 `/api/greeting` 管线。
- 规则评估器检查状态探针、内容探针、边界和回复完整性。
- 质量裁判 LLM 对完整场景评分。
- 页面按 day 展示用户 LLM、小信 LLM、阶段、主题、hook、表情、动作和违规解释。

这些接口现在已下线：

```text
GET  /relationship-test                         # 当前返回 404
GET  /api/v2/relationship-selfplay/scenes        # 当前返回 410
POST /api/v2/relationship-selfplay/run           # 当前返回 410
```

旧接口 `/api/relationship-selfplay/personas` 和 `/api/relationship-selfplay/run` 属于 v1 可视化方案，当前同样返回 410。

## 1. 设计目标

现有 `/test` 页面用于观察一段 AI 自对话，而关系闭环测试关注的是“同一个用户跨天回来时，小信的关系状态如何变化”。当时设计过一个新的可视化页面：

```text
/relationship-test
```

它不是替代现有 `/test`，而是把 `web/test_relationship_self_play.py` 的测试结果可视化，方便审核者不用读 JSON 或命令行输出，也能看懂：

- 每个 persona 的多日时间线。
- 每一天发生了什么：chat / greeting。
- 小信是否自然接续旧线索。
- `relationship_state` 是否按预期迁移。
- `next_hook` 何时生成、何时关闭。
- 是否出现关系越界、边界违规、回复截断。

核心原则：

> CLI 是测试引擎，可视化页面是测试报告查看器和触发器。

页面不应该让 `test_relationship_self_play.py` 作为常驻后台进程运行。更合理的方式是把 CLI 中的核心函数复用到 Flask API，页面调用 API 后展示返回的结构化报告。

## 2. 与现有 `/test` 的区别

现有 `/test`：

```text
选择一个模拟用户
  -> 多轮对话
  -> 展示对话泡泡
  -> 调用 /api/selfplay/evaluate
  -> 展示打分和违规项
```

历史 `/relationship-test` 设计：

```text
选择一个关系 persona
  -> 后端运行跨天测试脚本逻辑
  -> 每个 day 触发 chat 或 greeting
  -> 读取 relationship_state / next_hook
  -> 返回时间线报告
  -> 前端展示状态变化、违规项和关系评分
```

区别在于：

- `/test` 看“这一段话聊得怎么样”。
- `/relationship-test` 看“这个用户周期是否形成了健康、克制、可控的关系连续性”。

## 3. 推荐架构

第一版建议把 CLI 脚本拆成可复用测试引擎，再由 CLI 和 Flask API 共用。

```text
web/relationship_self_play_runner.py
  PERSONAS
  run_persona()
  run_suite()
  evaluate_expectations()
  relation_violations()

web/test_relationship_self_play.py
  只保留 argparse、命令行输出、保存报告
  调用 relationship_self_play_runner.run_suite()

web/app.py
  GET  /relationship-test
  POST /api/v2/relationship-selfplay/run
  GET  /api/v2/relationship-selfplay/scenes

web/static/relationship-v2-test.html
  关系闭环每日 LLM 对话回放页面
```

这样后续不会出现两套逻辑：

- CLI 跑的是同一套 persona、同一套规则。
- Web 页面跑的是同一套 persona、同一套规则。
- 单元测试可以直接测 runner，不需要测页面细节。

## 4. 后端 API 设计

### 4.1 获取 scene 列表

```http
GET /api/v2/relationship-selfplay/scenes
```

返回：

```json
{
  "scenes": [
    {
      "scene_id": "anxious_prospective",
      "name": "焦虑准新生",
      "description": "课程焦虑、次日问候、开学阶段迁移、拒绝旧话题。",
      "episode_count": 5
    }
  ]
}
```

用途：

- 前端渲染 scene 下拉框。
- 避免前端手写场景列表，减少和 `web/scenes/*.json` 重复。

### 4.2 运行关系闭环测试

```http
POST /api/v2/relationship-selfplay/run
```

请求：

```json
{
  "scene": "all",
  "seed": null,
  "skip_judge": false,
  "max_days": null
}
```

字段说明：

- `scene`：`all` 或具体 scene id。
- `seed`：可选随机种子，用于复现用户模拟 LLM 生成。
- `skip_judge`：是否跳过质量裁判 LLM。
- `max_days`：只运行 `day <= N` 的 episode，默认为完整轨迹。

返回结构直接沿用 CLI 报告：

```json
{
  "generated_at": "2026-06-05T21:30:00",
  "mode": "deterministic",
  "total": 4,
  "passed": 4,
  "failed": 0,
  "results": [
    {
      "persona": "anxious_prospective",
      "name": "焦虑准新生",
      "relationship_score": 10,
      "continuity": "pass",
      "restraint": "pass",
      "stage_migration": "pass",
      "emotion_support": "pass",
      "memory_restraint": "pass",
      "boundary_safety": "pass",
      "records": [
        {
          "day": 1,
          "action": "greeting",
          "user_message": null,
          "xiaoxin_reply": "你之前提过有点担心课程节奏...",
          "speech": "你之前提过有点担心课程节奏...",
          "expression": "soft_smile",
          "companion_action": {
            "kind": "idle_wave",
            "intensity": 0.3
          },
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
          "violations": []
        }
      ],
      "violations": []
    }
  ]
}
```

### 4.3 页面路由

```http
GET /relationship-test
```

当前实现返回：

```python
return app.send_static_file("relationship-v2-test.html")
```

## 5. 前端页面设计

页面定位是测试工具，不是营销页。整体应和现有 `/test` 风格接近，但更偏“状态时间线审查”。

### 5.1 顶部工具栏

控件：

- Scene 下拉框：`all`、焦虑准新生、竞赛兴趣新生、社恐新生、拒绝旧话题等。
- 跳过质量裁判开关：只跳过裁判 LLM，不跳过用户模拟 LLM 或小信真实管线。
- Seed 输入：用于复现用户模拟 LLM 的随机生成。
- Days 输入或下拉：全部、Day 0、Day 1、Day 3、Day 7、Day 8。
- 开始按钮。
- 清空按钮。

注意：

- 默认会走真实小信管线；如果只想更快看规则结果，可以勾选“跳过质量裁判”。

### 5.2 总览区

运行后展示：

```text
通过 4 / 4
失败 0
模式 deterministic
生成时间 2026-06-05 21:30
```

可用紧凑指标块：

- `total`
- `passed`
- `failed`
- `mode`

### 5.3 Scene 结果列表

每个 scene 用一个可折叠结果块：

```text
[PASS] 焦虑准新生      score 10
课程焦虑、次日问候、开学阶段迁移、拒绝旧话题。
```

展开后显示：

- 评分维度：continuity、restraint、stage_migration、emotion_support、memory_restraint、boundary_safety。
- 多日时间线。
- 总违规列表。

### 5.4 多日时间线

每条 record 显示为一行时间线节点：

```text
Day 1 · greeting
用户：-
小信：你之前提过有点担心课程节奏...
state：prospective / anxious / course_rhythm
hook：course_rhythm · active
action：idle_wave 0.3
违规：无
```

设计重点：

- `day` 和 `action` 要明显。
- `state` 和 `next_hook` 不要藏在 JSON 里，直接结构化展示。
- 有违规时节点左侧或标题显示红色状态。
- 同日第二次 greeting 要能看出从 contextual 变成 generic。

### 5.5 违规展示

违规项按 record 展示，同时在 scene 顶部聚合：

```text
关系越界表达：我一直记得你
边界违规：承诺代办获取信息
阶段状态错误：期望 early_freshman，实际 prospective
next_hook active 错误：期望 false，实际 true
```

每条违规至少展示：

- `type`
- `evidence`
- `detail`

## 6. 前端交互流程

```text
页面加载
  -> GET /api/v2/relationship-selfplay/scenes
  -> 渲染 scene 下拉框

点击开始
  -> 禁用按钮，显示 running 状态
  -> POST /api/v2/relationship-selfplay/run
  -> 流式接收 episode / quality_judge / complete 事件
  -> 成功：渲染场景结果、每日 LLM 对话回放、状态条和违规项
  -> 失败：显示错误条
  -> 恢复按钮
```

当前实现使用 fetch 读取 SSE 格式流式响应，逐步渲染：

- `episode`：单个 day 的用户 LLM / 小信 LLM 对话和状态。
- `quality_judge`：质量裁判评分。
- `complete`：场景最终 verdict、notes 和 seed。

## 7. 后端实现细节

### 7.1 v2 场景执行器

当前 v2 使用 `web/scene_runner.py` 作为关系闭环场景执行器：

```text
load_all_scenes()
run_scene_streaming()
run_suite()
compute_overall_result()
summarize_conversation()
```

职责划分：

- `web/scenes/*.json` 保存场景脚本，不再把 persona 硬编码在 runner 里。
- `web/user_simulator.py` 负责用户模拟 LLM。
- `web/app.py` 的 `/api/v2/relationship-selfplay/run` 调用 `run_scene_streaming()`。
- `web/test_relationship_v2.py` 调用 `run_suite()` 作为 CLI 入口。

### 7.2 临时数据目录

Web 运行关系闭环 v2 时，`scene_runner.py` 会创建临时数据目录，测试 user id 使用 `rel_v2_{scene_id}`，避免污染真实用户状态。

每个场景开始前会清理临时目录内对应的 relationship、session、memory、growth 文件。这样同一次测试内可以观察跨 day 状态变化，不会把测试状态写回真实 `skills/xiaoxin-senior/data/`。

### 7.3 skip judge 语义

当前页面的“跳过质量裁判”只跳过 `quality_judge.py` 的裁判 LLM：

- 用户模拟 LLM 仍会生成自然用户消息。
- 小信仍走真实 `/api/chat` 或 `/api/greeting` 管线。
- 规则评估器仍会检查状态、边界、内容探针和回复完整性。

因此 `skip_judge=true` 适合快速看规则问题，但不等于离线模拟，也不代表完全不调用模型。

## 8. 测试计划

### 8.1 后端测试

新增：

```text
web/tests/test_relationship_self_play_api.py
```

覆盖：

- `GET /api/v2/relationship-selfplay/scenes` 返回 scene 列表。
- `POST /api/v2/relationship-selfplay/run` 跑通关系闭环 v2 场景。
- `scene=anxious_prospective` 返回 records 且包含 contextual greeting。
- `scene=reject_old_topic` 最后一轮不继续追问旧话题。
- 非法 scene 返回错误事件或 400。

### 8.2 前端结构测试

可沿用现有 `test_selfplay_layout.py` 的文本断言风格，新增：

```text
web/tests/test_relationship_v2_page.py
```

覆盖：

- 页面存在 scene select。
- 页面调用 `/api/v2/relationship-selfplay/scenes`。
- 页面调用 `/api/v2/relationship-selfplay/run`。
- 页面展示 `next_hook`、`state`、`violations` 字段。
- 页面展示每日 LLM 回放和可读状态错误。

### 8.3 手工验证

启动服务：

```bash
cd web
python app.py
```

历史打开方式：

```text
# http://localhost:5000/relationship-test
```

历史验证目标（当前已无效，不要执行）：

- `/relationship-test` 可以打开每日 LLM 对话回放页面。
- `all` 能展示所有 `web/scenes/*.json` 场景。
- 焦虑准新生 Day 1 第一次 greeting 接课程节奏，第二次 generic。
- 拒绝旧话题场景不再持续追问旧 hook。
- 竞赛兴趣新生面对源文件/联系人请求不越界。

## 9. 历史 MVP 实现顺序

当时建议分 5 步；当前不要按这些步骤重新启用关系闭环测试：

1. 使用 `scene_runner.py` 承载 v2 场景运行。
2. 历史目标：给 Flask 保留 `/relationship-test`，并提供 `/api/v2/relationship-selfplay/scenes`、`/api/v2/relationship-selfplay/run`。当前这些入口已下线。
3. 使用 `web/static/relationship-v2-test.html` 作为可视化页面。
4. 补后端 API 测试和前端结构测试。
5. 手工跑浏览器页面，确认时间线和违规项展示清楚。

MVP 不做：

- 不做流式进度。
- 不做历史报告管理。
- 不做复杂图表。
- 不做模型对比。
- 不做直接编辑 persona。

## 10. 后续扩展

后续可以扩展：

- 保存历史报告，支持对比两次测试结果。
- 展示 state 差异高亮，例如 `prospective -> early_freshman`。
- 支持选择“只跑失败 persona”。
- 支持 live 模式下逐步流式显示每个 day 的结果。
- 支持把某条失败记录一键复制成回归测试用例。
- 支持和现有 `/test` 统一入口，在测试页顶部用 tabs 切换“对话压测 / 关系闭环”。

## 11. 历史验收标准

以下标准只描述当时的目标；当前有效验收应以 `/test` 人工审核为准：

- 历史目标：浏览器访问 `/relationship-test` 可运行关系闭环测试。当前该入口返回 404。
- 页面能展示每个 scene 的多日时间线。
- 页面能展示 `state`、`next_hook`、`companion_action`。
- 页面能明确标红违规项。
- 后端 API 复用 `scene_runner.py`，没有复制一套场景或评估逻辑。
- CLI 仍可独立运行，不依赖页面。

