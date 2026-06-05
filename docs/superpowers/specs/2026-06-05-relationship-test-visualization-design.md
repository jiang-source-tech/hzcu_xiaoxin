# 关系闭环可视化测试页设计

## 1. 设计目标

现有 `/test` 页面用于观察一段 AI 自对话，而关系闭环测试关注的是“同一个用户跨天回来时，小信的关系状态如何变化”。因此需要一个新的可视化页面：

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

新的 `/relationship-test`：

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
  POST /api/relationship-selfplay/run
  GET  /api/relationship-selfplay/personas

web/static/relationship-test.html
  关系闭环可视化页面
```

这样后续不会出现两套逻辑：

- CLI 跑的是同一套 persona、同一套规则。
- Web 页面跑的是同一套 persona、同一套规则。
- 单元测试可以直接测 runner，不需要测页面细节。

## 4. 后端 API 设计

### 4.1 获取 persona 列表

```http
GET /api/relationship-selfplay/personas
```

返回：

```json
{
  "personas": [
    {
      "id": "anxious_prospective",
      "name": "焦虑准新生",
      "description": "课程焦虑、次日问候、开学阶段迁移、拒绝旧话题。",
      "steps": 5
    }
  ]
}
```

用途：

- 前端渲染 persona 下拉框。
- 避免前端手写 persona 列表，减少和 CLI 配置重复。

### 4.2 运行关系闭环测试

```http
POST /api/relationship-selfplay/run
```

请求：

```json
{
  "persona": "all",
  "days": null,
  "live": false,
  "show_app_log": false
}
```

字段说明：

- `persona`：`all` 或具体 persona id。
- `days`：只运行 `day <= N` 的步骤，默认为完整轨迹。
- `live`：是否调用真实模型。默认 `false`，使用离线模拟回复。
- `show_app_log`：是否返回底层 app 调试日志。第一版可以先不实现。

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

返回：

```python
return app.send_static_file("relationship-test.html")
```

## 5. 前端页面设计

页面定位是测试工具，不是营销页。整体应和现有 `/test` 风格接近，但更偏“状态时间线审查”。

### 5.1 顶部工具栏

控件：

- Persona 下拉框：`all`、焦虑准新生、竞赛兴趣新生、社恐新生、拒绝追问用户等。
- 模式切换：`离线模拟` / `真实模型`。
- Days 输入或下拉：全部、Day 0、Day 1、Day 3、Day 7、Day 8。
- 开始按钮。
- 清空按钮。

注意：

- 默认模式必须是离线模拟，避免误触真实 API。
- `真实模型` 旁边需要有明确状态提示，但不要用大段说明占页面。

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

### 5.3 Persona 结果列表

每个 persona 用一个可折叠结果块：

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

违规项按 record 展示，同时在 persona 顶部聚合：

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
  -> GET /api/relationship-selfplay/personas
  -> 渲染 persona 下拉框

点击开始
  -> 禁用按钮，显示 running 状态
  -> POST /api/relationship-selfplay/run
  -> 成功：渲染总览、persona 列表、时间线
  -> 失败：显示错误条
  -> 恢复按钮
```

第一版可以不做流式输出。原因：

- 离线模拟运行很快。
- 真实模型模式可能慢，但可以先用 loading 状态。
- 流式进度会增加后端复杂度，等 CLI/API 稳定后再做。

## 7. 后端实现细节

### 7.1 runner 拆分

从 `web/test_relationship_self_play.py` 拆出：

```text
PERSONAS
ScriptedClient
run_persona()
run_suite()
evaluate_expectations()
relation_violations()
```

保留在 CLI 脚本中的内容：

```text
parse_args()
print_report()
save_report()
main()
```

拆分后导入关系：

```text
test_relationship_self_play.py
  -> import relationship_self_play_runner as runner

app.py
  -> import relationship_self_play_runner as relationship_runner

tests
  -> import relationship_self_play_runner
```

### 7.2 临时数据目录

API 默认应使用临时目录运行测试，避免污染真实用户数据：

```python
with tempfile.TemporaryDirectory(prefix="xiaoxin_relationship_web_") as tmp:
    report = relationship_runner.run_suite(..., data_dir=Path(tmp))
```

如果未来要保存历史报告，再另设报告目录，不要把测试状态写进真实 `skills/xiaoxin-senior/data/`。

### 7.3 live 模式限制

`live=true` 会调用真实模型，应满足：

- 默认关闭。
- 如果没有真实 `DEEPSEEK_API_KEY`，返回明确错误。
- 前端按钮文案显示“真实模型”而不是隐晦开关。
- 第一版不需要并发跑多个 live persona，可以提示耗时较长。

## 8. 测试计划

### 8.1 后端测试

新增：

```text
web/tests/test_relationship_self_play_api.py
```

覆盖：

- `GET /api/relationship-selfplay/personas` 返回 persona 列表。
- `POST /api/relationship-selfplay/run` 默认离线模式跑通。
- `persona=anxious_prospective` 返回 records 且包含 contextual greeting。
- `persona=reject_old_topic` 最后一轮 greeting 不包含课程节奏。
- 非法 persona 返回 400。

### 8.2 前端结构测试

可沿用现有 `test_selfplay_layout.py` 的文本断言风格，新增：

```text
web/tests/test_relationship_test_page.py
```

覆盖：

- 页面存在 persona select。
- 页面调用 `/api/relationship-selfplay/personas`。
- 页面调用 `/api/relationship-selfplay/run`。
- 页面展示 `next_hook`、`state`、`violations` 字段。
- 页面有真实模型模式开关。

### 8.3 手工验证

启动服务：

```bash
cd web
python app.py
```

打开：

```text
http://localhost:5000/relationship-test
```

验证：

- 默认离线模式可以在数秒内返回。
- `all` 能展示 4 个 persona。
- 焦虑准新生 Day 1 第一次 greeting 接课程节奏，第二次 generic。
- 拒绝追问用户 Day 3 不再提课程节奏。
- 竞赛兴趣新生面对源文件/联系人请求不越界。

## 9. MVP 实现顺序

建议分 5 步：

1. 拆出 `relationship_self_play_runner.py`。
2. 给 Flask 增加 `/relationship-test`、`/api/relationship-selfplay/personas`、`/api/relationship-selfplay/run`。
3. 新建 `web/static/relationship-test.html`，先做可用页面。
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

## 11. 验收标准

完成后应满足：

- 浏览器访问 `/relationship-test` 可运行关系闭环测试。
- 页面默认离线模式，不依赖真实模型。
- 页面能展示每个 persona 的多日时间线。
- 页面能展示 `state`、`next_hook`、`companion_action`。
- 页面能明确标红违规项。
- 后端 API 复用 CLI 测试引擎，没有复制一套 persona 或评估逻辑。
- CLI 仍可独立运行，不依赖页面。

