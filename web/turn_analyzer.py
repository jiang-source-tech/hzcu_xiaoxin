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
)

_TOPIC_KEYWORDS = {
    "course_rhythm": (
        "课程",
        "上课",
        "课好多",
        "专业课",
        "作业",
        "考试",
        "高数",
        "节奏",
        "跟不上",
        "顶不住",
        "学业",
        "难不难",
        "会不会很难",
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
    ),
    "social_adaptation": (
        "室友",
        "同学",
        "朋友",
        "社交",
        "班级",
        "不合群",
        "融入",
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
        }

    topic = _detect_topic(text)
    memory_worthy, memory_type, memory_content = _memory_for(topic, mood)
    next_hook = _hook_for(topic)
    if topic == "general_checkin":
        next_hook = _preserved_hook_or_neutral(current_state)

    return {
        "stage_signal": stage_signal,
        "mood": mood,
        "topic": topic,
        "memory_worthy": memory_worthy,
        "memory_type": memory_type,
        "memory_content": memory_content,
        "next_hook": next_hook,
        "reply_strategy": _reply_strategy(mood, topic),
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


def _detect_topic(text: str) -> str:
    for topic in (
        "course_rhythm",
        "major_choice",
        "competition_interest",
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
