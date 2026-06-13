from __future__ import annotations

import re


TOPIC_LABELS = {
    "course_rhythm": "课程节奏",
    "major_choice": "专业理解",
    "competition_interest": "竞赛兴趣",
    "social_adaptation": "人际适应",
    "campus_life": "校园生活",
    "family_concern": "家长沟通",
    "general_checkin": "近况",
}

_STAGE_SIGNALS = {"early_freshman", "pre_enrollment", "prospective"}


_EARLY_FRESHMAN_PATTERNS = [
    r"已经开学",
    r"开学了",
    r"刚开学",
    r"第一周",
    r"第[一1]周课",
    r"开始上课",
    r"上课了",
    r"课好多",
]

_PRE_ENROLLMENT_PATTERNS = [
    r"录取",
    r"通知书",
    r"报到",
    r"预报到",
    r"入学前",
    r"还没开学",
    r"准备开学",
]

_CRISIS_KEYWORDS = (
    "不想活",
    "自杀",
    "轻生",
    "伤害自己",
    "活不下去",
    "撑不住",
    "撑不下去",
)

_FRUSTRATED_KEYWORDS = (
    "烦",
    "别聊",
    "不想聊",
    "别提",
    "受够",
    "火大",
    "讨厌",
)

_ANXIOUS_KEYWORDS = (
    "怕",
    "担心",
    "焦虑",
    "紧张",
    "跟不上",
    "顶不住",
    "压力",
    "慌",
    "难不难",
    "会不会很难",
)

_LONELY_KEYWORDS = (
    "孤独",
    "孤单",
    "没人",
    "一个人",
    "没朋友",
    "不合群",
)

_CURIOUS_KEYWORDS = (
    "好奇",
    "想知道",
    "了解一下",
    "怎么",
    "吗",
    "？",
    "?",
)

_RELAXED_KEYWORDS = (
    "还好",
    "挺好",
    "开心",
    "舒服",
    "轻松",
    "不错",
)

_REFUSAL_KEYWORDS = (
    "别聊",
    "不聊",
    "不想聊",
    "别提",
    "换个话题",
    "不要聊",
    "聊点别的",
    "聊别的",
    "换话题",
    "不讲这个",
)

_TOPIC_KEYWORDS = {
    "course_rhythm": (
        "课程",
        "大学的课",
        "课排",
        "课排得",
        "课挺满",
        "课很多",
        "课不少",
        "课跟",
        "上课",
        "课好多",
        "专业课",
        "作业",
        "考试",
        "高数",
        "C语言",
        "c语言",
        "指针",
        "编程",
        "代码",
        "debug",
        "节奏",
        "跟不上",
        "听不懂",
        "落下",
        "顶不住",
        "学业",
        "难不难",
        "会不会很难",
        "学不会",
    ),
    "major_choice": (
        "专业",
        "信电",
        "转专业",
        "志愿",
        "方向",
        "电子信息",
        "计算机",
    ),
    "competition_interest": (
        "竞赛",
        "比赛",
        "大创",
        "挑战杯",
        "互联网+",
        "数学建模",
        "acm",
        "蓝桥杯",
        "智能车",
        "机器人",
        "开发板",
        "单片机",
        "入门培训",
        "社团纳新",
        "纳新",
        "招新",
        "宣讲",
    ),
    "social_adaptation": (
        "室友",
        "同学",
        "朋友",
        "没什么朋友",
        "别人聊天",
        "别人说什么",
        "大家都不认识",
        "社交",
        "说话",
        "开口",
        "不敢说话",
        "不好开口",
        "难开口",
        "说错话",
        "班级",
        "不合群",
        "融入",
        "融不进去",
        "孤独",
        "孤单",
    ),
    "campus_life": (
        "宿舍",
        "食堂",
        "校园",
        "社团",
        "军训",
        "寝室",
        "图书馆",
        "生活",
    ),
    "family_concern": (
        "爸",
        "妈",
        "父母",
        "家里",
        "家人",
        "想家",
        "家庭",
    ),
}


