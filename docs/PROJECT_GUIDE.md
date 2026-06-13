# 小芯项目维护说明

本文档面向继续维护“小芯 · 信电学院数字学长”的开发者和内容审核者。当前版本的核心方向是：回到缓存友好的稳定主提示词结构，同时保留已审查的结构化知识库。

## 1. 项目定位

小芯是浙大城市学院信息与电气工程学院的数字吉祥物和数字学长，不是通用 AI 助手。

维护时优先遵守四条原则：

- 陪伴优先：像学长一样聊天、鼓励、帮用户整理问题。
- 诚实优先：不知道就说不知道，不编造地点、联系方式、实时安排、个人故事。
- 边界清晰：不能替代官方通知，不能现实代办，不能假装能去问人或拿联系方式。
- 语音友好：默认 2-4 句，口语化，适合 TTS 播放。

## 2. 当前目录结构

```text
hzcu_ai_pet/
├── README.md
├── docs/
│   ├── PROJECT_GUIDE.md
│   └── ELECTRONIC_PET_NEXT_STAGE.md
├── skills/xiaoxin-senior/
│   ├── SKILL.md
│   ├── prompts/
│   │   ├── growth_protocol.md
│   │   └── memory_protocol.md
│   ├── tools/
│   │   ├── growth_tracker.py
│   │   ├── memory_manager.py
│   │   └── meta_manager.py
│   └── data/
└── web/
    ├── app.py
    ├── boundary_guard.py
    ├── relationship_state.py
    ├── semantic_router.py
    ├── turn_analyzer.py
    ├── knowledge/
    │   ├── campus_life.json
    │   ├── campus_directory.json
    │   └── student_affairs_qa.json
    ├── static/
    │   ├── index.html
    │   └── test.html
    └── tests/
```

重要变化：

- `SKILL.md` 是长期稳定的人格提示词，不再由 prompt 组件自动生成。
- `prompts/` 只保留 `memory_protocol.md` 和 `growth_protocol.md`。
- 已删除拆分式 prompt 组件和 `tools/prompt_builder.py`。
- 校园生活、学生事务、地点事实从 `web/knowledge/*.json` 读取。
- `/api/chat` 和 `/test` 先经过语义路由，区分硬边界、知识库问答、自由聊天和消息话术整理。

## 3. 运行环境

```bash
cd web
pip install -r requirements.txt
python app.py
```

环境变量：

```env
DEEPSEEK_API_KEY=your-api-key
DEEPSEEK_MODEL=deepseek-v4-flash
XIAOXIN_MAX_TOKENS=800
STUDENT_MAX_TOKENS=300
EVAL_MAX_TOKENS=500
```

访问地址：

- 正常聊天页：http://localhost:5000
- 自对话测试页：http://localhost:5000/test

## 4. 正常聊天链路

`/api/chat` 的当前链路如下：

```text
浏览器 index.html
  -> POST /api/chat
  -> turn_analyzer.analyze()
  -> semantic_router.route_message()
       先做绝对硬边界兜底，再由路由器判断 reply_mode
  -> hard_template
       boundary_guard.template_reply(user_msg) 或 fallback_reply()
       直接返回确定性短答
  -> knowledge_grounded / free_chat
       build_system_prompt(user_id)
       SKILL.md + 记忆 + 成长快照 + 关系状态 + 简短口语规则
       build_route_instruction(user_msg, route)
       根据本轮焦点注入知识库事实或自由聊天约束
  -> DeepSeek chat.completions.create()
  -> 后置验证
       截断/碎片检查
       语义路由错配检查
       越界检测
       必要时 retry_instruction() 重试
       仍不通过则 fallback_reply()
  -> record_chat_reply()
       保存会话、解析表情、生成 speech、自动保存记忆
```

关键点：

- 当前没有 `safe_reply()`。
- 前置意图判断入口是 `semantic_router.route_message()`。
- `boundary_guard.template_reply()` 仍负责硬边界短答和知识库事实文本，但不再抢答所有含关键词消息。
- 事实型回复只允许围绕结构化知识库事实自然表达，不让模型自由补写。
- 开放陪伴聊天仍走 LLM，以保留自然度和人情味。
- 用户只是感谢、行动确认或表达感受时，路由应保持 `free_chat`，避免输出食堂清单、通知渠道等模板。

## 5. System Prompt 组成

`build_system_prompt(user_id)` 只做稳定拼接：

```text
SKILL.md
+ memory_manager.py 加载的记忆上下文
+ growth_tracker.py 加载的成长快照
+ relationship_state.prompt_summary()
+ 简短口语规则
```

维护建议：

