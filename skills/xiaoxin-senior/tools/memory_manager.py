#!/usr/bin/env python3
"""小芯记忆引擎 · Memory Manager for XiaoXin

管理小芯数字人的对话记忆：重要性打分、艾宾浩斯遗忘曲线衰减、检索与持久化。

Usage:
    python memory_manager.py --action load   --data-dir <path> [--user-id <id>]
    python memory_manager.py --action save   --data-dir <path> --content "..." --type <type> [--user-id <id>]
    python memory_manager.py --action search --data-dir <path> --query "..." [--user-id <id>]
    python memory_manager.py --action decay  --data-dir <path> [--user-id <id>]
    python memory_manager.py --action stats  --data-dir <path> [--user-id <id>]
"""

import argparse
import json
import os
import sys
import time
import math
from datetime import datetime, timezone
from pathlib import Path


# ─── 记忆类型与基础重要性 ─────────────────────────────────────────────

MEMORY_TYPES = {
    "name":        {"base": 0.50, "label": "称呼"},
    "major":       {"base": 0.45, "label": "专业"},
    "hometown":    {"base": 0.40, "label": "家乡"},
    "goal":        {"base": 0.50, "label": "目标/计划"},
    "interest":    {"base": 0.40, "label": "兴趣爱好"},
    "emotion":     {"base": 0.45, "label": "情绪状态"},
    "topic":       {"base": 0.30, "label": "聊天话题"},
    "achievement": {"base": 0.45, "label": "成就/经历"},
    "relationship":{"base": 0.35, "label": "人际关系"},
    "misc":        {"base": 0.20, "label": "其他"},
}

# 重要性加分触发器
IMPORTANCE_BOOSTS = [
    # (关键词列表, 加分值, 说明)
    (["我是", "我叫", "我的名字", "喊我", "就叫我"], 0.15, "自我介绍信号"),
    (["记住", "别忘了", "记牢"], 0.20, "用户明确要求记住"),
    (["考研", "保研", "出国", "考公", "找工作", "转专业"], 0.15, "重大人生规划"),
    (["我好焦虑", "好迷茫", "不知道怎么办", "崩溃", "撑不住"], 0.15, "强烈负面情绪"),
    (["太开心了", "超爽", "好兴奋", "激动"], 0.10, "强烈正面情绪"),
    (["我喜欢", "我热爱", "我一直", "我从小"], 0.10, "长期偏好"),
    (["第一次", "拿到了", "过了", "成功了", "获奖"], 0.15, "里程碑事件"),
]
REPEAT_BOOST = 0.08  # 每次重复提及的加分


# ─── 遗忘曲线 ──────────────────────────────────────────────────────────

def calc_strength(importance: float, days_since_create: float,
                  days_since_access: float, access_count: int) -> float:
    """计算记忆当前强度。

    公式：strength = importance × e^(-days / (importance × 30 + 5))
    最近访问会减缓衰减（新鲜度加成）。
    """
    # 基础衰减：重要性越高，遗忘越慢
    half_life = importance * 30 + 5  # 重要性0.9 → 半衰期约22天；重要性0.3 → 半衰期约9天
    decay = math.exp(-days_since_create / half_life)

    # 新鲜度加成：最近访问过的记忆衰减更慢
    freshness = math.exp(-days_since_access / 7)  # 7天内访问有明显加成
    freshness_boost = 0.3 * freshness

    # 访问次数微调（多次访问让记忆更牢固，但上限明显）
    access_bonus = min(0.15, access_count * 0.03)

    raw = importance * decay + freshness_boost + access_bonus
    return round(min(1.0, max(0.0, raw)), 3)


def classify_memory(strength: float) -> str:
    """记忆强度分级"""
    if strength >= 0.5:  return "清晰"
    if strength >= 0.3:  return "可回忆"
    if strength >= 0.15: return "模糊"
    if strength >= 0.05: return "碎片"
    return "遗忘"


# ─── Memory Store 操作 ──────────────────────────────────────────────────