def analyze(user_msg: str, current_state: dict | None = None) -> dict:
    text = (user_msg or "").strip()
    stage_signal = _detect_stage_signal(text, current_state)
    mood = _detect_mood(text)

    if _is_refusal(text):
        return {
            "stage_signal": stage_signal,
            "mood": mood,
            "topic": "general_checkin",
            "memory_worthy": False,
            "memory_type": None,
            "memory_content": None,
            "next_hook": _deactivated_hook(current_state),
            "reply_strategy": _reply_strategy(mood, "general_checkin"),
            "followup_upsert": None,
            "followup_resolve": None,
        }

    if mood == "crisis":
        return {
            "stage_signal": stage_signal,
            "mood": mood,
            "topic": "general_checkin",
            "memory_worthy": False,
            "memory_type": None,
            "memory_content": None,
            "next_hook": _hook_for("general_checkin", active=True),
            "reply_strategy": _reply_strategy(mood, "general_checkin"),
            "followup_upsert": None,
            "followup_resolve": None,
        }

    if _is_casual_food_ack(text) or _is_general_lonely_disclosure(text, mood):
        hook = _preserved_hook_or_neutral(current_state)
        if _is_general_lonely_disclosure(text, mood):
            hook = _hook_for("general_checkin", active=True)
        return {
            "stage_signal": stage_signal,
            "mood": mood,
            "topic": "general_checkin",
            "memory_worthy": False,
            "memory_type": None,
            "memory_content": None,
            "next_hook": hook,
            "reply_strategy": _reply_strategy(mood, "general_checkin"),
            "followup_upsert": None,
            "followup_resolve": None,
        }

    topic = _detect_topic(text, current_state)
    memory_worthy, memory_type, memory_content = _memory_for(topic, mood)
    next_hook = _hook_for(topic)
    if topic == "general_checkin":
        next_hook = _preserved_hook_or_neutral(current_state)

    followup_upsert = detect_followups(text, mood, topic)
    followup_resolve = detect_resolutions(text)

    return {
        "stage_signal": stage_signal,
        "mood": mood,
        "topic": topic,
        "memory_worthy": memory_worthy,
        "memory_type": memory_type,
        "memory_content": memory_content,
        "next_hook": next_hook,
        "reply_strategy": _reply_strategy(mood, topic),
        "followup_upsert": followup_upsert,
        "followup_resolve": followup_resolve,
    }


def _detect_stage_signal(text: str, current_state: dict | None = None) -> str:
    current = None
    if isinstance(current_state, dict):
        user_stage = current_state.get("user_stage")
        if user_stage in _STAGE_SIGNALS:
            current = user_stage

    if _matches_any(text, _EARLY_FRESHMAN_PATTERNS) and not _is_hypothetical_future_school(text, current):
        return "early_freshman"
    if _matches_any(text, _PRE_ENROLLMENT_PATTERNS):
        if current == "early_freshman":
            return current
        return "pre_enrollment"
    if current:
        return current
    return "prospective"


def _is_hypothetical_future_school(text: str, current: str | None = None) -> bool:
    if current == "early_freshman":
        return False
    future_markers = (
        "如果",
        "假如",
        "万一",
        "到时候",
        "开学后",
        "还没开学",
        "没开学",
    )
    return any(marker in text for marker in future_markers)


def _detect_mood(text: str) -> str:
    if _contains_any(text, _CRISIS_KEYWORDS):
        return "crisis"
    if _is_frustrated(text):
        return "frustrated"
    if _contains_any(text, _ANXIOUS_KEYWORDS):
        return "anxious"
    if _contains_any(text, _LONELY_KEYWORDS):
        return "lonely"
    if _contains_any(text, _CURIOUS_KEYWORDS):
        return "curious"
    if _contains_any(text, _RELAXED_KEYWORDS):
        return "relaxed"
    return "relaxed"


