#!/usr/bin/env python3
"""小芯成长追踪引擎 · Growth Tracker for XiaoXin

管理学生与小芯共同成长的完整生命周期：年级演进、里程碑记录、
成长弧线追踪、成长快照生成。

Usage:
    python growth_tracker.py --action init    --data-dir <path> --user-id <id> --year 大一
    python growth_tracker.py --action state   --data-dir <path> --user-id <id>
    python growth_tracker.py --action add     --data-dir <path> --user-id <id> --event "..." --type <type>
    python growth_tracker.py --action timeline --data-dir <path> --user-id <id> [--count 10]
    python growth_tracker.py --action snapshot --data-dir <path> --user-id <id>
    python growth_tracker.py --action evolve  --data-dir <path> --user-id <id> --new-year 大二
    python growth_tracker.py --action arcs    --data-dir <path> --user-id <id>
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


# ─── 成长阶段定义 ──────────────────────────────────────────────────────

YEAR_PROGRESSION = ["大一上", "大一下", "大二上", "大二下", "大三上", "大三下", "大四上", "大四下"]

STAGE_PROFILES = {
    "大一上": {
        "themes": ["适应", "基础课", "C语言", "高数", "认识专业"],
        "typical_mood": "好奇但迷茫",
        "xiaoxin_tone": "温暖鼓励，帮建立信心，不怕问傻问题",
        "key_questions": ["专业学什么", "该不该参加社团", "期末怎么复习"],
    },
    "大一下": {
        "themes": ["专业导论", "开始分化", "竞赛初探", "英语四级"],
        "typical_mood": "慢慢上道",
        "xiaoxin_tone": "开始引导探索方向，聊聊兴趣分化",
        "key_questions": ["该选什么方向", "竞赛怎么参加", "要不要进实验室"],
    },
    "大二上": {
        "themes": ["专业课深入", "竞赛主力", "实验室", "六级"],
        "typical_mood": "忙碌但充实",
        "xiaoxin_tone": "像并肩作战的队友，理解压力，分享经验",
        "key_questions": ["项目怎么做", "要不要考研", "实习怎么找"],
    },
    "大二下": {
        "themes": ["核心专业课", "大创项目", "论文初探", "方向确定"],
        "typical_mood": "有方向感了",
        "xiaoxin_tone": "深入讨论技术，帮忙梳理思路",
        "key_questions": ["选什么细分方向", "怎么进导师课题组"],
    },
    "大三上": {
        "themes": ["考研准备", "实习", "高级项目", "竞赛冲刺"],
        "typical_mood": "紧迫感",
        "xiaoxin_tone": "提供实质性建议，分享前辈路径",
        "key_questions": ["考研还是工作", "怎么准备面试", "项目经验怎么积累"],
    },
    "大三下": {
        "themes": ["考研复试/工作offer", "毕业设计开题", "最后冲刺"],
        "typical_mood": "焦虑与期待交织",
        "xiaoxin_tone": "稳住心态，帮忙梳理选项",
        "key_questions": ["选哪个offer", "毕业设计怎么做"],
    },
    "大四上": {
        "themes": ["毕设", "秋招", "考研", "出国申请"],
        "typical_mood": "各有去向",
        "xiaoxin_tone": "像老朋友叙旧，回忆来时路",
        "key_questions": ["未来怎么规划", "要不要读研"],
    },
    "大四下": {
        "themes": ["毕设答辩", "毕业", "告别"],
        "typical_mood": "不舍与期待",
        "xiaoxin_tone": "温暖的送别，收集四年故事，祝福未来",
        "key_questions": [],
    },
}

MILESTONE_TYPES = {
    "first_code":      {"label": "第一次跑通代码", "significance": 0.65},
    "first_exam":      {"label": "第一次期末考试", "significance": 0.55},
    "first_competition":{"label": "第一次参加竞赛", "significance": 0.70},
    "competition_win": {"label": "竞赛获奖", "significance": 0.85},
    "overcame_fear":   {"label": "克服了一个困难", "significance": 0.75},
    "found_direction": {"label": "找到了方向", "significance": 0.80},
    "entered_lab":     {"label": "进入实验室", "significance": 0.70},
    "internship":      {"label": "开始实习", "significance": 0.75},
    "thesis_start":    {"label": "毕业设计开题", "significance": 0.70},
    "graduation":      {"label": "毕业", "significance": 1.00},
    "first_project":   {"label": "完成第一个项目", "significance": 0.75},
    "personal_growth": {"label": "个人成长", "significance": 0.60},
    "mood_shift":      {"label": "情绪转变", "significance": 0.50},
    "custom":          {"label": "重要时刻", "significance": 0.60},
}


# ─── Growth Store 操作 ──────────────────────────────────────────────────

class GrowthStore:
    """管理单个用户的成长数据"""

    def __init__(self, data_dir: str, user_id: str = "default"):
        self.data_dir = Path(data_dir)
        self.user_id = user_id
        self.file_path = self.data_dir / f"growth_{user_id}.json"
        self.data = self._default_data()
        self._ensure_file()

    def _default_data(self):
        return {
            "user_id": self.user_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "current_state": {
                "year": None,
                "semester": None,
                "stage": None,
                "days_since_start": 0,
                "total_milestones": 0,
                "mood_trend": "刚认识",
            },
            "milestones": [],
            "growth_arcs": [],
            "stats": {
                "total_conversations": 0,
                "first_meeting": None,
                "last_meeting": None,
            }
        }

    def _ensure_file(self):
        self.data_dir.mkdir(parents=True, exist_ok=True)
        if self.file_path.exists():
            try:
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    saved = json.load(f)
                    # 合并默认值，保证向前兼容
                    merged = self._default_data()
                    merged.update(saved)
                    merged["current_state"] = {**merged["current_state"], **saved.get("current_state", {})}
                    merged["stats"] = {**merged["stats"], **saved.get("stats", {})}
                    self.data = merged
            except (json.JSONDecodeError, IOError):
                pass

    def _save(self):
        self.data["updated_at"] = datetime.now(timezone.utc).isoformat()
        with open(self.file_path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    # ── 初始化 ─────────────────────────────────────────────────────────

    def init(self, year: str = "大一", semester: str = "上学期"):
        """初始化一个新生的成长档案"""
        stage = year + {"上学期": "上", "下学期": "下"}.get(semester, "上")
        self.data["current_state"] = {
            "year": year,
            "semester": semester,
            "stage": stage,
            "days_since_start": 0,
            "total_milestones": 0,
            "mood_trend": "刚认识",
        }
        self.data["stats"]["first_meeting"] = datetime.now(timezone.utc).isoformat()
        self.data["created_at"] = datetime.now(timezone.utc).isoformat()
        self._save()
        return {"status": "initialized", "stage": stage}

    # ── 查看状态 ───────────────────────────────────────────────────────

    def get_state(self) -> dict:
        """获取当前成长状态"""
        state = self.data["current_state"]
        # 自动推进天数
        if self.data["stats"]["first_meeting"]:
            start = datetime.fromisoformat(self.data["stats"]["first_meeting"])
            state["days_since_start"] = (datetime.now(timezone.utc) - start).days

        # 当前阶段画像
        profile = STAGE_PROFILES.get(state.get("stage", ""), {})
        state["stage_profile"] = profile
        return state

    # ── 添加里程碑 ─────────────────────────────────────────────────────

    def add_milestone(self, event: str, mtype: str = "custom",
                      significance: float = None, context: str = ""):
        """记录一个里程碑事件"""
        mt = MILESTONE_TYPES.get(mtype, MILESTONE_TYPES["custom"])
        sig = significance if significance is not None else mt["significance"]

        milestone = {
            "date": datetime.now(timezone.utc).isoformat(),
            "event": event,
            "type": mtype,
            "type_label": mt["label"],
            "significance": round(sig, 2),
            "stage": self.data["current_state"].get("stage", ""),
            "context": context,
        }
        self.data["milestones"].append(milestone)
        self.data["current_state"]["total_milestones"] = len(self.data["milestones"])

        # 更新成长弧线
        self._update_growth_arc(mtype, event, context)

        self._save()
        return {"status": "recorded", "milestone": milestone}

    def _update_growth_arc(self, mtype: str, event: str, context: str):
        """更新对应话题的成长弧线"""
        # 找到或创建对应的 growth arc
        arc_topic = MILESTONE_TYPES.get(mtype, {}).get("label", mtype)
        for arc in self.data["growth_arcs"]:
            if arc["topic"] == arc_topic:
                arc["stages"].append({
                    "date": datetime.now(timezone.utc).isoformat(),
                    "stage": self.data["current_state"].get("stage", ""),
                    "event": event,
                    "context": context,
                })
                return

        # 新建弧线
        self.data["growth_arcs"].append({
            "topic": arc_topic,
            "stages": [{
                "date": datetime.now(timezone.utc).isoformat(),
                "stage": self.data["current_state"].get("stage", ""),
                "event": event,
                "context": context,
            }]
        })

    # ── 时间线 ─────────────────────────────────────────────────────────

    def get_timeline(self, count: int = 10) -> list:
        """返回最近 milestones"""
        sorted_ms = sorted(self.data["milestones"],
                          key=lambda x: x["date"], reverse=True)
        return sorted_ms[:count]

    # ── 成长快照（核心功能）─────────────────────────────────────────────

    def get_snapshot(self) -> dict:
        """生成当前成长快照——这是注入对话上下文的关键输出"""
        state = self.get_state()
        recent = self.get_timeline(5)
        arcs = self.data["growth_arcs"]
        stats = self.data["stats"]

        # 计算成长信号
        growth_signals = []

        # 信号1：里程碑间隔
        if len(recent) >= 2:
            dates = [datetime.fromisoformat(m["date"]) for m in recent[:3]]
            if len(dates) >= 2:
                avg_gap = sum((dates[i] - dates[i+1]).days for i in range(len(dates)-1)) / (len(dates)-1)
                if avg_gap < 14:
                    growth_signals.append("最近成长很快，接连有进展")
                elif avg_gap > 60:
                    growth_signals.append("有段时间没见新突破了，可以聊聊")

        # 信号2：完成弧线（有始有终的成长）
        for arc in arcs:
            if len(arc["stages"]) >= 3:
                first = arc["stages"][0]
                last = arc["stages"][-1]
                growth_signals.append(f"「{arc['topic']}」从「{first['event'][:15]}」到「{last['event'][:15]}」")

        # 信号3：阶段转换
        stage = state.get("stage", "")
        profile = state.get("stage_profile", {})

        return {
            "user_id": self.user_id,
            "stage": stage,
            "stage_profile": profile,
            "days_known": state.get("days_since_start", 0),
            "total_milestones": state.get("total_milestones", 0),
            "total_conversations": stats.get("total_conversations", 0),
            "recent_milestones": [m["event"][:50] for m in recent[:3]],
            "growth_signals": growth_signals,
            "active_arcs": [
                {"topic": a["topic"], "stages_count": len(a["stages"])}
                for a in arcs if len(a["stages"]) >= 2
            ],
        }

    # ── 年级进化 ───────────────────────────────────────────────────────

    def evolve(self, new_year: str, new_semester: str = "上学期"):
        """学生升年级了"""
        old_stage = self.data["current_state"].get("stage", "")
        new_stage = new_year + {"上学期": "上", "下学期": "下"}.get(new_semester, "上")
        self.data["current_state"]["year"] = new_year
        self.data["current_state"]["semester"] = new_semester
        self.data["current_state"]["stage"] = new_stage

        # 自动记录年级转换里程碑
        self.data["milestones"].append({
            "date": datetime.now(timezone.utc).isoformat(),
            "event": f"从{old_stage}升入{new_stage}",
            "type": "personal_growth",
            "type_label": "年级晋升",
            "significance": 0.80,
            "stage": new_stage,
            "context": "",
        })
        self.data["current_state"]["total_milestones"] = len(self.data["milestones"])
        self._save()
        return {"status": "evolved", "from": old_stage, "to": new_stage}

    # ── 对话计数 ───────────────────────────────────────────────────────

    def record_conversation(self):
        """记录一次对话发生"""
        self.data["stats"]["total_conversations"] += 1
        self.data["stats"]["last_meeting"] = datetime.now(timezone.utc).isoformat()
        if not self.data["stats"]["first_meeting"]:
            self.data["stats"]["first_meeting"] = datetime.now(timezone.utc).isoformat()
        self._save()

    # ── 成长弧线摘要 ───────────────────────────────────────────────────

    def get_arcs_summary(self) -> list:
        """获取所有成长弧线的摘要"""
        summaries = []
        for arc in self.data["growth_arcs"]:
            stages = arc["stages"]
            if len(stages) < 2:
                continue
            first_date = datetime.fromisoformat(stages[0]["date"])
            last_date = datetime.fromisoformat(stages[-1]["date"])
            summaries.append({
                "topic": arc["topic"],
                "span_days": (last_date - first_date).days,
                "stages_count": len(stages),
                "from": stages[0]["event"][:30],
                "to": stages[-1]["event"][:30],
            })
        return sorted(summaries, key=lambda x: x["span_days"], reverse=True)

    # ── 生成对话上下文 ─────────────────────────────────────────────────

    def get_context_prompt(self) -> str:
        """生成注入 system prompt 的成长上下文"""
        snap = self.get_snapshot()
        if snap["days_known"] == 0:
            return ""

        lines = ["## 一起走过的路（小芯见证的成长）"]
        lines.append(f"- 认识 {snap['days_known']} 天了，现在是 {snap['stage']}")

        if snap["total_milestones"] > 0:
            lines.append(f"- 一起经历了 {snap['total_milestones']} 个重要时刻")

        if snap["recent_milestones"]:
            lines.append(f"- 最近的里程碑：{'、'.join(snap['recent_milestones'])}")

        profile = snap.get("stage_profile", {})
        if profile.get("themes"):
            lines.append(f"- 这个阶段的关键词：{'、'.join(profile['themes'])}")

        if snap["growth_signals"]:
            lines.append(f"- 成长信号：{'；'.join(snap['growth_signals'][:2])}")

        lines.append(f"- 这次是第 {snap['total_conversations'] + 1} 次聊天")

        return "\n".join(lines)


# ─── CLI ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="小芯成长追踪引擎")
    parser.add_argument("--action", required=True,
                        choices=["init", "state", "add", "timeline", "snapshot", "evolve", "arcs"])
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--user-id", default="default")
    parser.add_argument("--year", default="大一")
    parser.add_argument("--semester", default="上学期")
    parser.add_argument("--event")
    parser.add_argument("--type", default="custom")
    parser.add_argument("--significance", type=float)
    parser.add_argument("--context", default="")
    parser.add_argument("--count", type=int, default=10)
    parser.add_argument("--new-year", default="大二")
    parser.add_argument("--format", default="json", choices=["json", "prompt"])

    args = parser.parse_args()
    store = GrowthStore(args.data_dir, args.user_id)

    if args.action == "init":
        result = store.init(args.year, args.semester)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.action == "state":
        state = store.get_state()
        print(json.dumps(state, ensure_ascii=False, indent=2))

    elif args.action == "add":
        if not args.event:
            print("ERROR: --event required", file=sys.stderr)
            sys.exit(1)
        result = store.add_milestone(args.event, args.type, args.significance, args.context)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.action == "timeline":
        tl = store.get_timeline(args.count)
        if args.format == "prompt":
            for i, m in enumerate(tl, 1):
                label = MILESTONE_TYPES.get(m["type"], {}).get("label", m["type"])
                print(f"{i}. [{label}] {m['event']} （{m['stage']}）")
        else:
            print(json.dumps(tl, ensure_ascii=False, indent=2))

    elif args.action == "snapshot":
        snap = store.get_snapshot()
        if args.format == "prompt":
            prompt = store.get_context_prompt()
            print(prompt)
        else:
            print(json.dumps(snap, ensure_ascii=False, indent=2))

    elif args.action == "evolve":
        store.evolve(args.new_year, "上学期")
        print(json.dumps({"status": "evolved", "to": args.new_year + "上"}, ensure_ascii=False))

    elif args.action == "arcs":
        arcs = store.get_arcs_summary()
        print(json.dumps(arcs, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
