# 小芯 · 信电学院数字学长

> *"我不是什么都会的专家，我只是比你们早来几年的学长。"*

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://python.org)
[![Claude Code](https://img.shields.io/badge/Claude%20Code-Skill-blueviolet)](https://claude.ai/code)

浙大城市学院信息与电气工程学院数字吉祥物。一个具备记忆和成长能力的 AI 数字人，运行在嵌入式设备上（开发板 + 屏幕 + 语音交互），陪伴新生从入学到毕业。

---

## 效果示例

### 初次见面

```
新生: 你好小芯！我是大一新生。
小芯: 大一啊！欢迎来到信电学院。你是哪个专业的？

新生: 电子信息工程。
小芯: 电子信息工程这个方向会接触电路、编程和工程实践。刚开学先别急着给自己上强度，
      遇到听不懂的地方，我们可以一块把问题拆小一点。
```

### 吐槽课程

```
新生: 小芯，C语言好难啊
小芯: 嗯，C语言刚开始卡住很正常，尤其是指针、循环和报错一起出现的时候。
      先把报错信息、出错行和你想让程序做什么写清楚，我们可以一小块一小块看。[think]
```

### 超出知识范围

```
新生: 小芯，明天下雨吗？
小芯: 这你可问错人了。我肚子里的芯片不会预报天气。
      不过提醒你，杭州的天气嘛，随身带把伞准没错。[wink]
```

---

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
- **随机范围**：`"day": [5, 14]` — 用 seed 在范围内随机解析，每次运行产生不同时间线

- Web 页面：http://localhost:5000/relationship-test
- 页面形态：每日 LLM 对话回放，展示用户模拟 LLM、小芯 LLM、状态条、hook 和记忆审计面板

```bash
cd web

# 运行全部关系闭环场景
python tests/test_relationship_v2.py

# 只运行一个场景
python tests/test_relationship_v2.py --scene anxious_prospective

# 指定 seed 复现时间线
python tests/test_relationship_v2.py --scene anxious_prospective --seed 42

# 跳过质量裁判 LLM
python tests/test_relationship_v2.py --skip-judge

# 压力模式
python tests/test_relationship_v2.py --mode pressure --turns-per-day 5
```

费用提醒：`relationship_v2.py` 的真实运行会同时调用“用户模拟 LLM”和“小芯 LLM”，越界重试时还会增加额外调用；全场景 `--scene all` 会产生大量不同上下文，DeepSeek 缓存命中率较低。日常开发优先跑本地单元测试，人工审核优先使用 Web 页面或单个 scene；全场景真实 LLM 审计只建议在最终验收时运行。

---

## 技术栈

- **LLM**：DeepSeek V4 Flash（兼容 OpenAI API 格式）
- **后端**：Flask
- **前端**：原生 HTML/CSS/JS（单文件，无框架依赖）
- **记忆系统**：本地 JSON + 艾宾浩斯遗忘曲线
- **成长追踪**：里程碑时间线 + 8 阶段年级感知
- **Prompt 管理**：组件化 prompts/ + prompt_builder.py 自动组合

---

## 边界防护

小芯采用**"确定性 builder 前置 + LLM 开放聊天 + 后置验证"**三层架构：
- 事实型办事回复由 `safe_reply()` 程序化生成，不调用模型
- `safe_reply()` 使用本地知识库事实 + 受控小芯句式池；`stable_variant()` 按用户话术稳定选择表达
- 开放陪伴场景走 LLM，回复后做越界检测并重试/兜底

| 层级 | 文件 | 职责 |
|------|------|------|
| 前置 | `boundary_guard.py` `safe_reply()` | 确定性 builder：食堂、快递、地点、官方流程、收尾办事等场景直接组装回复 |
| 前置 | `app.py` `build_location_context()` | 将 campus_directory 地点事实注入 system prompt |
| 前置 | `prompts/hard_rules.md` | Layer 0 硬规则：反编造、诚实边界、价值观 |
| 前置 | `app.py` `build_system_prompt()` | System prompt 尾部追加 ⚠️ 禁编造约束 |
| 事后 | `boundary_guard.py` | 后置验证：违规检测 + 自动重试 → 兜底回复 + TTS 裁剪 |
| 事后 | `rule_evaluator.py` | 场景探针检查 + forbidden phrases |

违规检测覆盖：编造具体人物/竞赛/引语、承诺私人联系/代办、虚构真实经历、编造餐饮细节、报考预测、假设线下在场、**编造快递点/假设宿舍位置**、猜测用户位置、社交标签化、过度黏连关系表达，以及未核实的宿舍条件、社交统计、课程保障等。

### 地点查询（campus_directory）

- `safe_reply()` 前置拦截：单条目命中时直接返回确定性短答；多条目命中或含非地点追问词时交给模型
- 覆盖 23 个校园地点：学院办公室、行政楼、医务室、心理咨询、食堂、快递、超市等
- 对成绩单打印终端和快递查询有专属模板，快递回复不假设用户宿舍位置

### 快递回复规则

- 列出知识库中明确的快递点
- 不假设用户住在哪栋宿舍
- 外卖柜不是快递点
- 提醒以短信、取件码或快递平台通知为准

### 收尾/行动确认（action_commitment）

用户说"我先去办事""下次聊""先去试试"等收尾时，`is_action_commitment()` 优先识别并走短句安全回复。用 `stable_variant()` 从安全句式池里稳定选择表达，避免模型编造校园景物、路线或现场状态。

---

## 项目结构

```
xiaoxin/
├── skills/xiaoxin-senior/     # 小芯数字人核心
│   ├── SKILL.md               # 角色定义（由 prompt_builder.py 从 prompts/ 组件自动生成）
│   ├── prompts/               # Prompt 组件（按 Layer 0→5 分层）
│   │   ├── hard_rules.md      # Layer 0: 硬规则
│   │   ├── identity.md        # Layer 1: 身份锚定
│   │   ├── speech_style.md    # Layer 2: 对话风格
│   │   ├── mental_models.md   # Layer 3: 心智模型
│   │   ├── knowledge_domains.md # Layer 4: 知识域
│   │   ├── response_workflow.md # Layer 5: 回答工作流
│   │   ├── example_dialogues.md # 附录: 示例对话
│   │   ├── embedded_adaptation.md # 附录: 嵌入式设备适配
│   │   ├── memory_protocol.md # 记忆协议
│   │   └── growth_protocol.md # 成长协议
│   ├── tools/
│   │   ├── prompt_builder.py  # Prompt 组件组合工具
│   │   ├── meta_manager.py    # 用户画像管理（画像 + 纠正记录）
│   │   ├── memory_manager.py  # 记忆引擎（艾宾浩斯遗忘曲线）
│   │   └── growth_tracker.py  # 成长引擎（里程碑 + 阶段感知）
│   └── data/                  # 运行时数据（不入库）
├── web/                       # 网页版聊天 + 测试
│   ├── app.py                 # Flask 后端（加载 SKILL → 调 LLM API）
│   ├── boundary_guard.py      # 边界防护：safe_reply + 模板回复 + 违规检测 + TTS 裁剪
│   ├── relationship_state.py  # 关系状态：阶段、hook、每日问候策略
│   ├── scene_runner.py        # 关系闭环 v2 场景执行器
│   ├── turn_analyzer.py       # 用户消息分析
│   ├── user_simulator.py      # 用户模拟 LLM
│   ├── rule_evaluator.py      # 规则评估
│   ├── quality_judge.py       # 质量裁判 LLM
│   ├── scenes/                # 场景定义 JSON
│   ├── knowledge/             # 结构化知识库（campus_life、campus_directory 等）
│   ├── static/                # 前端页面
│   │   ├── index.html         # 聊天界面
│   │   ├── test.html          # 自对话测试页
│   │   └── relationship-v2-test.html # 关系闭环回放页
│   ├── tests/                 # 单元测试和回归测试
│   └── requirements.txt
└── docs/
    ├── PROJECT_GUIDE.md       # 项目维护说明
    └── ELECTRONIC_PET_NEXT_STAGE.md
```

---

## 核心理念

小芯不是问答机器人。他是一个**陪伴型数字学长**：
- 不给答案，给方向和鼓励
- 不知道就说不知道，不编造信息
- 见证学生从大一到大四的每一点变化
- 重要的刻在心里，琐碎的随风而去

---

## 致敬 & 引用

本项目架构灵感来源于：

- **[自己.skill](https://github.com/notdog1998/yourself-skill)**（by Notdog）— 首创"把人蒸馏成 AI Skill"的双层架构（Self Memory + Persona），本项目借鉴了其 prompt 组件化与 Layer 0 硬规则分层设计
- **[同事.skill](https://github.com/titanwings/colleague-skill)**（by titanwings）— 首创"把人蒸馏成 AI Skill"的 Skill 架构范式

小芯在此基础上将视角转向**数字吉祥物与陪伴**——对象不再是真实人物镜像，而是一个有温度、有边界、能陪伴学生成长的学院数字学长。