def _detect_topic(text: str, current_state: dict | None = None) -> str:
    current_topic = None
    current_hook_active = False
    if isinstance(current_state, dict):
        current_topic = current_state.get("recent_topic")
        hook = current_state.get("next_hook") or {}
        if isinstance(hook, dict) and hook.get("active"):
            current_topic = hook.get("topic") or current_topic
            current_hook_active = True

    if (
        current_hook_active
        and current_topic == "competition_interest"
        and _contains_any(text, (
            "C语言", "c语言", "开发板", "板子", "单片机", "材料", "入门",
            "练练手", "零基础", "小白", "智能车", "机器人", "教程",
            "资料", "社团纳新", "纳新", "宣讲",
        ))
    ):
        return "competition_interest"

    for topic in (
        "course_rhythm",
        "competition_interest",
        "major_choice",
        "social_adaptation",
        "family_concern",
        "campus_life",
    ):
        if _contains_any(text, _TOPIC_KEYWORDS[topic]):
            return topic
    return "general_checkin"


def _is_refusal(text: str) -> bool:
    if "不是不聊" in text or "不是不想聊" in text:
        return False
    return _contains_any(text, _REFUSAL_KEYWORDS)


def _is_frustrated(text: str) -> bool:
    if "麻烦" in text:
        text = text.replace("麻烦", "")
    if re.search(r"(好烦|很烦|太烦|烦死|烦躁|烦透|别聊|不想聊|别提|受够|火大|讨厌)", text):
        return True
    return False


def _is_casual_food_ack(text: str) -> bool:
    if not text or text.strip().endswith(("?", "？")):
        return False
    food_context = _contains_any(text, ("食堂", "餐厅", "北秀", "晨苑", "煎包", "香锅", "外卖"))
    ack_context = _contains_any(text, ("谢谢", "好嘞", "好呀", "收到", "明天", "回头", "尝尝", "去了几次", "叫外卖"))
    return food_context and ack_context


def _is_general_lonely_disclosure(text: str, mood: str) -> bool:
    if mood not in {"lonely", "anxious"}:
        return False
    return _contains_any(text, (
        "一个人在扛",
        "自己一个人在扛",
        "一个人搞定",
        "自己一个人搞定",
        "想找个人说说",
        "没人能帮我分担",
        "喘不过气",
    ))


def _memory_for(topic: str, mood: str) -> tuple[bool, str | None, str | None]:
    if topic == "course_rhythm" and mood in {"anxious", "frustrated"}:
        return True, "concern", "担心信电课程跟不上"
    return False, None, None


def _hook_for(topic: str, active: bool = True) -> dict:
    return {
        "topic": topic,
        "label": TOPIC_LABELS[topic],
        "active": active,
    }


def _preserved_hook_or_neutral(current_state: dict | None) -> dict:
    current_hook = {}
    if isinstance(current_state, dict):
        current_hook = current_state.get("next_hook") or {}
    if isinstance(current_hook, dict) and current_hook:
        return dict(current_hook)
    return _hook_for("general_checkin", active=False)


def _deactivated_hook(current_state: dict | None) -> dict:
    current_hook = {}
    if isinstance(current_state, dict):
        current_hook = current_state.get("next_hook") or {}

    topic = current_hook.get("topic") if isinstance(current_hook, dict) else None
    if topic not in TOPIC_LABELS:
        topic = "general_checkin"

    label = current_hook.get("label") if isinstance(current_hook, dict) else None
    if not label:
        label = TOPIC_LABELS[topic]

    return {
        "topic": topic,
        "label": label,
        "active": False,
    }


def _reply_strategy(mood: str, topic: str) -> str:
    if mood == "crisis":
        return "crisis_support"
    if mood == "frustrated":
        return "deescalate"
    if mood == "anxious":
        return "reassure_and_ground"
    if mood == "lonely":
        return "companionship"
    if mood == "curious":
        return "answer_with_options"
    if topic == "general_checkin":
        return "light_checkin"
    return "warm_followup"


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(needle.lower() in lowered for needle in needles)


def _matches_any(text: str, patterns: list[str]) -> bool:
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)


# ─── Followup Detection ──────────────────────────────────────────────────

