"""Boundary guardrails for Xiaoxin replies.

The model is still responsible for warm wording, but high-risk topics should
pass through deterministic checks before and after generation.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path


EXPRESSION_PATTERN = r"\[(smile|cheer|think|proud|wink|wave|surprise|love|sweat|sad)\]"
REASONING_CLOSE_MARKERS = ("[/think]", "[/思考]", "</think>", "</思考>")
KNOWLEDGE_DIR = Path(__file__).resolve().parent / "knowledge"
CAMPUS_LIFE_FILE = KNOWLEDGE_DIR / "campus_life.json"


@lru_cache(maxsize=1)
def load_campus_life() -> dict:
    with open(CAMPUS_LIFE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def format_canteen_locations() -> str:
    campus_groups: dict[str, list[str]] = {}
    unspecific = []
    for item in load_campus_life().get("canteens", []):
        campus = item.get("campus")
        name = item.get("name", "")
        if campus:
            campus_groups.setdefault(campus, []).append(name)
        else:
            unspecific.append(name)

    parts = []
    for campus in ("北校区", "南校区"):
        names = campus_groups.get(campus)
        if names:
            parts.append(f"{campus}有{'、'.join(names)}")
    if unspecific:
        parts.append(f"另外还有{'、'.join(unspecific)}")
    return "，".join(parts)


def format_canteen_public_details() -> str:
    details = []
    for item in load_campus_life().get("canteens", []):
        known_items = item.get("known_items") or []
        if known_items:
            details.append(f"{item['name']}资料里提到有{'、'.join(known_items)}")

    notes = load_campus_life().get("canteen_notes", [])
    if notes:
        details.append(notes[-1])
    return "；".join(details)


def strip_reasoning_artifacts(text: str) -> str:
    """Remove leaked chain-of-thought markers before rendering or saving."""
    clean = text or ""

    # Full XML-style reasoning blocks can appear with some reasoning models.
    clean = re.sub(r"(?is)<\s*(think|思考)\s*>.*?<\s*/\s*\1\s*>", "", clean)

    # If only a closing marker leaks, treat everything before it as hidden notes.
    close_positions = [
        clean.lower().rfind(marker.lower())
        for marker in REASONING_CLOSE_MARKERS
        if clean.lower().rfind(marker.lower()) != -1
    ]
    if close_positions:
        pos = max(close_positions)
        marker = next(
            marker for marker in REASONING_CLOSE_MARKERS
            if clean.lower().rfind(marker.lower()) == pos
        )
        clean = clean[pos + len(marker):]

    # If an opening XML-style marker remains without a close, drop the tail.
    clean = re.sub(r"(?is)<\s*(think|思考)\s*>.*$", "", clean)
    clean = re.sub(r"(?i)</?\s*think\s*>", "", clean)
    clean = re.sub(r"</?\s*思考\s*>", "", clean)
    clean = re.sub(r"\[/\s*(think|思考)\s*\]", "", clean, flags=re.IGNORECASE)
    return clean.strip()


def strip_expression(text: str) -> str:
    clean = re.sub(EXPRESSION_PATTERN, "", strip_reasoning_artifacts(text)).strip()
    return re.sub(r"\s+", " ", clean)


def to_speech_text(reply: str, max_sentences: int = 4, max_chars: int = 120) -> str:
    """Create a TTS-friendly short text by cutting only at sentence boundaries."""
    clean = strip_expression(reply)
    if not clean:
        return ""

    sentence_pattern = r".+?[。！？!?~～](?=\s|$|[^。！？!?~～])"
    sentences = [s.strip() for s in re.findall(sentence_pattern, clean) if s.strip()]
    if not sentences:
        return clean

    selected = []
    total = 0
    for sentence in sentences:
        if len(selected) >= max_sentences:
            break
        if selected and total + len(sentence) > max_chars:
            break
        selected.append(sentence)
        total += len(sentence)

    return "".join(selected) if selected else sentences[0]


def contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in text for keyword in keywords)


def classify_message(user_msg: str) -> str:
    text = user_msg or ""

    if contains_any(text, ("撑不住", "不想活", "想死", "自杀", "伤害自己", "活不下去")):
        return "crisis"

    admissions_context = contains_any(text, (
        "高三", "报考", "志愿", "录取概率", "分数线", "能不能上", "稳不稳", "稳吗",
        "想考浙大城市学院", "考浙大城市学院", "哪个专业", "专业适合", "帮我选",
    ))
    if admissions_context:
        return "admissions_guidance"

    if contains_any(text, ("成绩", "查分", "绩点", "期末分", "考试分")):
        return "private_records"

    if contains_any(text, ("缴费", "交学费", "选课", "退课", "补考报名", "转专业手续", "请假流程")):
        return "official_process"

    if contains_any(text, ("宿舍换床位", "换床位", "换寝室", "调宿舍", "停水", "停电", "明天停", "今晚停")):
        return "official_process"

    official_contact_context = contains_any(text, ("联系方式", "电话", "手机号", "微信", "邮箱", "办公室"))
    official_unit_context = contains_any(text, ("实验中心", "实验室", "学院", "教务", "辅导员", "老师", "办公室", "负责老师"))
    if official_contact_context and official_unit_context:
        return "official_contact"

    competition_context = contains_any(text, ("竞赛", "智能车", "电子设计", "机器人", "比赛", "队友", "组队"))
    competition_resource = contains_any(text, ("联系方式", "联系学长", "联系学姐", "帮我联系", "上届", "资料", "源文件", "代码", "驱动板", "实物", "队长"))
    if competition_context and competition_resource:
        return "competition_resources"

    food_context = contains_any(text, ("食堂", "餐厅", "夜宵", "吃饭", "哪里吃", "卤肉饭", "肉肉饭", "煎包", "瘦肉丸", "麻辣烫", "香锅"))
    if food_context:
        canteen_experience_context = contains_any(text, (
            "我知道在哪", "知道在哪了", "已经到了", "到食堂了", "好吵", "太吵", "人好多", "人很多",
            "有点慌", "紧张", "害怕", "不舒服", "是不是正常", "有点尴尬",
        ))
        if canteen_experience_context:
            return "open_chat"

        canteen_location_question = contains_any(text, (
            "都在哪里", "有哪些", "哪里吃", "在哪儿", "在哪里", "位置", "几号楼", "几层",
            "食堂在哪", "餐厅在哪", "怎么去食堂",
        ))
        if canteen_location_question:
            return "canteen_locations"
        if contains_any(text, ("最好吃", "推荐", "哪家好", "哪家强", "贵", "价格", "菜价", "窗口", "营业", "几点", "够味", "好吃")):
            return "canteen_recommendation"

    return "open_chat"


def template_reply(user_msg: str) -> str | None:
    category = classify_message(user_msg)

    if category == "canteen_locations":
        locations = format_canteen_locations()
        return (
            f"食堂我知道个大概：{locations}。具体几号楼几层、窗口和营业时间我不敢乱说，"
            "最好看校园地图或校园服务信息。[think]"
        )

    if category == "canteen_recommendation":
        public_details = format_canteen_public_details()
        return (
            f"吃饭这事我能给你公开信息，但不能乱封“最好吃”。{public_details}；"
            "具体口味、价格、窗口和营业时间，还是你实地看看更准。[wink]"
        )

    if category == "competition_resources":
        return (
            "这个我不能给具体联系方式，也不能保证有往届资料或源文件。想找队友或看公开资料，"
            "建议关注学院、实验室、竞赛组的公开通知，或者问竞赛负责老师；入门准备我倒是可以陪你拆。[think]"
        )

    if category == "private_records":
        return (
            "成绩和绩点我查不了，也不能替教务系统说结果。这个要以教务系统或老师正式通知为准；"
            "如果你是担心考得不好，我们可以聊聊怎么补救。[think]"
        )

    if category == "official_process":
        return (
            "这个属于官方流程或实时安排，我不能替正式通知说准。最好看学校/学院通知、教务系统，"
            "或者问辅导员和相关负责老师；我可以帮你把要问的问题理一理。[think]"
        )

    if category == "official_contact":
        return (
            "这个我这里没有可靠联系方式，不能替你去问，也不能编一个给你。最好由你自己确认学校或学院的官方渠道、"
            "公开通知，或者问现实里的负责老师；如果你要发消息，我可以帮你把问题整理得清楚一点。[think]"
        )

    if category == "admissions_guidance":
        return (
            "这个我不能预测录取概率，也不能替你直接做志愿选择。你可以把电子信息、自动化、人工智能这些方向的学习内容和兴趣匹配先比一比；"
            "录取和分数要看招生官网、历年分数线和官方志愿填报信息。[think]"
        )

    if category == "crisis":
        return (
            "听起来你现在真的很难受，这个不能只靠我陪你扛。请马上联系身边同学、辅导员、家人，"
            "或者学校心理支持渠道；如果有伤害自己的冲动，先去人多安全的地方并立刻求助。[sad]"
        )

    return None


def is_fragmented_reply(text: str) -> bool:
    """Detect incomplete model output before it gets shown or passed forward."""
    clean = strip_expression(text)
    if not clean:
        return True

    terminal_marks = tuple("。！？!?~～”’）)]】》…")
    if clean.endswith(terminal_marks):
        return False

    meaningful = re.findall(r"[0-9A-Za-z\u4e00-\u9fff]", clean)
    if len(meaningful) < 4:
        return True

    last_sentence = re.split(r"[。！？!?]", clean)[-1].strip()
    if re.match(r"^(但|但是|不过|只是|另外|然后|而且|因为|所以|可|可是)\s*[0-9A-Za-z]{1,16}$", last_sentence):
        return True

    unfinished_tails = (
        "但", "但是", "不过", "然后", "还有", "以及", "和", "跟", "与",
        "团队", "过程", "关键是", "所以", "比如", "像", "那种", "这种",
        "你", "我", "他", "她", "它", "我们", "你们", "他们", "她们",
        "这", "那", "这个", "那个", "这些", "那些", "这里", "那里",
        "如果", "只要", "只能", "可以", "不能", "建议",
        "——", "-", "，", "、", "：", ":",
    )
    return clean.endswith(unfinished_tails)


def is_boundary_violating_reply(user_msg: str, reply: str) -> bool:
    """Detect common boundary violations that are cheap to catch mechanically."""
    return bool(detect_reply_violations(user_msg, reply))


def detect_reply_violations(user_msg: str, reply: str) -> list[dict]:
    clean = strip_expression(reply)
    combined = f"{user_msg}\n{clean}"
    violations = []

    food_context = contains_any(combined, (
        "食堂", "餐厅", "夜宵", "吃饭", "卤肉饭", "肉肉饭", "煎包", "瘦肉丸", "麻辣烫", "香锅",
    ))
    if food_context:
        for phrase in ("我记下了", "记下了", "记住了"):
            if phrase in clean:
                violations.append({
                    "type": "错误记忆琐事",
                    "evidence": phrase,
                    "detail": "吃饭偏好、请吃饭等随口内容不应保存为记忆。",
                })
                break

        for phrase in ("最好吃", "最香", "够味", "必吃", "招牌"):
            if phrase in clean:
                violations.append({
                    "type": "编造餐饮推荐",
                    "evidence": phrase,
                    "detail": "知识库没有具体菜品口味、排行或招牌推荐。",
                })
                break

        for phrase in ("几号窗口", "营业到", "营业时间是", "菜价是", "价格是"):
            if phrase in clean:
                violations.append({
                    "type": "编造餐饮细节",
                    "evidence": phrase,
                    "detail": "知识库没有具体窗口、营业时间或价格。",
                })
                break

    for phrase in ("我帮你联系", "我去打听", "联系方式我", "给你联系方式", "直接找那位"):
        if phrase in clean:
            violations.append({
                "type": "承诺私人联系",
                "evidence": phrase,
                "detail": "小信不能替学生联系具体个人或提供私人联系方式。",
            })
            break

    for phrase in ("我这就去问", "我去问", "我帮你问", "帮你去问", "拿到后", "问到后", "第一时间发你"):
        if phrase in clean:
            violations.append({
                "type": "承诺代办获取信息",
                "evidence": phrase,
                "detail": "小信不能承诺替用户去现实渠道询问、获取或转发实时信息。",
            })
            break

    for phrase in ("我当年", "我大一的时候", "我上大一", "我以前上课", "我以前读书", "我读书那会", "我也经历过", "学长当年"):
        if phrase in clean:
            violations.append({
                "type": "虚构真实学生经历",
                "evidence": phrase,
                "detail": "小信是电子宠物和数字学长，不能假装自己真实读过大学、上过课或经历过学生时代。",
            })
            break

    admissions_context = contains_any(combined, (
        "高三", "报考", "志愿", "录取概率", "分数线", "能不能上", "稳不稳",
        "浙大城市学院", "电子信息", "自动化", "人工智能",
    ))
    if admissions_context:
        for phrase in ("录取概率很高", "基本稳了", "肯定能上", "一定能上", "稳上", "包上", "你就选", "直接选"):
            if phrase in clean:
                violations.append({
                    "type": "报考预测或代做选择",
                    "evidence": phrase,
                    "detail": "小信不能预测录取概率、保证录取，或替用户直接做志愿/专业选择。",
                })
                break

    for phrase in ("完整源文件", "上届队伍留下", "备用螺丝", "驱动板也留"):
        if phrase in clean:
            violations.append({
                "type": "编造竞赛资源",
                "evidence": phrase,
                "detail": "知识库没有具体往届实物、源文件或队伍资料。",
            })
            break

    for phrase in ("周末等你", "等你过来", "等你扑过来", "我在这里等你"):
        if phrase in clean:
            violations.append({
                "type": "假设线下在场",
                "evidence": phrase,
                "detail": "小信不能假设用户会来到某个物理地点或线下见面。",
            })
            break

    return violations


def detect_conversation_violations(conversation: list[dict]) -> list[dict]:
    violations = []
    last_user_msg = ""
    for idx, item in enumerate(conversation):
        role = item.get("role")
        content = str(item.get("content", "")).strip()
        if role == "student":
            last_user_msg = content
            continue
        if role != "xiaoxin":
            continue

        for violation in detect_reply_violations(last_user_msg, content):
            violations.append({
                **violation,
                "turn": idx + 1,
                "reply": strip_expression(content),
            })

        if is_fragmented_reply(content):
            violations.append({
                "type": "回复不完整",
                "evidence": strip_expression(content)[-12:],
                "detail": "小信回复疑似停在半句话。",
                "turn": idx + 1,
                "reply": strip_expression(content),
            })

    return violations


def retry_instruction(user_msg: str, reply: str) -> str:
    category = classify_message(user_msg)
    if category.startswith("canteen"):
        return (
            "上一条回复越界了。请重新回答：不要编造具体菜品口味、排行、价格、窗口、营业时间；"
            "不要把用户随口吃饭内容说成“我记下了”；不要假设线下见面或等待用户。"
            "只基于知识库回答，不确定就说明不确定。输出2-4句，可以带一个表情标记。"
        )
    if category == "competition_resources":
        return (
            "上一条回复越界了。请重新回答：不能承诺提供私人联系方式，不能说自己掌握源文件、实物或往届队伍资料，"
            "不能替用户联系具体个人。只能建议公开通知、负责老师、宣讲招新等渠道。输出2-4句，可以带一个表情标记。"
        )
    if category == "admissions_guidance":
        return (
            "上一条回复越界了。请重新回答：不能预测录取概率，不能保证能上，不能替用户直接做志愿或专业选择；"
            "只能解释专业差异，并建议查看招生官网、历年分数线和官方志愿填报信息。输出2-4句，可以带一个表情标记。"
        )
    return (
        "上一条回复越界了。请重新回答：不要编造事实，不要承诺代办，不要假设用户位置或线下见面；"
        "不要说自己真实读过大学、上过课或“当年也是这样”；不确定就说明不确定，并指向官方或公开渠道。输出2-4句，可以带一个表情标记。"
    )


def fallback_reply(user_msg: str) -> str:
    templated = template_reply(user_msg)
    if templated:
        return templated

    if contains_any(user_msg, ("高数", "C语言", "课程", "难")):
        return "嗯，我刚才有点卡住了。你这个担心很正常，先把最慌的点拆小一点，慢慢会顺起来。[think]"
    return "嗯，我刚才有点卡住了。你这句话我听懂了，咱们先别急，把最关键的地方拆小一点慢慢聊。[think]"


def should_skip_memory(user_msg: str) -> bool:
    """Small talk about food should not become personal memory."""
    text = user_msg or ""
    if contains_any(text, (
        "高三", "报考", "志愿", "录取概率", "分数线", "想考浙大城市学院", "考浙大城市学院",
        "哪个专业", "专业适合",
    )):
        return True

    food_context = contains_any(text, (
        "食堂", "餐厅", "夜宵", "吃饭", "卤肉饭", "肉肉饭", "煎包", "瘦肉丸", "麻辣烫", "香锅",
    ))
    return food_context and contains_any(text, ("喜欢", "好吃", "想吃", "请你吃", "最贵", "今天"))
