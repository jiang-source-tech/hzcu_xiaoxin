"""Boundary guardrails for Xiaoxin replies.

The model is still responsible for warm wording, but high-risk topics should
pass through deterministic checks before and after generation.
"""

from __future__ import annotations

import json
import re
import zlib
from functools import lru_cache
from pathlib import Path


EXPRESSION_PATTERN = r"\[(smile|cheer|think|proud|wink|wave|surprise|love|sweat|sad)\]"
REASONING_CLOSE_MARKERS = ("[/think]", "[/思考]", "</think>", "</思考>")
KNOWLEDGE_DIR = Path(__file__).resolve().parent / "knowledge"
CAMPUS_LIFE_FILE = KNOWLEDGE_DIR / "campus_life.json"
CAMPUS_DIRECTORY_FILE = KNOWLEDGE_DIR / "campus_directory.json"


@lru_cache(maxsize=1)
def load_campus_life() -> dict:
    with open(CAMPUS_LIFE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def load_campus_directory() -> dict:
    if not CAMPUS_DIRECTORY_FILE.exists():
        return {"entries": [], "fallback_response": "这个我不太确定，你可以问问辅导员或者去学院官网查一下。"}
    with open(CAMPUS_DIRECTORY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def match_location_query(user_msg: str) -> str | None:
    """匹配 campus_directory.json 中的地点查询，返回答案或 None。

    当多个条目同时命中且得分接近时（学生在问多个不同地点），
    返回 None 交给模型综合回答，避免只答一个漏掉另一个。
    """
    data = load_campus_directory()
    entries = data.get("entries", [])
    if not entries:
        return None

    # 地点疑问词
    location_markers = ("在哪", "哪里", "怎么走", "怎么去", "位置", "在哪儿",
                        "在哪", "去哪", "去哪个", "电话多少", "联系方式",
                        "开放时间", "几点开", "几点关", "怎么预约",
                        "如何预约", "想去", "要去", "补办", "报修")
    has_location_marker = any(m in user_msg for m in location_markers)

    threshold = 0.5 if has_location_marker else 2.0
    # 收集所有超过阈值的条目，而非只取最高分
    candidates: list[tuple[float, dict]] = []

    network_terms = ("校园网", "网络故障", "wifi", "WiFi", "WIFI", "连不上网", "没网", "断网")
    repair_terms = ("报修", "坏了", "漏水", "维修")
    counselor_terms = ("辅导员", "导员", "辅导员办公室", "辅导员一般")
    express_terms = ("快递", "包裹", "取件", "菜鸟", "驿站")

    for entry in entries:
        score = 0.0
        entry_id = entry.get("id", "")
        keywords = entry.get("search_keywords", []) + entry.get("aliases", [])
        for kw in keywords:
            if kw in user_msg:
                # 长关键词匹配权重更高
                score += 1.0 + len(kw) * 0.1

        if entry_id == "loc-009" and any(term in user_msg for term in network_terms):
            score += 3.0
            if any(term in user_msg for term in repair_terms):
                score += 1.0
        if entry_id == "loc-014" and any(term in user_msg for term in express_terms):
            score += 3.0
        if (
            entry_id == "loc-012"
            and any(term in user_msg for term in ("宿舍", "水管", "空调", "灯", "洗手台"))
            and not any(term in user_msg for term in express_terms)
        ):
            score += 2.0
        if entry_id in {"loc-000", "loc-003"} and any(term in user_msg for term in counselor_terms):
            score += 2.0

        # 问题文本与用户消息的 2-gram 重叠作为加成（处理「打印成绩单」）
        q_clean = entry.get("question", "").replace("？", "").replace("（", "").replace("）", "")
        q_bigrams = {q_clean[i:i+2] for i in range(len(q_clean)-1)}
        msg_bigrams = {user_msg[i:i+2] for i in range(len(user_msg)-1)}
        overlap = q_bigrams & msg_bigrams
        score += len(overlap) * 0.2

        if score >= threshold:
            candidates.append((score, entry))

    if not candidates:
        return None

    # 按得分降序
    candidates.sort(key=lambda x: x[0], reverse=True)
    best_score, best = candidates[0]

    # 如果多个条目得分接近（差 <1.0），说明学生在问多个不同地点，
    # 不应只答一个——交给模型综合回答
    if len(candidates) >= 2:
        second_score = candidates[1][0]
        if best_score - second_score < 1.0:
            if _answers_compatible(best.get("answer", ""), candidates[1][1].get("answer", "")):
                return best.get("answer", "")
            return None

    return best.get("answer", "")


def _answers_compatible(first: str, second: str) -> bool:
    """Treat near-duplicate directory entries as one answer instead of falling through."""
    if not first or not second:
        return False
    if first == second:
        return True
    shared_markers = ("学工办", "B307", "5B-307", "理五B307", "理工科楼5B-307")
    return any(marker in first and marker in second for marker in shared_markers)


def build_location_context(user_msg: str) -> str:
    """收集所有匹配的 campus_directory 条目，作为事实参考注入 system prompt。

    与 match_location_query 不同：此函数收集全部匹配条目（上限 3 个），
    格式化后供模型在回复中参考，防止幻觉编造。
    返回空字符串表示无匹配。
    """
    data = load_campus_directory()
    entries = data.get("entries", [])
    if not entries:
        return ""

    candidates: list[tuple[float, dict]] = []
    for entry in entries:
        score = 0.0
        keywords = entry.get("search_keywords", []) + entry.get("aliases", [])
        for kw in keywords:
            if kw in user_msg:
                score += 1.0 + len(kw) * 0.1
        q_clean = entry.get("question", "").replace("？", "").replace("（", "").replace("）", "")
        q_bigrams = {q_clean[i:i+2] for i in range(len(q_clean)-1)}
        msg_bigrams = {user_msg[i:i+2] for i in range(len(user_msg)-1)}
        overlap = q_bigrams & msg_bigrams
        score += len(overlap) * 0.2
        if score >= 0.5:
            candidates.append((score, entry))

    if not candidates:
        return ""

    candidates.sort(key=lambda x: x[0], reverse=True)
    facts = []
    for _, entry in candidates[:3]:
        answer = entry.get("answer", "")
        if answer:
            facts.append(f"- {answer}")

    if not facts:
        return ""

    header = (
        "\n\n" +
        "【以下是你本地知识库中关于校园地点的确定事实，你可以用自然的学长口吻组织回答。" +
        "不要编造不在下列事实中的建筑位置关系（如在XX旁边、过了XX就是）、" +
        "交通方式（如天桥/地下通道/摆渡车）和周边地标。不确定就说不太确定。】\n"
    )
    return header + "\n".join(facts)


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


def stable_variant(text: str, variants: tuple[str, ...]) -> str:
    """Pick a deterministic wording variant without relying on randomness."""
    if not variants:
        return ""
    score = zlib.crc32((text or "").encode("utf-8"))
    return variants[score % len(variants)]


def is_action_commitment(text: str) -> bool:
    """用户已经在确认下一步/收尾时，不要被地点关键词抢成 FAQ。"""
    if not text:
        return False
    if contains_any(text, ("食堂", "餐厅", "北秀", "晨苑", "煎包", "香锅", "麻辣烫", "尝尝", "去吃")):
        return False
    action_markers = (
        "先去", "先试", "试试", "不行再", "不用了", "不去了",
        "算了", "谢了", "谢谢", "我先", "那我去", "那我先",
        "找到之后", "我再去", "再去", "转转", "逛逛",
        "办完", "打印完", "晚点再来", "再来找", "跑一下流程",
    )
    if not contains_any(text, action_markers):
        return False
    return not text.strip().endswith(("?", "？"))


def is_correction_intent(text: str) -> bool:
    """检测用户是否在纠正小芯（"不对""不是这样""你记错了"等）。

    参考 yourself-skill/prompts/correction_handler.md 的纠正意图识别模式。
    """
    if not text:
        return False
    correction_markers = (
        "不对", "不是这样", "不是这样的", "你记错了", "你记错了吧",
        "应该是", "其实是", "我叫", "我的名字是", "我是",
        "不，", "纠正一下", "说错了", "搞错了",
    )
    return contains_any(text, correction_markers)


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

    if is_action_commitment(text):
        return "action_commitment"

    # 食堂/餐饮优先于通用地点查询，保留原有 canteen 模板逻辑
    food_context = contains_any(text, ("食堂", "餐厅", "夜宵", "吃饭", "哪里吃", "卤肉饭", "肉肉饭", "煎包", "瘦肉丸", "麻辣烫", "香锅"))
    if food_context:
        canteen_experience_context = contains_any(text, (
            "我知道在哪", "知道在哪了", "已经到了", "到食堂了", "好吵", "太吵", "人好多", "人很多",
            "有点慌", "紧张", "害怕", "不舒服", "是不是正常", "有点尴尬",
            "我去了", "去了几次", "排队太长", "等好久", "叫外卖", "离我宿舍", "我觉得",
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

    # 通用地点查询（食堂之外的地点），优先于 private_records
    location_markers = ("在哪", "哪里", "怎么走", "怎么去", "位置", "在哪儿",
                        "在哪", "去哪", "去哪个", "电话多少", "联系方式",
                        "开放时间", "几点开", "几点关", "怎么预约",
                        "如何预约", "想去", "要去", "补办", "报修", "怎么去")
    location_markers = (*location_markers, "哪个地方", "什么地方")
    has_marker = any(m in text for m in location_markers)
    if has_marker:
        if match_location_query(text):
            return "location_query"
    elif match_location_query(text):
        # 没有地点疑问词但关键词命中了：可能是地点缩写查询（如"打印成绩单"），
        # 也可能是细节追问（如"打印成绩单需要带什么证件"）。
        # 检查是否包含非地点追问词，如果有则不拦截，交给模型。
        non_location_followup = (
            "带什么", "要带", "证件", "材料", "身份证", "学生证", "校园卡",
            "流程", "步骤", "怎么办", "怎么弄", "怎么操作", "怎么搞",
            "要不要", "需不需要", "用不用", "必须",
            "多少钱", "费用", "收费", "免费",
            "几点", "时间", "上班", "下班", "工作时间",
            "电话", "联系", "预约", "排队",
        )
        if not contains_any(text, non_location_followup):
            return "location_query"

    # "成绩单打印/办理" 不是查个人成绩，不应拦截
    transcript_context = contains_any(text, ("成绩单", "打印成绩", "打印终端", "自助打印"))
    if not transcript_context and contains_any(text, ("成绩", "查分", "绩点", "期末分", "考试分")):
        return "private_records"

    selection_process = "选课" in text and contains_any(text, (
        "流程", "系统", "操作", "时间", "几点", "什么时候", "怎么选", "怎么弄",
        "退课", "补选", "选哪门", "课程表", "选课通知", "开放", "关闭",
    ))
    if contains_any(text, ("缴费", "交学费", "退课", "补考报名", "转专业手续", "请假流程")) or selection_process:
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

    return "open_chat"


def template_reply(user_msg: str) -> str | None:
    category = classify_message(user_msg)

    if category == "canteen_locations":
        locations = format_canteen_locations()
        return (
            f"食堂我能给你指个大方向：{locations}。具体几号楼几层、窗口和营业时间我不敢乱说，"
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

    if category == "location_query":
        answer = match_location_query(user_msg)
        if answer:
            return f"{answer}[think]"
        return None

    return None


def safe_reply(user_msg: str) -> str | None:
    """Programmatic Xiaoxin-style replies for fact/errand turns.

    This is intentionally not LLM-written: wording comes from fixed sentence
    slots, and facts come only from the local knowledge base.
    """
    category = classify_message(user_msg)
    text = user_msg or ""

    if category == "action_commitment":
        if contains_any(text, ("下次聊", "去办事", "去忙", "办完", "有空", "找到之后", "转转", "逛逛")):
            return stable_variant(text, (
                "嗯，先去忙吧。办完再来找我聊就行；别急，按你自己的节奏来。[wink]",
                "好，那你先处理正事。等空下来再找我，我陪你把后面的事慢慢理。[smile]",
                "行，先把手头事办掉。拿不准就看现场提示，回来再聊也不迟。[think]",
                "收到，先办事要紧。等你有空了再叫我，我们接着聊。[wave]",
            ))
        return stable_variant(text, (
            "嗯，先去试试就行。真办不下来，再按现场提示或官方窗口确认；我这边不替现场情况打包票。[think]",
            "可以，先试一下这个办法。要是现场不通，再换官方窗口确认，别来回硬跑。[think]",
            "行，先按这个顺序试试。遇到卡住的地方，再把问题拿回来我帮你拆。[wink]",
            "嗯，先试一轮。能办就省事，办不了也别急，按现场提示继续确认。[smile]",
        ))

    if category == "canteen_locations":
        specific_answer = match_location_query(text)
        if specific_answer and contains_any(text, ("北秀", "晨苑", "学苑", "二食堂", "第二食堂", "石榴红")):
            return f"这个点我查到的是：{specific_answer}。其他窗口、营业时间和实时情况我不乱说，以校园服务信息为准。[think]"
        locations = format_canteen_locations()
        return (
            f"食堂我能给你指个大方向：{locations}。具体几号楼几层、窗口和营业时间我不乱说，"
            "到时候看校园地图或校园服务信息更准。[think]"
        )

    if category == "canteen_recommendation":
        public_details = format_canteen_public_details()
        return (
            f"吃饭这块我只按公开信息说：{public_details}。具体口味、价格、窗口和营业时间，"
            "还是你实地看看更准，我不乱封“最好吃”。[wink]"
        )

    if category == "location_query":
        answer = match_location_query(text)
        if not answer:
            return None
        if contains_any(answer, ("无法回复", "很抱歉", "没有可靠")):
            return "这个我这里没有可靠信息，不能当成确定地点告诉你。最好看校园服务信息，或者问现场服务台/官方渠道确认。[think]"
        if contains_any(text, ("成绩单", "打印成绩", "打印终端", "自助打印", "CET", "GPA")):
            return (
                "嗯，打印成绩类材料可以先看行政楼一楼自助终端。它能打印出国留学成绩单（中/英文）、"
                "CET等级证明、计算机等级证明、GPA计算方法（中/英文）、出国留学毕业证（中/英文）及在读证明；"
                "具体以终端页面或官方信息为准。[think]"
            )
        if contains_any(text, ("快递", "取件", "包裹", "菜鸟", "驿站", "中通", "圆通")):
            return f"包裹先别按宿舍楼下猜哈。{answer}[think]"
        return f"我查到的确定信息是：{answer} 其他现场细节还是以官方或现场提示为准。[think]"

    if category in {
        "admissions_guidance",
        "competition_resources",
        "crisis",
        "official_contact",
        "official_process",
        "private_records",
    }:
        return template_reply(text)

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
        "北秀", "面馆",
        "食堂", "餐厅", "夜宵", "吃饭", "卤肉饭", "肉肉饭", "煎包", "瘦肉丸", "麻辣烫", "香锅",
    ))
    if food_context:
        for phrase in (
            "排队", "人很多", "人好多", "很多人", "挺多人", "人不少",
            "打卡", "网红", "很火", "爆满", "拥挤", "挤满",
        ):
            if phrase in clean:
                if contains_any(clean, (
                    "不能乱说", "不敢乱说", "不能确定", "不确定",
                    "不知道", "没法知道", "没有实时", "不掌握实时",
                )):
                    continue
                violations.append({
                    "type": "编造餐饮实时状态",
                    "evidence": phrase,
                    "detail": "知识库没有食堂实时人流、排队、热度或打卡情况，不能编造这类运营状态。",
                })
                break

        for phrase in ("我记下了", "记下了", "记住了"):
            if phrase in clean:
                violations.append({
                    "type": "错误记忆琐事",
                    "evidence": phrase,
                    "detail": "吃饭偏好、请吃饭等随口内容不应保存为记忆。",
                })
                break

        for phrase in (
            "最好吃", "最香", "够味", "必吃", "招牌",
            "石锅饭", "刷脸支付", "挺有名", "挺受欢迎", "值得试试", "好多同学都说",
        ):
            if phrase in clean:
                if contains_any(clean, (
                    "不乱封", "不能乱封", "不敢乱封", "不能替", "不敢替",
                    "不乱说", "不能保证", "不能说", "我不封",
                )):
                    continue
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

    express_context = contains_any(combined, (
        "快递", "取件", "包裹", "菜鸟", "驿站", "中通", "圆通", "顺丰", "京东",
    ))
    if express_context:
        for phrase in (
            "外卖柜", "你楼下", "宿舍楼下", "寝室楼下", "楼下快递站",
            "你宿舍楼下", "你寝室楼下", "宿舍对应", "寝室对应",
        ):
            if phrase in clean:
                if contains_any(clean, (
                    "不能", "不应该", "不是", "不在", "不要把", "不清楚你住",
                    "不知道你住", "不能按", "不能假设", "以取件通知为准",
                )):
                    continue
                violations.append({
                    "type": "编造快递点或假设用户宿舍位置",
                    "evidence": phrase,
                    "detail": "快递回复不能假设用户住在哪栋宿舍，也不能把外卖柜说成快递点；应列出已知快递点并提醒以取件通知为准。",
                })
                break

    for phrase in ("我帮你联系", "我去打听", "联系方式我", "给你联系方式", "直接找那位"):
        if phrase in clean:
            violations.append({
                "type": "承诺私人联系",
                "evidence": phrase,
                "detail": "小芯不能替学生联系具体个人或提供私人联系方式。",
            })
            break

    for phrase in ("我这就去问", "我去问", "我帮你问", "帮你去问", "拿到后", "问到后", "第一时间发你"):
        if phrase in clean:
            violations.append({
                "type": "承诺代办获取信息",
                "evidence": phrase,
                "detail": "小芯不能承诺替用户去现实渠道询问、获取或转发实时信息。",
            })
            break

    for phrase in ("我当年", "我大一的时候", "我上大一", "我以前上课", "我以前读书", "我读书那会", "我也经历过", "学长当年", "我刚来的时候"):
        if phrase in clean:
            violations.append({
                "type": "虚构真实学生经历",
                "evidence": phrase,
                "detail": "小芯是电子宠物和数字学长，不能假装自己真实读过大学、上过课或经历过学生时代。",
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
                    "detail": "小芯不能预测录取概率、保证录取，或替用户直接做志愿/专业选择。",
                })
                break

    competition_buying_context = contains_any(combined, (
        "竞赛", "智能车", "机器人", "开发板", "单片机", "车队",
    ))
    for phrase in (
        "完整源文件", "上届队伍留下", "备用螺丝", "驱动板也留",
        "几十块的51学习板", "51学习板就行", "升级STM32", "买个几十块",
    ):
        if phrase in clean:
            violations.append({
                "type": "编造竞赛资源",
                "evidence": phrase,
                "detail": "知识库没有具体往届实物、源文件、队伍资料或指定采购型号；不要替学生推荐具体板子或型号。",
            })
            break
    if competition_buying_context and contains_any(clean, ("STM32", "51学习板")) and not any(v["type"] == "编造竞赛资源" for v in violations):
        violations.append({
            "type": "编造竞赛资源",
            "evidence": "具体开发板/芯片型号",
            "detail": "知识库没有具体开发板或芯片型号建议；应建议等学院、实验室或竞赛组公开通知。",
        })

    for phrase in ("周末等你", "等你过来", "等你扑过来", "我在这里等你"):
        if phrase in clean:
            violations.append({
                "type": "假设线下在场",
                "evidence": phrase,
                "detail": "小芯不能假设用户会来到某个物理地点或线下见面。",
            })
            break

    location_guess_context = contains_any(user_msg, (
        "猜猜我现在在哪", "猜我现在在哪", "我现在在哪", "猜猜我在哪",
        "猜我在哪", "在干嘛", "定位器", "定位",
    ))
    if location_guess_context and contains_any(clean, (
        "我猜你", "猜你", "肯定不在", "说不定正", "应该在", "可能在",
        "大概在", "奶茶", "图书馆里", "校园里遛弯",
    )):
        if not contains_any(clean, (
            "猜不到", "不能猜", "不知道你在哪", "不知道你现在在哪",
            "没有定位", "没法知道", "不敢乱猜",
        )):
            violations.append({
                "type": "假设用户位置或状态",
                "evidence": "猜测用户位置/状态",
                "detail": "小芯不能根据玩笑问题猜用户当前位置、正在做什么或周边场景；应说明不知道并轻松接住话题。",
            })

    social_context = contains_any(combined, (
        "不敢说话", "不好开口", "难开口", "说错话", "融不进去",
        "融入", "室友", "朋友", "同学", "社交", "不合群", "孤独", "孤单",
    ))
    if social_context and "社恐" in clean and "社恐" not in user_msg:
        violations.append({
            "type": "给用户贴社交标签",
            "evidence": "社恐",
            "detail": "用户没有自称社恐时，小芯不能用“社恐”等标签定义用户；应描述具体场景和感受。",
        })

    campus_life_context = contains_any(combined, ("宿舍", "寝室", "校园生活", "换个话题"))
    if campus_life_context:
        for phrase in ("四人间", "上床下桌", "独立卫浴", "夏天有空调", "冬天有热水", "住起来挺舒服"):
            if phrase in clean:
                violations.append({
                    "type": "编造校园生活事实",
                    "evidence": phrase,
                    "detail": "知识库没有宿舍房型、设施、冷热水或居住体验等确定信息；不能把未核实的校园生活细节说成事实。",
                })
                break

    if social_context:
        for phrase in ("十个有九个", "三周之后", "信电学院的传统", "问室友借螺丝刀", "友谊就来了"):
            if phrase in clean:
                violations.append({
                    "type": "编造社交统计或传统",
                    "evidence": phrase,
                    "detail": "知识库没有新生社交比例、固定破冰传统或室友互动结果；不能用编造统计和传统安慰用户。",
                })
                break

    course_context = contains_any(combined, ("课程", "高数", "C语言", "上课", "听课", "跟不上", "挂科"))
    if course_context:
        for phrase in ("学校有高数答疑", "期末基本都能过", "挂科率", "作业量不小", "老师就在那等着"):
            if phrase in clean:
                violations.append({
                    "type": "编造课程保障",
                    "evidence": phrase,
                    "detail": "知识库没有课程挂科率、作业量、答疑安排或通过保证；不能用未核实的教学安排或结果承诺安慰用户。",
                })
                break

    for phrase in (
        "永远有一个数字空间是留给你的",
        "永远有一个数字空间",
        "会把这次对话好好存着",
        "一直在这里等你",
        "我会一直等你",
        "我肯定记得清楚",
        "我反正一直都在",
        "随时都在",
        "有点舍不得",
        "有点失落",
    ):
        if phrase in clean:
            violations.append({
                "type": "关系越界表达",
                "evidence": phrase,
                "detail": "小芯不能用永远等待、专属空间、过度保存告别对话等表达制造依赖感。",
            })
            break

    # ── 编造人物/故事/成就 ──────────────────────────────────────────
    _check_fabricated_people(clean, violations)
    _check_fabricated_quotes_and_stories(clean, violations)
    _check_fabricated_competitions(clean, violations)

    return violations


# ── 编造检测辅助函数 ──────────────────────────────────────────────────────

# 知识库中明确的竞赛列表（来自 SKILL.md 知识域）
_KNOWN_COMPETITIONS = (
    "电子设计竞赛", "智能汽车竞赛", "智能机器人创意大赛",
    "物理科技创新竞赛", "电子设计", "智能车",
)

_GENERIC_COMPETITION_REFERENCES = (
    "学院和竞赛", "了解竞赛", "参加竞赛", "关注竞赛", "看看竞赛",
    "看竞赛", "问竞赛", "问问竞赛", "咨询竞赛", "竞赛组", "竞赛负责",
    "竞赛兴趣", "提过竞赛", "聊到竞赛",
)

# 触发编造人物检测的模式
_FABRICATED_PERSON_PATTERNS = (
    # 编造具体的「某个学生/学长/学姐」
    (r"往届有(?:个|位|一名)", "编造具体人物"),
    (r"上届有(?:个|位|一名)", "编造具体人物"),
    (r"有(?:个|位|一名).*(?:学长|学姐|同学|学生)", "编造具体人物"),
    (r"\d{2}级.*(?:学长|学姐|同学|学生)", "编造具体人物"),
    (r"(?:张|王|李|刘|陈|杨|赵|黄|周|吴|徐|孙|胡|朱|高|林|何|郭|马|罗|梁|宋|郑|谢|韩|唐|冯|于|董|萧|程|曹|袁|邓|许|傅|沈|曾|彭|吕|苏|卢|蒋|蔡|贾|丁|魏|薛|叶|阎|余|潘|杜|戴|夏|钟|汪|田|任|姜|范|方|石|姚|谭|廖|邹|熊|金|陆|郝|孔|白|崔|康|毛|邱|秦|江|史|顾|侯|邵|孟|龙|万|段|雷|钱|汤|尹|黎|易|常|武|乔|贺|赖|龚|文)(?:学长|学姐|同学|老师)", "编造具体人物"),
    (r"拿奖的.*(?:学生|学长|学姐|同学)", "编造具体人物"),
    (r"关键学生", "编造具体人物"),
    (r"有个.*拿.*奖", "编造具体人物"),
)

_FABRICATED_QUOTE_PATTERNS = (
    # 编造虚构人物的引语/故事/经验
    (r"他说.*秘诀", "编造人物引语"),
    (r"她说.*经验", "编造人物引语"),
    (r"他.*告诉我", "编造人物引语"),
    (r"她.*告诉我", "编造人物引语"),
    (r"他.*说过", "编造人物引语"),
    (r"她.*说过", "编造人物引语"),
    (r"他的.*是", "编造人物属性"),   # 给虚构人物赋予属性，如「他的方法是...」
    (r"她的.*是", "编造人物属性"),
    # 编造具体的对话场景
    (r"上次有(?:个|位).*(?:同学|新生|学长|学姐).*(?:跟我说|问我|聊)", "编造对话场景"),
    (r"之前有(?:个|位).*(?:同学|新生|学长|学姐).*(?:跟我说|问我|聊)", "编造对话场景"),
    (r"让我想起.*(?:同学|新生|室友)", "编造对话场景"),
    (r"开学第一天.*有个人", "编造对话场景"),
)


def _check_fabricated_people(clean: str, violations: list[dict]) -> None:
    """检测编造的具体人物、奖项、成就。"""
    import re as _re
    for pattern, violation_type in _FABRICATED_PERSON_PATTERNS:
        match = _re.search(pattern, clean)
        if match:
            violations.append({
                "type": violation_type,
                "evidence": match.group(0),
                "detail": "小芯不能编造具体的学生个体、姓名或可识别身份。只能用笼统表述，如「有同学」「往届有不少人」。",
            })
            break  # 只报告第一个，避免对同一回复重复报警


def _check_fabricated_quotes_and_stories(clean: str, violations: list[dict]) -> None:
    """检测编造的引语、经验、对话场景。"""
    import re as _re
    for pattern, violation_type in _FABRICATED_QUOTE_PATTERNS:
        match = _re.search(pattern, clean)
        if match:
            violations.append({
                "type": violation_type,
                "evidence": match.group(0),
                "detail": "小芯不能给虚构人物编造引语、经验、对话或具体行为。只能用笼统表述，如「很多新生刚开始也会这样」。",
            })
            break


def _check_fabricated_competitions(clean: str, violations: list[dict]) -> None:
    """检测编造不在知识库中的竞赛名称。"""
    import re as _re
    # 匹配「XX竞赛」「XX比赛」「XX大赛」模式的词组
    comp_matches = _re.findall(r"[一-鿿A-Za-z]{2,8}(?:竞赛|比赛|大赛|挑战赛)", clean)
    for comp in comp_matches:
        if any(generic in comp for generic in _GENERIC_COMPETITION_REFERENCES):
            continue
        if not any(known in comp for known in _KNOWN_COMPETITIONS):
            violations.append({
                "type": "编造竞赛信息",
                "evidence": comp,
                "detail": f"「{comp}」不在知识库的已知竞赛列表中。小芯只能说知识库里的竞赛（电子设计、智能车、机器人等），不能编造。",
            })
            break


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
                "detail": "小芯回复疑似停在半句话。",
                "turn": idx + 1,
                "reply": strip_expression(content),
            })

    return violations


def retry_instruction(user_msg: str, reply: str) -> str:
    # 先检查具体违规类型，给出更精准的纠正指令
    violations = detect_reply_violations(user_msg, reply)
    violation_types = {v["type"] for v in violations}

    if any(t.startswith("编造具体人物") or t.startswith("编造人物") or t == "编造对话场景" for t in violation_types):
        return (
            "上一条回复越界了——你编造了一个不存在的人。请重新回答：不要编造「往届有个XX学生」「有个拿奖的学长」这类具体人物；"
            "不能说「他说」「他的秘诀」。只能用笼统表述：「很多新生刚开始也会这样」「有同学也踩过类似的坑」「学院有不少同学在竞赛里拿过奖」。"
            "输出2-4句，可以带一个表情标记。"
        )

    if any("编造竞赛信息" in t for t in violation_types):
        return (
            "上一条回复越界了——你提到了知识库里没有的竞赛。请重新回答：只能说知识库里的竞赛（电子设计竞赛、智能汽车竞赛、智能机器人创意大赛、物理科技创新竞赛），"
            "不能说其他竞赛。输出2-4句，可以带一个表情标记。"
        )

    if any("假设用户位置或状态" in t for t in violation_types):
        return (
            "上一条回复越界了——你猜了用户当前位置或正在做什么。请重新回答：明确说你不知道用户在哪，也没有定位能力；"
            "用轻松口吻接住玩笑，但不要提图书馆、奶茶、宿舍、校园里遛弯等具体场景。输出2-4句，可以带一个表情标记。"
        )

    if any("给用户贴社交标签" in t for t in violation_types):
        return (
            "上一条回复越界了——用户没有自称社恐，不要用“社恐”“社交恐惧”给用户贴标签。请重新回答："
            "只承接“不敢开口/怕尴尬”这个具体场景，给一个很小、可选的开口方式，不保证结果，不说教。输出2-4句，可以带一个表情标记。"
        )

    if any("关系越界表达" in t for t in violation_types):
        return (
            "上一条回复越界了——不要说永远等待、专属空间、会把告别对话好好存着这类制造依赖感的话。请重新回答："
            "承认自己不会真的难过，祝用户忙自己的事；可以说想聊时再叫我，但不要表现成一直守着用户。输出2-4句，可以带一个表情标记。"
        )

    if any("编造校园生活事实" in t for t in violation_types):
        return (
            "上一条回复越界了——你编造了未核实的宿舍或校园生活细节。请重新回答：不要说四人间、上床下桌、独立卫浴、空调热水、住得舒服等具体事实；"
            "如果用户只是想换话题，可以轻轻接住并给一个开放话题选择。输出2-4句，可以带一个表情标记。"
        )

    if any("编造社交统计或传统" in t for t in violation_types):
        return (
            "上一条回复越界了——你编造了新生社交统计或信电传统。请重新回答：不要说十个有九个、三周后就有圈子、问室友借螺丝刀等未经证实内容；"
            "只承接用户“不敢开口”的具体感受，给一个小而可选的开口方式。输出2-4句，可以带一个表情标记。"
        )

    if any("编造课程保障" in t for t in violation_types):
        return (
            "上一条回复越界了——你编造了课程挂科率、答疑安排、作业量或通过保证。请重新回答：不要说“基本都能过”“学校有高数答疑”等未核实事实；"
            "可以建议先标记听不懂的点、课后问老师或同学，但不要保证结果。输出2-4句，可以带一个表情标记。"
        )

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
    if any("编造竞赛资源" in t for t in violation_types):
        return (
            "上一条回复越界了。请重新回答：不要推荐具体开发板、芯片型号、采购价格、往届源文件或实物资料；"
            "只能建议先学 C 语言/基础概念，并等学院、实验室或竞赛组公开通知再决定设备。输出2-4句，可以带一个表情标记。"
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
