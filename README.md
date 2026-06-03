# 小信 · 信电学院数字学长

浙大城市学院信息与电气工程学院数字吉祥物。一个具备记忆和成长能力的 AI 数字人，最终部署在嵌入式设备上（开发板 + 屏幕 + 语音交互），陪伴新生从入学到毕业。

## 项目结构

```
xiaoxin/
├── skills/xiaoxin-senior/     # 小信数字人核心
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
│   ├── test_self_play.py      # CLI 自对话测试脚本
│   ├── static/
│   │   ├── index.html         # 聊天界面
│   │   └── test.html          # AI 自对话可视化测试页
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

### 4. CLI 自对话测试

```bash
# 单个场景
python test_self_play.py --scenario meet      # 初次见面
python test_self_play.py --scenario struggle  # 学业困扰
python test_self_play.py --scenario boundary  # 边界测试
python test_self_play.py --scenario full      # 完整学期

# 全部场景
python test_self_play.py --scenario all
```

## 技术栈

- **LLM**：DeepSeek V4 Flash（兼容 OpenAI API 格式）
- **后端**：Flask
- **前端**：原生 HTML/CSS/JS（单文件，无框架依赖）
- **记忆系统**：本地 JSON + 艾宾浩斯遗忘曲线
- **成长追踪**：里程碑时间线 + 8 阶段年级感知

## 核心理念

小信不是问答机器人。他是一个**陪伴型数字学长**：
- 不给答案，给方向和鼓励
- 不知道就说不知道，不编造信息
- 见证学生从大一到大四的每一点变化
- 重要的刻在心里，琐碎的随风而去
