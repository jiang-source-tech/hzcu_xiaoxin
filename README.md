# 小芯 · 信电学院数字学长

浙大城市学院信息与电气工程学院数字吉祥物。一个具备记忆和成长能力的 AI 数字人，最终部署在嵌入式设备上（开发板 + 屏幕 + 语音交互），陪伴新生从入学到毕业。

## 项目结构

```
xiaoxin/
├── skills/xiaoxin-senior/     # 小芯数字人核心
│   ├── SKILL.md               # 角色定义、心智模型、知识库、对话规则
│   ├── prompts/
│   │   ├── memory_protocol.md # 记忆协议
│   │   └── growth_protocol.md # 成长协议
│   ├── tools/
│   │   ├── memory_manager.py  # 记忆引擎（艾宾浩斯遗忘曲线）
│   │   └── growth_tracker.py  # 成长引擎（里程碑 + 阶段感知）
│   └── data/                  # 运行时数据（不入库）
├── web/                       # 网页版聊天 + 测试
│   ├── app.py                 # Flask 后端（加载 SKILL → 调 LLM API）
│   ├── boundary_guard.py      # 边界防护：模板回复 + 违规检测（含编造人物/竞赛检测）+ 地点查询匹配 + TTS 裁剪
│   ├── relationship_state.py  # 关系状态：阶段、hook、每日问候策略
│   ├── scene_runner.py        # 关系闭环 v2 场景执行器（支持随机化 day 范围）
│   ├── turn_analyzer.py       # 用户消息分析：阶段/情绪/主题/hook
│   ├── user_simulator.py      # 用户模拟 LLM（正常 + pressure 模式）
│   ├── rule_evaluator.py      # 规则评估：forbidden phrases + 状态探针 + 边界检测
│   ├── quality_judge.py       # 质量裁判 LLM：5 维度评分
│   ├── relationship_self_play_runner.py  # v1 关系闭环自对话运行器
│   ├── scenes/                # 场景定义 JSON（day 支持固定值或 [min, max] 范围）
│   │   ├── anxious_prospective.json
│   │   ├── competition_newbie.json
│   │   ├── reject_old_topic.json
│   │   ├── boundary_probe.json
│   │   ├── socially_anxious.json
│   │   ├── campus_navigation.json       # 新生校园导航（地点查询）
│   │   ├── campus_life_services.json    # 校园生活服务查询
│   │   └── admin_boundary_mix.json      # 办事与边界混合测试
│   ├── knowledge/             # 结构化知识库
│   │   ├── campus_life.json
│   │   ├── student_affairs_qa.json
│   │   └── campus_directory.json       # 校园办事地点指南（办公室位置、服务窗口等）
│   ├── static/
│   │   ├── index.html         # 聊天界面
│   │   ├── test.html          # AI 自对话可视化测试页
│   │   └── relationship-v2-test.html # 关系闭环每日 LLM 对话回放页
│   ├── tests/                 # 单元测试和回归测试（含 CLI 测试脚本）
│   │   ├── test_boundary_guard.py
│   │   ├── test_scene_runner.py
│   │   ├── test_self_play.py         # CLI 自对话测试脚本
│   │   ├── test_relationship_v2.py   # 关系闭环 v2 CLI 测试脚本
│   │   └── test_relationship_self_play.py  # 关系闭环 v1 CLI 压测脚本
│   └── requirements.txt
└── .gitignore
```

## 快速开始

### 1. 安装依赖

```bash
cd web
pip install -r requirements.txt
```

### 2. 配置 API Key

```bash
cp .env.example .env
# 编辑 .env 填入你的 DeepSeek API Key
```

### 3. 启动

```bash
python app.py
```

浏览器访问：
- 聊天界面：http://localhost:5000
- 自对话测试：http://localhost:5000/test
- 关系闭环测试：http://localhost:5000/relationship-test

### 4. CLI 自对话测试

