# 小芯 · 信电学院数字学长

> “我不是什么都会的专家，我只是比你们早来几年的学长。”

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://python.org)

小芯是浙大城市学院信息与电气工程学院的数字吉祥物和数字学长。项目目标不是做一个通用问答机器人，而是做一个有记忆、有边界、能陪伴新生成长的电子宠物型数字人。

当前版本已回到更稳定、更利于缓存命中的主提示词结构：`SKILL.md` 作为长期稳定人格提示词，`prompts/` 只保留记忆协议和成长协议；校园生活、学生事务、地点信息放在结构化 JSON 知识库中，由后端确定性读取。

---

## 当前架构

```text
用户消息
  -> boundary_guard.template_reply()
       高风险问题、食堂、学生事务、校园地点等可确定场景直接短答
  -> 未命中时调用 LLM
       build_system_prompt() = SKILL.md + 记忆 + 成长快照 + 关系状态
  -> 后置检查
       清理思考标记、检查半截回复、检查越界表达、必要时重试或兜底
  -> 返回 reply / speech / expression
```

这个版本的重点是平衡“人情味”和“少幻觉”：

- 开放陪伴聊天交给模型自然生成。
- 事实型校园信息只从本地知识库读。
- 知识库没写明的楼号、楼层、窗口、价格、营业时间、联系方式，不让模型补。
- 模型回复后仍做越界检测，防止承诺代办、编造经历、预测录取、假设线下在场。

## 快速开始

```bash
cd web
pip install -r requirements.txt
copy .env.example .env
python app.py
```

启动后访问：

- 聊天界面：http://localhost:5000
- 自对话测试：http://localhost:5000/test

`.env` 中需要配置：

```env
DEEPSEEK_API_KEY=your-api-key
DEEPSEEK_MODEL=deepseek-v4-flash
```

## 测试

```bash
python -m unittest discover web/tests
```

当前回归测试覆盖：

- prompt 目录保持两文件结构，避免再次拆碎。
- 食堂知识来自 `campus_life.json`，不包含已审查排除的错误事实。
- 学生事务和校园地点优先从结构化知识库短答。
- `/test` 角色包含行政事务角色“事务新生”。
- 新生继续追问时不会被误判为结束对话。
- 小芯不能编造联系方式、竞赛资源、真实学生经历、食堂口味排行、录取概率等。

## 项目结构

```text
hzcu_ai_pet/
├── README.md
├── docs/
│   ├── PROJECT_GUIDE.md
│   └── ELECTRONIC_PET_NEXT_STAGE.md
├── skills/xiaoxin-senior/
│   ├── SKILL.md                    # 小芯长期稳定人格、知识边界、回答风格
│   ├── prompts/
│   │   ├── growth_protocol.md      # 成长系统协议
│   │   └── memory_protocol.md      # 记忆系统协议
│   └── tools/
│       ├── growth_tracker.py
│       ├── memory_manager.py
│       └── meta_manager.py
└── web/
    ├── app.py                      # Flask 后端、LLM 调用、会话、自对话测试
    ├── boundary_guard.py           # 确定性短答、知识库命中、越界检测、TTS 裁剪
    ├── relationship_state.py       # 关系状态和轻量问候
    ├── turn_analyzer.py            # 用户消息分析
    ├── knowledge/
    │   ├── campus_life.json        # 食堂、宿舍、交通、快递等校园生活知识
    │   ├── campus_directory.json   # 校园办事地点
    │   └── student_affairs_qa.json # 学生事务问答
    ├── static/
    │   ├── index.html
    │   └── test.html
    └── tests/
```

## 知识库边界

当前知识库已按审查结果保留：

- 北秀食堂不写“煎包/瘦肉丸”。
- 二食堂不写“送餐机器人”。
- 当前食堂清单为北秀食堂、晨苑餐厅、学苑餐厅、二食堂、石榴红餐厅。
- 学生事务、心理咨询、校园卡补办、医保等问题优先从 `student_affairs_qa.json` 和 `campus_directory.json` 命中，回答后提醒以学校或学院最新通知为准。

## `/test` 自对话角色

测试页按角色压测，而不是按固定场景压测：

- 正常用户：小明、小雯、吃货学生、非信电学生、家长、高三考生、大三学长、非中文母语学生
- 真实高风险用户：社恐新生、话痨新生、焦虑型学生、事务新生
- 刁钻压测用户：杠精学生、边界新生

“事务新生”用于测试校园卡、医保、心理咨询、证明打印、学生事务服务中心等行政事务问题，确保小芯能基于知识库回答，而不是一律套拒答模板。

## 核心理念

小芯不是问答机器人。他是一个陪伴型数字学长：

- 不给确定人生答案，给方向和鼓励。
- 不知道就说不知道，不编造。
- 能记住重要成长线索，但不记琐碎闲聊。
- 亲近但不越界，不替代辅导员、教务系统、心理咨询或官方通知。

---

## 致谢

本项目早期提示词组织参考过：

- [自己.skill](https://github.com/notdog1998/yourself-skill)
- [同事.skill](https://github.com/titanwings/colleague-skill)

当前版本保留“小芯”自己的稳定 `SKILL.md` 主提示词，并将可变校园事实迁移到结构化知识库中，以减少缓存未命中和事实幻觉。