_CONCERN_KEYWORDS = (
    "好难", "太难", "搞不懂", "学不会", "跟不上", "听不懂",
    "不会做", "做不出来", "调不通", "debug", "报错",
    "担心", "害怕", "焦虑", "紧张", "没信心",
    "挂了", "没过", "考砸", "很差", "倒数",
)

_DECISION_KEYWORDS = (
    "要不要", "该不该", "不知道要不要", "纠结", "犹豫",
    "选哪个", "怎么选", "怎么决定", "拿不定",
    "考研还是", "工作还是", "出国还是",
)

_EVENT_KEYWORDS = (
    "期中考试", "期末考试", "面试", "答辩", "比赛",
    "考试周", "ddl", "deadline", "下周", "这周",
)

_RESOLUTION_KEYWORDS = (
    "好多了", "搞懂了", "会了", "懂了", "解决了",
    "不纠结了", "决定了", "想好了", "想通了",
    "考完了", "过了", "上岸了", "拿到offer", "录取了",
    "现在好多了", "终于", "比之前好", "没那么难了",
)

_CONCERN_LABELS = {
    "C语言": "C语言学习",
    "c语言": "C语言学习",
    "指针": "C语言指针",
    "高数": "高数学习",
    "数学": "数学学习",
    "英语": "英语学习",
    "编程": "编程入门",
    "代码": "代码调试",
    "实验": "实验操作",
    "考研": "考研方向",
    "工作": "就业方向",
    "专业方向": "专业选择",
    "竞赛": "竞赛参与",
    "宿舍": "宿舍适应",
    "室友": "室友关系",
    "孤独": "社交融入",
    "跟不上": "课程节奏",
}


def _extract_label(text: str, fallback: str = "近况") -> str:
    """从用户消息中提取关键主题标签。"""
    for keyword, label in _CONCERN_LABELS.items():
        if keyword.lower() in text.lower():
            return label
    cleaned = re.sub(r"[，。！？?；;：:“”\"'（）()\[\]【】…~、]", " ", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if cleaned and len(cleaned) <= 8:
        return cleaned
    return fallback or "近况"


def detect_followups(
    text: str, mood: str, topic: str
) -> dict | None:
    """检测用户消息中值得跟进的内容。

    Returns:
        dict with kind/label/context/intensity, or None.
    """
    if not text:
        return None

    # 决策类：用户在纠结选择
    if _contains_any(text, _DECISION_KEYWORDS):
        label = _extract_label(text, fallback=TOPIC_LABELS.get(topic, "近况"))
        if label and len(label) >= 2:
            return {
                "kind": "decision",
                "label": label,
                "context": text[:100],
                "intensity": "high" if mood in {"anxious", "frustrated"} else "medium",
            }

    # 事件类：即将发生的事
    if _contains_any(text, _EVENT_KEYWORDS) and not _contains_any(text, _RESOLUTION_KEYWORDS):
        label = _extract_label(text, fallback=TOPIC_LABELS.get(topic, "近况"))
        if label:
            return {
                "kind": "event",
                "label": label,
                "context": text[:100],
                "intensity": "medium",
            }

    # 困难类：用户表达了困难/焦虑 + 具体课程/话题
    has_concern_signal = _contains_any(text, _CONCERN_KEYWORDS)
    if has_concern_signal and (topic != "general_checkin" or mood in {"anxious", "frustrated"}):
        label = _extract_label(text, fallback=TOPIC_LABELS.get(topic, "近况"))
        intensity = "high" if mood in {"anxious", "frustrated"} else "medium"
        # 如果是积极情绪中的轻微困难，降低强度
        if mood in {"relaxed", "curious"}:
            intensity = "low"
        if label:
            return {
                "kind": "concern",
                "label": label,
                "context": text[:100],
                "intensity": intensity,
            }

    return None


def detect_resolutions(text: str) -> str | None:
    """检测用户是否暗示某个问题/决策已解决。

    Returns:
        followup label to resolve, or None.
    """
    if not text:
        return None

    if not _contains_any(text, _RESOLUTION_KEYWORDS):
        return None

    # 从消息中提取对应的 label
    label = _extract_label(text)
    if label:
        return label

    return None