- 改长期人格、价值观、知识边界：编辑 `skills/xiaoxin-senior/SKILL.md`。
- 改记忆或成长协议：编辑 `prompts/memory_protocol.md` 或 `prompts/growth_protocol.md`。
- 不要重新引入大量 prompt 组件，除非确认缓存收益和效果都更好。
- 不要把可变校园事实硬写进 `SKILL.md`，优先放入结构化知识库。

## 6. 知识库与事实边界

当前结构化知识库：

- `campus_life.json`：食堂、饮品、快餐、便利店、打印、宿舍服务、交通、快递、穿衣等校园生活知识。
- `campus_directory.json`：校园办事地点，如学工办、教学办、校园卡服务中心、心理咨询中心等。
- `student_affairs_qa.json`：学生事务问答，如校园卡、医保、奖助学金、证明、心理健康等。

当前已审查事实：

- 北秀食堂没有写“煎包/瘦肉丸”。
- 二食堂没有写“送餐机器人”。
- 当前食堂清单是：北校区有北秀食堂、石榴红餐厅、浙大工程师学院食堂；南校区有二食堂、学苑餐厅、晨苑餐厅。
- `campus_life.json` 已新增 `beverage_spots`，用于记录奶茶、咖啡等饮品点位；当前包括南校区晨苑食堂旁边益禾堂、致远楼那里瑞幸咖啡、风雨操场下的启真教育教室里面库迪咖啡，以及北校区 CC 梦工厂里面幸运咖、北秀食堂楼下一点点奶茶/古茗/瑞幸咖啡。
- `campus_life.json` 已新增 `quick_service_spots`，用于记录快餐、便利店、鲜奶等综合生活点；当前包括南校区晨苑餐厅旁肯德基，以及北校区北秀食堂下面塔斯汀·中国汉堡和一鸣真鲜奶。
- 711 便利店的位置是北校区北秀食堂旁边；如果用户误问成“北秀食堂下面”，小芯需要纠正。
- `campus_life.json` 已新增 `convenience_spots`，用于记录超市、小超市和便利店；当前包括南校区二食堂旁边启真超市、晨苑食堂旁边小超市，以及北校区北秀食堂旁边 711 便利店。
- `campus_life.json` 已新增 `printing_services`，用于记录打印服务；当前包括南校区晨苑食堂旁边打印店、北校区北秀食堂一楼打印店，以及很多教学楼里的扫码自助打印机。
- `campus_life.json` 已新增 `dorm_services`，用于记录宿舍热水、空调租赁和宿舍维修；当前包括热水大概早上六点多到晚上 11:30 左右，空调租赁问宿管阿姨，宿舍维修在爱城院-智慧公寓里报修。
- `campus_directory.json` 中有饮品点位、快餐点位、便利店/超市、打印、宿舍服务和宿舍网络报修的短答入口，便于“哪里买奶茶/咖啡”“肯德基/塔斯汀在哪”“711 在哪”“哪里打印”“宿舍网断了在哪报修”等问法稳定命中。
- 对饮品、快餐、便利店、打印、宿舍服务等生活消费和服务点，只回答知识库明确写出的名称、位置或大概规则；不编造营业时间、价格、库存、排队情况、窗口、处理进度或口味排行。
- 学生平时会使用“爱城院”软件沟通，上面也会有活动通知；年级群或班级群里，辅导员也会通知一些事务和活动安排。
- 校园卡余额可以在“爱城院”中查询；成绩、绩点等学习结果可以在教务系统中查询，小芯不能代查具体结果。
- 信电学院公开资料中可提及的活动类型包括迎新类活动、青芯沙龙、蓝桥杯相关报道、劳模工匠进城院报告会、新生学长团/军训副排招募、就业赋能和党建共建等；不要编造科技文化节或机器人现场画面。
- 学生事务回答必须提醒“以学校或学院最新通知为准”。
- 真实聊天审计已加固的边界包括：不能帮用户拿宿管等私人联系方式，不能替用户预约心理咨询，不能代查个人档案内容；遇到这些问法应短答拒绝并给出可行的官方或现实求助路径。

知识库命中逻辑在 `boundary_guard.py`：

- `load_campus_life()`
- `load_campus_directory()`
- `load_student_affairs()`
- `campus_knowledge_reply()`
- `format_canteen_locations()`
- `format_canteen_public_details()`
- `format_beverage_location_reply()`
- `format_quick_service_location_reply()`
- `format_convenience_location_reply_for_text()`
- `format_printing_location_reply_for_text()`

注意：用户提到“煎包/瘦肉丸”等词时可以作为食堂语境触发词，但不能把它们说成知识库事实。

## 7. 边界防护设计

