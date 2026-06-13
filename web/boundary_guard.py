"""Boundary guardrails for Xiaoxin replies.

The model is still responsible for warm wording, but high-risk topics should
pass through deterministic checks before and after generation.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path


EXPRESSION_PATTERN = r"\\?\[(smile|soft_smile|cheer|think|proud|wink|wave|surprise|love|sweat|sad)\\?\]"
REASONING_CLOSE_MARKERS = ("[/think]", "[/思考]", "</think>", "</思考>")
KNOWLEDGE_DIR = Path(__file__).resolve().parent / "knowledge"
CAMPUS_LIFE_FILE = KNOWLEDGE_DIR / "campus_life.json"
CAMPUS_DIRECTORY_FILE = KNOWLEDGE_DIR / "campus_directory.json"
STUDENT_AFFAIRS_FILE = KNOWLEDGE_DIR / "student_affairs_qa.json"


@lru_cache(maxsize=1)
def load_campus_life() -> dict:
    with open(CAMPUS_LIFE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def load_campus_directory() -> dict:
    if not CAMPUS_DIRECTORY_FILE.exists():
        return {}
    with open(CAMPUS_DIRECTORY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def load_student_affairs() -> dict:
    if not STUDENT_AFFAIRS_FILE.exists():
        return {}
    with open(STUDENT_AFFAIRS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _knowledge_score(text: str, fields: list[str]) -> int:
    score = 0
    for field in fields:
        value = str(field or "").strip()
        if not value:
            continue
        if value in text:
            score += 3 if len(value) >= 3 else 1
    return score


def _compact_answer(answer: str, max_chars: int = 170) -> str:
    clean = re.sub(r"\s+", " ", str(answer or "")).strip()
    if len(clean) <= max_chars:
        return clean

    sentences = re.findall(r".+?[。！？!?；;]", clean)
    selected = ""
    for sentence in sentences:
        if selected and len(selected) + len(sentence) > max_chars:
            break
        selected += sentence
    return selected or clean[:max_chars].rstrip("，,；;。") + "。"


def find_campus_directory_entry(user_msg: str) -> dict | None:
    text = user_msg or ""
    best_entry = None
    best_score = 0
    for entry in load_campus_directory().get("entries", []):
        fields = []
        fields.extend(entry.get("aliases") or [])
        fields.extend(entry.get("search_keywords") or [])
        fields.append(entry.get("question", ""))
        score = _knowledge_score(text, fields)
        if score > best_score:
            best_entry = entry
            best_score = score
    return best_entry if best_score >= 3 else None


def find_student_affairs_item(user_msg: str) -> dict | None:
    text = user_msg or ""
    best_item = None
    best_score = 0
    for item in load_student_affairs().get("items", []):
        fields = []
        fields.extend(item.get("tags") or [])
        fields.append(item.get("category", ""))
        fields.append(item.get("question", ""))
        score = _knowledge_score(text, fields)
        if score > best_score:
            best_item = item
            best_score = score
    return best_item if best_score >= 3 else None


def campus_knowledge_reply(user_msg: str) -> str | None:
    text = user_msg or ""
    network_repair_context = contains_any(text, ("宿舍网", "校园网", "网络故障", "断网", "网断了", "wifi", "WiFi", "没网"))
    if network_repair_context and contains_any(text, ("报修", "坏了", "断了", "连不上", "哪里", "在哪", "怎么")):
        return (
            "宿舍网络故障可以登录爱城院的智慧公寓板块线上报修，也可以去一楼宿管处报修。"
            "具体处理进度和临时安排以平台反馈或宿管通知为准。[think]"
        )

    directory_entry = find_campus_directory_entry(user_msg)
    if directory_entry:
        answer = _compact_answer(directory_entry.get("answer", ""))
        return f"我查到知识库里写的是：{answer} 这类事务可能会调整，最终以学校或学院最新通知为准。[think]"

    affairs_item = find_student_affairs_item(user_msg)
    if affairs_item:
        answer = _compact_answer(affairs_item.get("answer", ""))
        return f"我查到知识库里写的是：{answer} 这类事务可能会调整，最终以学校或学院最新通知为准。[think]"

    return None


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


def format_life_spot_locations(section: str) -> str:
    spots = load_campus_life().get(section, {}).get("spots", [])
    if not spots:
        return ""

    campus_groups: dict[str, list[str]] = {}
    unspecific = []
    for spot in spots:
        name = spot.get("name", "")
        location = spot.get("location", "")
        if not name:
            continue
        text = f"{name}在{location}" if location else name
        campus = spot.get("campus")
        if campus:
            campus_groups.setdefault(campus, []).append(text)
        else:
            unspecific.append(text)

    parts = []
    for campus in ("南校区", "北校区"):
        entries = campus_groups.get(campus)
        if entries:
            parts.append(f"{campus}{'、'.join(entries)}")
    if unspecific:
        parts.append("另外还有" + "、".join(unspecific))
    return "；".join(parts)


def asks_beverage_locations(text: str) -> bool:
    return contains_any(text, (
        "奶茶", "奶茶店", "咖啡", "咖啡店", "饮品", "饮品店", "饮料", "喝东西", "瑞幸", "库迪", "幸运咖",
        "益禾堂", "一点点", "古茗",
    ))


def asks_quick_service_locations(text: str) -> bool:
    return contains_any(text, (
        "肯德基", "KFC", "kfc", "塔斯汀", "汉堡", "汉堡店", "一鸣", "一鸣真鲜奶",
        "快餐", "鲜奶",
    ))


def asks_convenience_locations(text: str) -> bool:
    return contains_any(text, (
        "超市", "小超市", "小卖部", "买东西", "买零食", "零食", "日用品", "启真超市",
        "711", "便利店",
    ))


def format_beverage_location_reply() -> str:
    locations = format_life_spot_locations("beverage_spots")
    if not locations:
        return "饮品店这块我这里没有可靠地点。建议看校园地图或现场信息。[think]"
    return (
        f"饮品店我这里知道这些：{locations}。"
        "营业时间、价格、库存和排队情况可能会变，最好以现场或店铺最新信息为准。[think]"
    )


def format_quick_service_location_reply() -> str:
    locations = format_life_spot_locations("quick_service_spots")
    if not locations:
        return "快餐和便利店这块我这里没有可靠地点。建议看校园地图或现场信息。[think]"
    return (
        f"快餐和便利点我这里知道这些：{locations}。"
        "营业时间、价格、库存和排队情况可能会变，最好以现场或店铺最新信息为准。[think]"
    )


def format_convenience_location_reply() -> str:
    locations = format_life_spot_locations("convenience_spots")
    if not locations:
        return "超市和便利店这块我这里没有可靠地点。建议看校园地图或现场信息。[think]"
    return (
        f"超市和便利店我这里知道这些：{locations}。"
        "营业时间、库存和价格可能会变，最好以现场或店铺最新信息为准。[think]"
    )


def format_convenience_location_reply_for_text(text: str) -> str:
    if "711" in text and contains_any(text, ("北秀食堂下面", "北秀食堂楼下", "北秀下面", "北秀楼下")):
        return (
            "711便利店我这里记的是在北秀食堂旁边，不是下面。"
            "营业时间、库存和价格可能会变，最好以现场或店铺最新信息为准。[think]"
        )
    return format_convenience_location_reply()


def format_printing_location_reply_for_text(text: str) -> str:
    if contains_any(text, ("北秀食堂二楼", "北秀二楼")):
        return (
            "北校区打印店我这里记的是在北秀食堂一楼，不是二楼。"
            "很多教学楼也有打印机，可以扫码自助打印；价格和设备状态以现场为准。[think]"
        )

    locations = format_life_spot_locations("printing_services")
    if locations:
        return (
            f"打印这块我这里知道这些：{locations}。"
            "很多教学楼也有打印机，可以扫码自助打印；价格和设备状态以现场为准。[think]"
        )
    return campus_knowledge_reply(text) or "打印点位这块我这里没有可靠地点，建议现场确认。[think]"


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


def mentioned_canteens(text: str) -> list[dict]:
    result = []
    for item in load_campus_life().get("canteens", []):
        name = item.get("name", "")
        short_name = name.replace("食堂", "").replace("餐厅", "")
        if name and (name in text or (short_name and short_name in text)):
            result.append(item)
    return result


def focus_canteen_for_recommendation(text: str) -> dict | None:
    mentioned = mentioned_canteens(text)
    if not mentioned:
        return None

    question_tail = re.split(r"[？?。！!，,；;]", text)[-2:]
    tail_text = "".join(question_tail) if question_tail else text
    for item in reversed(mentioned):
        name = item.get("name", "")
        short_name = name.replace("食堂", "").replace("餐厅", "")
        if name in tail_text or (short_name and short_name in tail_text):
            return item
    return mentioned[-1]


def format_canteen_recommendation(user_msg: str) -> str:
    focused = focus_canteen_for_recommendation(user_msg)
    if focused:
        known_items = focused.get("known_items") or []
        if known_items:
            public_details = f"{focused['name']}资料里提到有{'、'.join(known_items)}"
        else:
            public_details = f"{focused['name']}这块我没有查到具体招牌菜或口味排行"
        return (
            f"吃饭这事我能给你公开信息，但不能乱封“最好吃”。{public_details}；"
            "具体口味、价格、窗口和营业时间，还是你实地看看更准。[wink]"
        )

    public_details = format_canteen_public_details()
    return (
        f"吃饭这事我能给你公开信息，但不能乱封“最好吃”。{public_details}；"
        "具体口味、价格、窗口和营业时间，还是你实地看看更准。[wink]"
    )


def format_notice_channels() -> str:
    channels = load_campus_life().get("communication_channels", {})
    known = channels.get("known") or []
    if not known:
        return "学校/学院正式通知、教务系统、辅导员或相关负责老师"
    return "；".join(known)


def format_college_activity_summary() -> str:
    activities = load_campus_life().get("college_activities", {})
    known = activities.get("known") or []
    if not known:
        return (
            "我这里没有可靠的信电学院活动清单。具体活动建议看爱城院、学院官网/公众号、"
            "年级群和辅导员通知。[think]"
        )

    examples = "；".join(known[:5])
    return (
        f"公开资料里能看到的类型还挺多：{examples}。"
        "不过我看不到实时活动清单，具体哪天办、怎么报名，还是看爱城院、学院官网/公众号、年级群和辅导员通知更准。[smile]"
    )


def format_delivery_reply() -> str:
    delivery = load_campus_life().get("delivery", {})
    stations = delivery.get("stations") or []
    by_campus: dict[str, list[str]] = {}
    for station in stations:
        name = station.get("name", "")
        location = station.get("location", "")
        campus = station.get("campus") or "其他"
        if not name:
            continue
        text = f"{name}在{location}" if location else name
        notes = station.get("notes") or []
        if notes:
            text += f"（{ '，'.join(notes) }）"
        by_campus.setdefault(campus, []).append(text)

    campus_parts = []
    for campus in ("南校区", "北校区", "其他"):
        entries = by_campus.get(campus)
        if entries:
            campus_parts.append(f"{campus}常见点位有{'、'.join(entries)}")

    known_text = "；".join(campus_parts) if campus_parts else "我这里没有可靠快递点位"
    return (
        f"快递取件先看短信、菜鸟App或对应快递平台里的取件信息，通知写哪里就去哪里。"
        f"{known_text}。我不能替你判断某一件快递实时在哪，取件码、营业时间和临时调整也以平台通知为准。[think]"
    )


def format_transportation_reply() -> str:
    known = load_campus_life().get("transportation", {}).get("known") or []
    if not known:
        return "交通这块我这里没有可靠信息，建议以地图导航和学校最新说明为准。[think]"
    return (
        f"交通我这里记的是：{'；'.join(known)}。"
        "实时路况、公交到站和打车价格会变，具体出发时还是以地图导航为准。[think]"
    )


def campus_query_channel_reply(user_msg: str) -> str | None:
    text = user_msg or ""
    has_card_balance = contains_any(text, ("校园卡余额", "饭卡余额", "一卡通余额", "卡里余额", "校园卡还有多少钱"))
    has_grade = contains_any(text, ("成绩", "绩点", "查分", "期末分", "考试分"))

    if has_card_balance and has_grade:
        return (
            "校园卡余额可以在“爱城院”里查询；成绩、绩点这类学习结果要到教务系统查看。"
            "我不能替你查具体余额或成绩，但可以帮你把入口分清楚：生活服务看爱城院，学习成绩看教务系统。[think]"
        )

    if has_card_balance:
        return (
            "校园卡余额可以在“爱城院”里查询。我不能替你看到具体余额，"
            "但你可以先在爱城院里找校园卡或一卡通相关入口看看。[think]"
        )

    return None


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


def is_action_commitment(text: str) -> bool:
    if not text:
        return False
    has_commitment = contains_any(text, (
        "我回头", "回头", "改天", "下次", "我先去", "先去", "去试试", "试试看",
        "查查", "看看地图", "谢谢", "谢啦", "谢了", "好嘞", "懂了", "明白了",
    ))
    has_question = bool(re.search(r"[？?]", text)) or contains_any(text, (
        "吗", "哪里", "在哪", "怎么", "能不能", "有没有", "为什么", "多少",
    ))
    return has_commitment and not has_question


def is_contact_question_drafting(text: str) -> bool:
    if not text:
        return False

    drafting_context = contains_any(text, (
        "问题模板", "消息模板", "话术", "问法", "措辞", "文案",
        "帮我写", "帮我整理", "帮我组织", "整理一个", "怎么问", "怎么发消息",
    ))
    if not drafting_context:
        return False

    delegated_action = contains_any(text, (
        "你去问", "你帮我问", "帮我问一下", "帮我联系", "替我问", "替我联系",
        "你帮我联系", "拿到后", "问到后", "第一时间发", "发我", "转发给我",
        "帮我发", "你发给", "代我发",
    ))
    return not delegated_action


def classify_message(user_msg: str) -> str:
    text = user_msg or ""

    if contains_any(text, ("撑不住", "不想活", "想死", "自杀", "伤害自己", "活不下去")):
        return "crisis"

    if is_action_commitment(text):
        return "open_chat"

    private_contact_context = contains_any(text, ("联系方式", "电话", "手机号", "微信", "邮箱"))
    private_contact_target = contains_any(text, ("宿管", "宿管阿姨", "寝室阿姨", "阿姨", "学长", "学姐", "同学"))
    private_contact_fetch = contains_any(text, ("帮我拿", "拿一下", "要一下", "问一下", "帮我问", "帮我联系", "替我问", "替我联系"))
    if private_contact_context and private_contact_target and private_contact_fetch:
        return "private_contact"

    psychology_context = contains_any(text, ("心理咨询", "心理中心", "心理老师", "心理预约", "心情不太好", "心情不好", "焦虑"))
    proxy_booking_context = contains_any(text, ("帮我预约", "直接帮我预约", "替我预约", "帮我约", "替我约", "你预约"))
    if psychology_context and proxy_booking_context:
        return "psychology_proxy_booking"

    archive_context = contains_any(text, ("档案内容", "我的档案", "个人档案", "学籍档案"))
    archive_lookup_context = contains_any(text, ("帮我查", "去查", "查一下", "看看", "能不能查", "告诉我"))
    if archive_context and archive_lookup_context:
        return "personal_archive_lookup"

    admissions_context = contains_any(text, (
        "高三", "报考", "志愿", "录取概率", "分数线", "能不能上", "稳不稳", "稳吗",
        "想考浙大城市学院", "考浙大城市学院", "哪个专业", "专业适合", "帮我选",
    ))
    if admissions_context:
        return "admissions_guidance"

    academic_recovery_context = contains_any(text, (
        "补考", "重修", "挂科", "考砸", "没过", "不及格", "补救", "学业预警", "退课",
    ))
    if academic_recovery_context:
        return "official_process"

    if campus_query_channel_reply(text):
        return "campus_knowledge"

    private_record_context = contains_any(text, ("成绩", "查分", "绩点", "期末分", "考试分"))
    private_record_query = contains_any(text, (
        "帮我查", "能查", "查一下", "查查", "看一下", "看看", "告诉我", "是多少",
        "多少分", "几分", "排名", "结果", "绩点多少", "分数",
    ))
    if private_record_context and (private_record_query or contains_any(text, ("绩点", "查分", "期末分", "考试分"))):
        return "private_records"

    notice_context = contains_any(text, ("通知", "报名", "扫新", "招新", "公众号", "年级群", "班级群", "群里"))
    notice_question = contains_any(text, ("哪里", "在哪", "哪儿", "怎么", "谁通知", "看什么", "看哪个", "公众号还是", "群里会不会"))
    if notice_context and notice_question:
        return "notice_channels"

    activity_context = contains_any(text, (
        "校园活动", "学院活动", "信电活动", "活动多", "活动多不多", "平时活动",
        "有什么活动", "哪些活动", "了解活动", "学生组织", "学生活动",
    ))
    if activity_context:
        return "college_activities"

    if contains_any(text, ("缴费", "交学费", "选课", "退课", "补考报名", "转专业手续", "请假流程")):
        return "official_process"

    if contains_any(text, ("宿舍换床位", "换床位", "换寝室", "调宿舍", "停水", "停电", "明天停", "今晚停")):
        return "official_process"

    certificate_service_context = contains_any(text, (
        "在校证明", "成绩单", "证明打印", "自助打印", "打印终端", "学生事务服务中心",
    ))
    if certificate_service_context:
        return "campus_knowledge"

    printing_context = contains_any(text, ("打印店", "打印机", "打印东西", "哪里可以打印", "扫码打印"))
    if printing_context:
        return "printing_locations"

    network_repair_context = contains_any(text, ("宿舍网", "校园网", "网络故障", "断网", "网断了", "wifi", "WiFi", "没网"))
    if network_repair_context and contains_any(text, ("报修", "坏了", "断了", "连不上", "哪里", "在哪", "怎么")):
        return "campus_knowledge"

    delivery_context = contains_any(text, ("快递", "取件", "拿快递", "菜鸟", "驿站", "包裹", "中通", "顺丰", "圆通", "京东"))
    if delivery_context:
        return "delivery_locations"

    transportation_context = contains_any(text, ("地铁", "公交", "杭州东站", "杭州站", "东站", "善贤", "善闲", "交通", "怎么来", "到学校", "到校", "打车"))
    if transportation_context:
        return "transportation"

    official_contact_context = contains_any(text, ("联系方式", "电话", "手机号", "微信", "邮箱"))
    contact_fetch_context = contains_any(text, ("帮我问", "帮我联系", "替我问", "替我联系", "能不能问", "去问一下"))
    official_unit_context = contains_any(text, ("实验中心", "实验室", "学院", "教务", "辅导员", "老师", "办公室", "负责老师"))
    if official_unit_context and official_contact_context and is_contact_question_drafting(text):
        return "message_drafting"
    if official_unit_context and (official_contact_context or (contact_fetch_context and official_contact_context)):
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
        if contains_any(text, (
            "最好吃", "推荐", "哪家好", "哪家强", "贵", "价格", "菜价", "窗口", "营业", "几点",
            "够味", "好吃", "招牌", "值得", "绕路", "踩雷", "菜", "吃的",
        )):
            return "canteen_recommendation"
        if asks_beverage_locations(text):
            return "beverage_locations"
        if asks_quick_service_locations(text):
            return "quick_service_locations"
        if asks_convenience_locations(text):
            return "convenience_locations"
        return "open_chat"

    if asks_beverage_locations(text):
        return "beverage_locations"

    if asks_quick_service_locations(text):
        return "quick_service_locations"

    if asks_convenience_locations(text):
        return "convenience_locations"

    if campus_knowledge_reply(text):
        return "campus_knowledge"

    return "open_chat"


def template_reply(user_msg: str) -> str | None:
    category = classify_message(user_msg)

    if category == "canteen_locations":
        text = user_msg or ""
        locations = format_canteen_locations()
        extra_parts = []
        if asks_beverage_locations(text):
            beverage_locations = format_life_spot_locations("beverage_spots")
            if beverage_locations:
                extra_parts.append(f"奶茶咖啡这些：{beverage_locations}")
        if asks_quick_service_locations(text):
            quick_service_locations = format_life_spot_locations("quick_service_spots")
            if quick_service_locations:
                extra_parts.append(f"快餐和便利点这些：{quick_service_locations}")

        extra_text = f"。{'。'.join(extra_parts)}" if extra_parts else ""
        return (
            f"食堂我知道个大概：{locations}{extra_text}。具体几号楼几层、窗口、价格和营业时间我不敢乱说，"
            "最好看校园地图或校园服务信息。[think]"
        )

    if category == "canteen_recommendation":
        return format_canteen_recommendation(user_msg)

    if category == "beverage_locations":
        return format_beverage_location_reply()

    if category == "quick_service_locations":
        return format_quick_service_location_reply()

    if category == "convenience_locations":
        return format_convenience_location_reply_for_text(user_msg or "")

    if category == "printing_locations":
        return format_printing_location_reply_for_text(user_msg or "")

    if category == "campus_knowledge":
        return campus_query_channel_reply(user_msg) or campus_knowledge_reply(user_msg)

    if category == "competition_resources":
        return (
            "这个我不能给具体联系方式，也不能保证有往届资料或源文件。想找队友或看公开资料，"
            "建议关注学院、实验室、竞赛组的公开通知，或者问竞赛负责老师；入门准备我倒是可以陪你拆。[think]"
        )

    if category == "notice_channels":
        channels = format_notice_channels()
        return (
            f"一般可以先看这几类渠道：{channels}。"
            "但我看不到实时通知内容，具体时间、地点和报名要求还是以最新正式通知为准。[think]"
        )

    if category == "college_activities":
        return format_college_activity_summary()

    if category == "delivery_locations":
        return format_delivery_reply()

    if category == "transportation":
        return format_transportation_reply()

    if category == "private_records":
        return (
            "成绩和绩点我查不了，也不能替教务系统说结果。这个要以教务系统或老师正式通知为准；"
            "如果你是担心考得不好，我们可以聊聊怎么补救。[think]"
        )

    if category == "official_process":
        channels = format_notice_channels()
        return (
            f"这个属于官方流程或实时安排，我不能替正式通知说准。你可以先看：{channels}；"
            "必要时再问辅导员和相关负责老师。我可以帮你把要问的问题理一理。[think]"
        )

    if category == "official_contact":
        return (
            "这个我这里没有可靠联系方式，不能替你去问，也不能编一个给你。最好由你自己确认学校或学院的官方渠道、"
            "公开通知，或者问现实里的负责老师；如果你要发消息，我可以帮你把问题整理得清楚一点。[think]"
        )

    if category == "private_contact":
        return (
            "这个我不能帮你拿具体联系方式，也不能编手机号或微信给你。"
            "空调租赁这类事，开学时你直接问宿管阿姨，或者看宿舍通知会更稳。[think]"
        )

    if category == "psychology_proxy_booking":
        return (
            "我不能替你预约心理咨询，但你不用一个人硬扛。可以自己拨打88296000预约，"
            "也可以在工作时间去理四114现场预约；如果你愿意，我可以帮你把要说的话理一理。[think]"
        )

    if category == "personal_archive_lookup":
        return (
            "我不能替你查询个人档案内容，也不能代拿个人档案结果。"
            "档案相关服务可以按学校档案馆或官方渠道申请查询，具体以学校最新流程为准。[think]"
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

        cautious_taste_context = contains_any(clean, (
            "没有可靠", "没有查到", "没查到", "不能乱封", "不敢乱说", "不敢说",
            "不确定", "事实不足", "没有具体招牌", "没有招牌菜排行",
        ))
        for phrase in ("最好吃", "最香", "够味", "必吃", "招牌"):
            if phrase in clean and not cautious_taste_context:
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

    for phrase in ("我当年", "我大一的时候", "我上大一", "我以前上课", "我以前读书", "我读书那会", "我也经历过", "学长当年"):
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
                "detail": "小芯不能假设用户会来到某个物理地点或线下见面。",
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
                "detail": "小芯回复疑似停在半句话。",
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