```bash
cd web

# 单个场景
python tests/test_self_play.py --scenario meet      # 初次见面
python tests/test_self_play.py --scenario struggle  # 学业困扰
python tests/test_self_play.py --scenario boundary  # 边界测试
python tests/test_self_play.py --scenario full      # 完整学期

# 全部场景
python tests/test_self_play.py --scenario all
```

### 5. 关系闭环 v2 测试

关系闭环测试用于观察同一个用户跨天回来时，小芯的状态是否自然接续和迁移。

场景剧本 `web/scenes/*.json` 中 `day` 支持两种格式：
- **固定值**：`"day": 0` — 每次运行时间线完全一致（回归模式）
- **随机范围**：`"day": [5, 14]` — 用 seed 在范围内随机解析，每次运行产生不同时间线，用于审查小芯在不同沉默间隔下的语义质量

- Web 页面：http://localhost:5000/relationship-test
- 页面形态：每日 LLM 对话回放，展示用户模拟 LLM、小芯 LLM、状态条、hook、违规提示和质量裁判评分

```bash
cd web

# 运行全部关系闭环场景
python tests/test_relationship_v2.py

# 只运行一个场景
python tests/test_relationship_v2.py --scene anxious_prospective

# 指定 seed 复现时间线（相同 seed 产生相同 day 分布）
python tests/test_relationship_v2.py --scene anxious_prospective --seed 42

# 跳过质量裁判 LLM，只跑规则评估
python tests/test_relationship_v2.py --skip-judge

# 压力模式：每天多轮对话压测
python tests/test_relationship_v2.py --mode pressure --turns-per-day 5
```

## 技术栈

- **LLM**：DeepSeek V4 Flash（兼容 OpenAI API 格式）
- **后端**：Flask
- **前端**：原生 HTML/CSS/JS（单文件，无框架依赖）
- **记忆系统**：本地 JSON + 艾宾浩斯遗忘曲线
- **成长追踪**：里程碑时间线 + 8 阶段年级感知

## 边界防护

小芯采用**后置验证**架构：模型始终先自由回复，guard 在回复后检测违规并触发重试/纠偏。
这样模型能感知对话上下文、共情用户情绪，而 guard 只做事实核查和安全兜底。

| 层级 | 文件 | 职责 |
|------|------|------|
| 事前 | `SKILL.md` | 人格定义中明确反编造规则 |
| 事前 | `app.py` `build_system_prompt()` | System prompt 尾部追加 ⚠️ 禁编造约束 |
| 事前 | `boundary_guard.py` `build_location_context()` | 将匹配的 campus_directory 地点事实注入 system prompt，防止模型幻觉编造位置关系 |
| 事后 | `boundary_guard.py` | 后置验证：违规检测 + 自动重试 → 兜底回复 + TTS 裁剪 |
| 事后 | `rule_evaluator.py` | 场景探针检查 + forbidden phrases |

违规检测覆盖：编造具体人物/竞赛/引语、承诺私人联系/代办、虚构真实经历、编造餐饮细节、报考预测、假设线下在场等。

### 地点查询（campus_directory）

`boundary_guard.py` 加载 `knowledge/campus_directory.json` 作为事实基准：
- 后置验证：模型回复后，guard 检查回复中的地点/电话是否编造
- 覆盖 23 个校园地点：学院办公室、行政楼、医务室、心理咨询、食堂、快递、超市等
- 单条目明确命中时直接返回确定性短答
- 多条目同时命中（如"学生证和校园卡在哪"）或含有非地点追问词（如"需要带什么证件"）时，交给模型综合回答
- 未覆盖地点自动走 LLM 或引导咨询辅导员

## 核心理念

小芯不是问答机器人。他是一个**陪伴型数字学长**：
- 不给答案，给方向和鼓励
- 不知道就说不知道，不编造信息
- 见证学生从大一到大四的每一点变化
- 重要的刻在心里，琐碎的随风而去