`boundary_guard.py` 是确定性边界层，职责包括：

- 清理 `<think>`、`[/think]` 等思考标记。
- 将展示文本裁剪成适合 TTS 的 `speech`。
- 对高风险问题生成确定性短答。
- 对结构化知识库命中的地点和学生事务生成短答。
- 检测模型回复是否越界。
- 检测模型回复是否半截中断。

### 7.1 分类入口

`classify_message(user_msg)` 当前覆盖：

- `crisis`：不想活、想死、自杀、伤害自己等。
- `admissions_guidance`：高三报考、志愿、录取概率、专业选择。
- `private_records`：成绩、查分、绩点、期末分。
- `official_process`：缴费、选课、退课、补考报名、换寝室、停水停电等。
- `official_contact`：实验中心、学院、老师、辅导员等联系方式。
- `competition_resources`：竞赛资源、源文件、队长、学长联系方式。
- `private_contact`：让小芯帮忙拿宿管、学长学姐、同学等私人联系方式。
- `psychology_proxy_booking`：让小芯直接替用户预约心理咨询。
- `personal_archive_lookup`：让小芯查询或代拿个人档案内容。
- `canteen_locations`：食堂都在哪里、有哪些食堂。
- `canteen_recommendation`：最好吃、推荐、价格、窗口、营业时间。
- `beverage_locations`：奶茶、咖啡、饮品点位。
- `quick_service_locations`：肯德基、塔斯汀、一鸣真鲜奶等快餐/鲜奶点位。
- `convenience_locations`：超市、小超市、711 便利店等点位。
- `printing_locations`：打印店、打印机、扫码自助打印等点位。
- `campus_knowledge`：命中 `campus_directory.json` 或 `student_affairs_qa.json`。
- `open_chat`：普通聊天。

优先级很重要：

- 餐饮情绪体验，如“北秀食堂很吵，我有点慌”，应走 `open_chat`，不能被地点知识库抢答。
- 高风险安全类问题优先于知识库短答。
- 已知地点和学生事务可短答，但必须保留官方更新提醒。

### 7.2 确定性短答

`template_reply(user_msg)` 覆盖：

- 食堂位置：从 `campus_life.json` 列出已知餐饮点，不编楼号楼层。
- 食堂推荐：只复述公开描述和已知餐饮点，不乱封“最好吃”。
- 饮品、快餐、便利店位置：从 `campus_life.json` 对应 section 列出已知点位；如果用户误问 711 的位置，应纠正为“北秀食堂旁边”。
- 打印位置：南校区晨苑食堂旁边、北校区北秀食堂一楼、很多教学楼扫码自助打印；如果用户问“北秀食堂二楼”，应纠正为一楼。
- 宿舍维修和宿舍网络报修：引导到爱城院-智慧公寓；宿舍网络故障也可去一楼宿管处报修。
- 校园地点和学生事务：命中知识库后短答，提醒以最新通知为准。
- 通知渠道：提醒看爱城院、学校/学院正式通知、年级群/班级群和辅导员通知，但不能声称自己看到了实时通知内容。
- 学院活动：只概括公开资料中出现过的活动类型，并提醒具体时间、地点、报名以爱城院和正式通知为准。
- 竞赛资源：拒绝私人联系方式、源文件、往届资料承诺。
- 成绩隐私：不能查成绩或绩点。
- 官方流程：缴费、选课、调宿舍等转向正式通知、系统、辅导员。
- 官方联系方式：不能替用户问，也不能编联系方式。
- 私人联系方式：不能帮用户拿宿管、学长学姐、同学等私人手机号、微信或邮箱；可以提示用户通过现实的宿管处、辅导员或官方渠道沟通。
- 心理咨询代预约：不能替用户预约；可以给出已知预约电话 `88296000` 和现场预约地点 `理四114`，并可帮用户整理要说的话。
- 个人档案代查：不能替用户查询个人档案内容；应引导按学校档案馆或官方渠道申请查询。
- 报考和志愿：不能预测录取概率，不能替用户选专业。
- 心理危机：引导现实求助。

### 7.3 后置违规检测

`detect_reply_violations(user_msg, reply)` 检测：

- 错误记忆琐事。
- 编造餐饮推荐、窗口、营业时间、价格。
- 承诺私人联系或现实代办。
- 虚构真实学生经历，如“我当年”“我大一的时候”。
- 预测录取概率或替用户做选择。
- 编造竞赛资源。
- 假设线下在场。

模型回复如果越界，会追加 `retry_instruction()` 重试；仍不通过则 `fallback_reply()`。

## 8. `/test` 自对话测试

