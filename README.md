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
│   ├── boundary_guard.py      # 边界防护：safe_reply 确定性 builder + 模板回复 + 违规检测（含编造人物/竞赛/快递）+ 地点查询匹配 + 行动确认拦截 + TTS 裁剪
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
│   │   ├── test_boundary_guard.py     # 边界分类、模板回复、违规检测、TTS 裁剪
│   │   ├── test_skill_boundaries.py   # SKILL.md 边界规则存在性验证
│   │   ├── test_selfplay_end.py       # 自对话 API、模拟用户人格、边界重试
│   │   ├── test_selfplay_openings.py  # /test 页面角色和开场白
│   │   ├── test_selfplay_layout.py    # 测试页布局和违规展示
│   │   ├── test_relationship.py       # 关系状态加载/保存/更新/prompt_summary
│   │   ├── test_scene_runner.py       # v2 场景加载、随机化 day、memory_audit
│   │   ├── test_relationship_v2.py    # 关系闭环 v2 CLI 测试脚本
│   │   ├── test_relationship_v2_page.py # /relationship-test 页面和记忆审计面板
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
- 页面形态：每日 LLM 对话回放，展示用户模拟 LLM、小芯 LLM、状态条、hook 和记忆审计面板（不展示系统 PASS/WARN/FAIL 和质量裁判评分，避免自动判断误伤真实对话）

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

小芯采用**"确定性 builder 前置 + LLM 开放聊天 + 后置验证"**三层架构：
- 事实型办事回复由 `safe_reply()` 程序化生成，不调用模型
- 开放陪伴场景走 LLM，回复后做越界检测并重试/兜底
- 这样事实只来自本地知识库，模型只负责自然对话

| 层级 | 文件 | 职责 |
|------|------|------|
| 前置 | `boundary_guard.py` `safe_reply()` | 确定性 builder：食堂、快递、地点、官方流程、收尾办事等场景直接组装回复 |
| 前置 | `app.py` `build_location_context()` | 将匹配的 campus_directory 地点事实注入 system prompt，防止模型幻觉编造位置关系 |
| 前置 | `SKILL.md` | 人格定义中明确反编造规则 |
| 前置 | `app.py` `build_system_prompt()` | System prompt 尾部追加 ⚠️ 禁编造约束 |
| 事后 | `boundary_guard.py` | 后置验证：违规检测 + 自动重试 → 兜底回复 + TTS 裁剪 |
| 事后 | `rule_evaluator.py` | 场景探针检查 + forbidden phrases |

违规检测覆盖：编造具体人物/竞赛/引语、承诺私人联系/代办、虚构真实经历、编造餐饮细节、报考预测、假设线下在场、**编造快递点/假设宿舍位置**等。

### 地点查询（campus_directory）

`boundary_guard.py` 加载 `knowledge/campus_directory.json` 作为事实基准：
- `safe_reply()` 前置拦截：对 `location_query` 类问题，`match_location_query()` 单条目命中时直接返回确定性短答；多条目命中或含非地点追问词时交给模型
- 后置验证：模型回复后，guard 检查回复中的地点/电话是否编造
- 覆盖 23 个校园地点：学院办公室、行政楼、医务室、心理咨询、食堂、快递、超市等
- 对成绩单打印终端和快递查询有专属模板，快递回复不假设用户宿舍位置

### 快递回复规则

问到快递站、包裹、取件时：
- 列出知识库中明确的快递点
- 不假设用户住在哪栋宿舍，不说"你楼下快递站""寝室楼下那个柜子"
- 外卖柜不是快递点，不能按快递处理
- 提醒以短信、取件码或快递平台通知为准

### 收尾/行动确认（action_commitment）

用户说"我先去办事""下次聊""先去试试""转转""逛逛"等收尾或行动确认时，`is_action_commitment()` 优先识别并走短句安全回复，防止被地点关键词误判为 FAQ，也避免模型编造校园景物、路线或现场状态。

## 核心理念

小芯不是问答机器人。他是一个**陪伴型数字学长**：
- 不给答案，给方向和鼓励
- 不知道就说不知道，不编造信息
- 见证学生从大一到大四的每一点变化
- 重要的刻在心里，琐碎的随风而去