class MemoryStore:
    """管理单个用户的记忆 JSON 文件"""

    def __init__(self, data_dir: str, user_id: str = "default"):
        self.data_dir = Path(data_dir)
        self.user_id = user_id
        self.file_path = self.data_dir / f"memory_{user_id}.json"
        self.data = {"user_id": user_id, "memories": [], "stats": {}}
        self._ensure_file()

    def _ensure_file(self):
        self.data_dir.mkdir(parents=True, exist_ok=True)
        if self.file_path.exists():
            try:
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    self.data = json.load(f)
            except (json.JSONDecodeError, IOError):
                self.data = {"user_id": self.user_id, "memories": [], "stats": {}}

    def _save(self):
        self.data["stats"]["last_updated"] = datetime.now(timezone.utc).isoformat()
        self.data["stats"]["total_memories"] = len(self.data["memories"])
        with open(self.file_path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    # ── 加载有效记忆 ──────────────────────────────────────────────────

    def load_active(self, min_strength: float = 0.10) -> list:
        """返回强度 >= min_strength 的记忆，按强度降序排列"""
        now = datetime.now(timezone.utc)
        active = []
        for m in self.data["memories"]:
            days_create = (now - datetime.fromisoformat(m["created_at"])).total_seconds() / 86400
            days_access = (now - datetime.fromisoformat(m["last_accessed"])).total_seconds() / 86400
            m["strength"] = calc_strength(m["importance"], days_create, days_access, m.get("access_count", 0))
            m["status"] = classify_memory(m["strength"])
            if m["strength"] >= min_strength:
                active.append(m)
        active.sort(key=lambda x: x["strength"], reverse=True)
        return active

    # ── 保存新记忆 ────────────────────────────────────────────────────

    def add_memory(self, content: str, mem_type: str = "misc",
                   importance_override: float = None) -> dict:
        """添加一条新记忆。自动检测是否与已有记忆重复/冲突。"""

        # 1. 计算重要性
        if importance_override is not None:
            importance = max(0.0, min(1.0, importance_override))
        else:
            importance = self._score_importance(content, mem_type)

        # 2. 去重检测：是否存在高度相似的记忆
        existing = self._find_similar(content)
        if existing:
            # 更新已有记忆
            existing["importance"] = min(1.0, existing["importance"] + 0.05)
            existing["last_accessed"] = datetime.now(timezone.utc).isoformat()
            existing["access_count"] = existing.get("access_count", 0) + 1
            existing["content"] = content  # 用新内容替换（可能是更新）
            self._save()
            return {"action": "updated", "memory": existing}

        # 3. 新建记忆
        now = datetime.now(timezone.utc).isoformat()
        memory = {
            "id": f"m{int(time.time() * 1000)}",
            "content": content,
            "type": mem_type if mem_type in MEMORY_TYPES else "misc",
            "importance": importance,
            "created_at": now,
            "last_accessed": now,
            "access_count": 1,
            "strength": importance,
            "status": "清晰" if importance >= 0.5 else "可回忆"
        }
        self.data["memories"].append(memory)

        # 4. 数量上限保护（最多200条，超出删最弱的）
        if len(self.data["memories"]) > 200:
            self.data["memories"].sort(key=lambda x: x["importance"])
            self.data["memories"] = self.data["memories"][-200:]

        self._save()
        return {"action": "created", "memory": memory}

    def _score_importance(self, content: str, mem_type: str) -> float:
        """根据内容和类型计算重要性分数"""
        base = MEMORY_TYPES.get(mem_type, MEMORY_TYPES["misc"])["base"]
        boost = 0.0
        for keywords, value, _ in IMPORTANCE_BOOSTS:
            if any(kw in content for kw in keywords):
                boost = max(boost, value)  # 取最高加分，不叠加
        return round(min(1.0, base + boost), 2)

    def _find_similar(self, content: str) -> dict | None:
        """简单的关键词重叠检测去重"""
        words_new = set(content)
        for m in self.data["memories"]:
            words_old = set(m["content"])
            if len(words_old) > 0:
                overlap = len(words_new & words_old) / len(words_old)
                if overlap > 0.6:
                    return m
        return None

    # ── 搜索记忆 ──────────────────────────────────────────────────────

    def search(self, query: str, top_k: int = 5) -> list:
        """在记忆库中搜索相关内容（简单关键词匹配）"""
        self.load_active()  # 先刷新强度
        query_words = set(query)
        scored = []
        for m in self.data["memories"]:
            content_words = set(m["content"])
            if len(content_words) == 0:
                continue
            score = len(query_words & content_words) / len(query_words)
            if score > 0:
                scored.append((score * m.get("strength", 0.3), m))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [m for _, m in scored[:top_k]]

    # ── 衰减清理 ──────────────────────────────────────────────────────

    def decay_cleanup(self, archive_threshold: float = 0.05):
        """清理已遗忘的记忆（strength < threshold），归档到 archive.json"""
        now = datetime.now(timezone.utc)
        kept = []
        archived = []
        for m in self.data["memories"]:
            days_create = (now - datetime.fromisoformat(m["created_at"])).total_seconds() / 86400
            days_access = (now - datetime.fromisoformat(m["last_accessed"])).total_seconds() / 86400
            strength = calc_strength(m["importance"], days_create, days_access, m.get("access_count", 0))
            if strength >= archive_threshold:
                kept.append(m)
            else:
                archived.append(m)

        if archived:
            archive_path = self.data_dir / f"archive_{self.user_id}.json"
            existing_archive = []
            if archive_path.exists():
                with open(archive_path, 'r', encoding='utf-8') as f:
                    existing_archive = json.load(f)
            existing_archive.extend(archived)
            with open(archive_path, 'w', encoding='utf-8') as f:
                json.dump(existing_archive, f, ensure_ascii=False, indent=2)

        self.data["memories"] = kept
        self._save()
        return {"kept": len(kept), "archived": len(archived)}

    # ── 统计 ──────────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        active = self.load_active()
        by_type = {}
        for m in active:
            t = m["type"]
            by_type[t] = by_type.get(t, 0) + 1
        return {
            "user_id": self.user_id,
            "total_stored": len(self.data["memories"]),
            "active_count": len(active),
            "by_type": by_type,
            "by_status": {
                "清晰": sum(1 for m in active if m.get("status") == "清晰"),
                "可回忆": sum(1 for m in active if m.get("status") == "可回忆"),
                "模糊": sum(1 for m in active if m.get("status") == "模糊"),
            },
            "top_memories": [
                {"content": m["content"][:40], "strength": m["strength"], "type": m["type"]}
                for m in active[:5]
            ]
        }

    # ── 最近对话摘要（嵌入上下文用）─────────────────────────────────────

    def get_context_prompt(self, max_items: int = 8, min_strength: float = 0.15) -> str:
        """生成嵌入 system prompt 的记忆上下文文本"""
        active = self.load_active(min_strength)
        if not active:
            return ""

        lines = ["## 关于这个新生（小芯记得的）"]
        for i, m in enumerate(active[:max_items], 1):
            label = MEMORY_TYPES.get(m["type"], {}).get("label", m["type"])
            status_icon = {"清晰": "●", "可回忆": "◐", "模糊": "○"}.get(m.get("status"), "○")
            lines.append(f"{i}. [{label}] {status_icon} {m['content']}")

        if len(active) > max_items:
            lines.append(f"... 还有 {len(active) - max_items} 条模糊的记忆")
        return "\n".join(lines)


# ─── CLI ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="小芯记忆引擎")
    parser.add_argument("--action", required=True,
                        choices=["load", "save", "search", "decay", "stats"])
    parser.add_argument("--data-dir", required=True, help="data/ 目录路径")
    parser.add_argument("--user-id", default="default", help="用户ID")
    parser.add_argument("--content", help="记忆内容（save/search 用）")
    parser.add_argument("--type", default="misc", help="记忆类型")
    parser.add_argument("--importance", type=float, help="手动指定重要性")
    parser.add_argument("--query", help="搜索关键词（search 用）")
    parser.add_argument("--min-strength", type=float, default=0.10, help="最低强度阈值")
    parser.add_argument("--format", default="prompt", choices=["json", "prompt"],
                        help="输出格式：json 或 prompt文本")

    args = parser.parse_args()
    store = MemoryStore(args.data_dir, args.user_id)

    if args.action == "load":
        memories = store.load_active(args.min_strength)
        if args.format == "prompt":
            prompt = store.get_context_prompt(min_strength=args.min_strength)
            if prompt:
                print(prompt)
        else:
            print(json.dumps(memories, ensure_ascii=False, indent=2))

    elif args.action == "save":
        if not args.content:
            print("ERROR: --content is required for save action", file=sys.stderr)
            sys.exit(1)
        result = store.add_memory(args.content, args.type, args.importance)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.action == "search":
        if not args.query:
            print("ERROR: --query is required for search action", file=sys.stderr)
            sys.exit(1)
        results = store.search(args.query)
        print(json.dumps(results, ensure_ascii=False, indent=2))

    elif args.action == "decay":
        result = store.decay_cleanup()
        print(json.dumps(result, ensure_ascii=False))

    elif args.action == "stats":
        stats = store.get_stats()
        print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