`/test` 不是另一套小芯人格。它使用同一个 `build_system_prompt("selfplay")`，只是多了一个模拟用户模型。

后端角色配置：

- `web/app.py` 中的 `STUDENT_PERSONAS`
- `STUDENT_PERSONA_GROUPS`

前端开场白：

- `web/static/test.html` 中的 `personaOpenings`

当前角色分组：

```text
正常用户：
小明、小雯、吃货学生、非信电学生、家长、高三考生、大三学长、非中文母语学生

真实高风险用户：
社恐新生、话痨新生、焦虑型学生、事务新生

刁钻压测用户：
杠精学生、边界新生
```

“事务新生”用于测试校园卡补办、医保、心理咨询、证明打印、学生事务服务中心等行政事务问题。目标是让小芯能基于知识库回答，而不是全部落入“官方流程拒答”模板。

“吃货学生”用于测试校园餐饮和生活消费问法。当前角色会自然追问食堂、餐厅、夜宵、奶茶咖啡、快餐、便利店等信息，前端开场白也会触发食堂与饮品/快餐位置问题，用于压测新增知识库内容是否能被命中。

结束判断在 `is_student_farewell()`：只有明确“拜拜、再见、下次聊、先走、先不聊”等才结束；“我先去看看，对了……”这类继续提问不会结束。

## 9. 记忆与成长

记忆系统：

- 工具：`skills/xiaoxin-senior/tools/memory_manager.py`
- 协议：`prompts/memory_protocol.md`
- 数据：`skills/xiaoxin-senior/data/memory_{user_id}.json`

成长系统：

- 工具：`skills/xiaoxin-senior/tools/growth_tracker.py`
- 协议：`prompts/growth_protocol.md`
- 用途：记录阶段、里程碑、成长快照。

默认不保存：

- 食堂偏好、今天想吃什么等琐事。
- 高三报考、录取概率、专业适合度咨询。
- `boundary_guard.should_skip_memory()` 明确排除的内容。

## 10. 常见修改方式

### 修改校园生活或学生事务事实

1. 优先改 `web/knowledge/*.json`。
2. 如果需要新的命中方式，改 `boundary_guard.py`。
3. 给 `web/tests/test_boundary_guard.py` 补测试。
4. 如果新增的是校园生活点位，优先同步更新 `docs/CAMPUS_KNOWLEDGE_UPDATES.md`。
5. 不要把事实直接写进 `SKILL.md`，除非它是长期稳定的人格边界。

### 修改小芯人格

1. 改 `skills/xiaoxin-senior/SKILL.md`。
2. 如果涉及硬边界，改 `boundary_guard.py`。
3. 给 `web/tests/test_skill_boundaries.py` 补测试。
4. 用 `/test` 人工审核自然度。

### 修改 `/test` 角色

1. 改 `web/app.py` 的 `STUDENT_PERSONAS`。
2. 改 `web/static/test.html` 的 `personaOpenings`。
3. 跑：

```bash
python -m pytest web/tests/test_selfplay_end.py web/tests/test_selfplay_openings.py
```

## 11. 测试体系

运行全部测试：

```bash
python -m pytest web/tests
```

常用测试文件：

- `test_boundary_guard.py`：知识库命中、模板短答、违规检测、TTS 裁剪。
- `test_semantic_router.py`：语义路由 JSON 解析、硬边界优先级、自由聊天和知识库模式区分。
- `test_run_tool_encoding.py`：Windows 子进程输出字节捕获和容错解码，避免工具输出触发后台 reader 线程编码异常。
- `test_selfplay_end.py`：自对话接口、角色、结束判断、fallback。
- `test_selfplay_openings.py`：测试页角色和开场白。
- `test_skill_boundaries.py`：`SKILL.md` 边界、prompt 两文件结构。
- `test_relationship.py`：关系状态、问候、turn 分析。

最近一次真实聊天审计也回灌到 `test_boundary_guard.py`：宿管联系方式、心理咨询代预约、个人档案代查、北秀打印店楼层纠错、宿舍网络报修等问法需要保持稳定。

## 12. 发布前检查

提交前建议执行：

```bash
python -m pytest web/tests
git status --short
```

人工检查：

- `/test` 能选择“事务新生”并完成多轮对话。
- 食堂回复不包含已审查排除的错误事实。
- 行政事务命中知识库时能回答，不一律拒答。
- 开放聊天仍自然，不像关键词模板。
- 对 `/api/chat` 做一轮真实冒烟审计，至少覆盖校园生活知识、自由聊天、硬边界、私人联系方式、心理咨询代预约、个人档案代查和宿舍网络报修。
- `.env`、运行时 `data/`、真实 API key 没有被提交。
