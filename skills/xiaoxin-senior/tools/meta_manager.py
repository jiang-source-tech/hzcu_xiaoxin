#!/usr/bin/env python3
"""小芯用户元数据管理器 · Meta Manager

管理每个用户的画像元数据：基本信息、统计、纠正记录。
参考 yourself-skill/tools/skill_writer.py 的 meta.json 模式。

每个用户一个 meta_{user_id}.json 文件，存储结构化画像，
与 memory/growth/sessions 数据互补。

Usage:
    python meta_manager.py --action init   --data-dir <path> --user-id <id> [--name <name>] [--major <major>] [--grade <grade>]
    python meta_manager.py --action load   --data-dir <path> --user-id <id> [--format prompt|json]
    python meta_manager.py --action update --data-dir <path> --user-id <id> --field <field> --value <value>
    python meta_manager.py --action stats  --data-dir <path> --user-id <id>
    python meta_manager.py --action record-correction --data-dir <path> --user-id <id> --correction <text>
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def _meta_path(data_dir: Path, user_id: str) -> Path:
    return data_dir / f"meta_{user_id}.json"


def _load_meta(data_dir: Path, user_id: str) -> dict:
    path = _meta_path(data_dir, user_id)
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return _empty_meta(user_id)


def _save_meta(data_dir: Path, user_id: str, meta: dict):
    data_dir.mkdir(parents=True, exist_ok=True)
    meta["updated_at"] = datetime.now(timezone.utc).isoformat()
    with open(_meta_path(data_dir, user_id), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


def _empty_meta(user_id: str) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    return {
        "user_id": user_id,
        "profile": {},
        "stats": {
            "first_seen": now,
            "total_chats": 0,
            "total_sessions": 0,
            "last_active": now,
        },
        "corrections": [],
        "created_at": now,
        "updated_at": now,
    }


# ─── Public API ──────────────────────────────────────────────────────────


def init_meta(
    data_dir: Path,
    user_id: str,
    name: str | None = None,
    major: str | None = None,
    grade: str | None = None,
    hometown: str | None = None,
    interests: list[str] | None = None,
) -> dict:
    """初始化用户 meta 文件（首次创建用户时调用）。"""
    meta = _load_meta(data_dir, user_id)
    profile = meta.get("profile", {})
    if name:
        profile["name"] = name
    if major:
        profile["major"] = major
    if grade:
        profile["grade"] = grade
    if hometown:
        profile["hometown"] = hometown
    if interests:
        existing = profile.get("interests", [])
        profile["interests"] = list(set(existing + interests))
    meta["profile"] = profile
    _save_meta(data_dir, user_id, meta)
    return meta


def load_meta(data_dir: Path, user_id: str) -> dict:
    """加载用户 meta。"""
    return _load_meta(data_dir, user_id)


def update_meta(data_dir: Path, user_id: str, field: str, value: str) -> dict:
    """更新用户 meta 的 profile 字段。"""
    meta = _load_meta(data_dir, user_id)
    meta.setdefault("profile", {})[field] = value
    _save_meta(data_dir, user_id, meta)
    return meta


def increment_chats(data_dir: Path, user_id: str):
    """增加聊天计数。"""
    meta = _load_meta(data_dir, user_id)
    meta.setdefault("stats", {})["total_chats"] = meta["stats"].get("total_chats", 0) + 1
    meta["stats"]["last_active"] = datetime.now(timezone.utc).isoformat()
    _save_meta(data_dir, user_id, meta)


def record_correction(data_dir: Path, user_id: str, correction_text: str) -> dict:
    """记录一条用户纠正。"""
    meta = _load_meta(data_dir, user_id)
    meta.setdefault("corrections", []).append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "text": correction_text,
    })
    # 保留最近 20 条纠正
    if len(meta["corrections"]) > 20:
        meta["corrections"] = meta["corrections"][-20:]
    _save_meta(data_dir, user_id, meta)
    return meta


def corrections_prompt(data_dir: Path, user_id: str) -> str:
    """将用户纠正格式化为 prompt 片段，供 system prompt 注入。"""
    meta = _load_meta(data_dir, user_id)
    corrections = meta.get("corrections", [])
    if not corrections:
        return ""
    recent = corrections[-5:]  # 只注入最近 5 条
    lines = ["\n【用户近期纠正（请尊重以下信息）】"]
    for c in recent:
        ts = c.get("timestamp", "")[:10]
        text = c.get("text", "")
        lines.append(f"- [{ts}] {text}")
    return "\n".join(lines)


def profile_prompt(data_dir: Path, user_id: str) -> str:
    """将用户画像格式化为 prompt 片段。"""
    meta = _load_meta(data_dir, user_id)
    profile = meta.get("profile", {})
    parts = []
    if profile.get("name"):
        parts.append(f"名字：{profile['name']}")
    if profile.get("major"):
        parts.append(f"专业：{profile['major']}")
    if profile.get("grade"):
        parts.append(f"年级：{profile['grade']}")
    if profile.get("hometown"):
        parts.append(f"家乡：{profile['hometown']}")
    if not parts:
        return ""
    return "\n【用户画像】\n" + "\n".join(parts)


def stats_meta(data_dir: Path, user_id: str) -> dict:
    """返回用户统计摘要。"""
    meta = _load_meta(data_dir, user_id)
    return {
        "user_id": user_id,
        "profile": meta.get("profile", {}),
        "stats": meta.get("stats", {}),
        "corrections_count": len(meta.get("corrections", [])),
        "created_at": meta.get("created_at", ""),
    }


# ─── CLI ─────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="小芯用户元数据管理器")
    parser.add_argument("--action", required=True,
                        choices=["init", "load", "update", "stats", "record-correction"])
    parser.add_argument("--data-dir", required=True, help="数据目录路径")
    parser.add_argument("--user-id", required=True, help="用户 ID")
    parser.add_argument("--name", help="用户名字")
    parser.add_argument("--major", help="专业")
    parser.add_argument("--grade", help="年级")
    parser.add_argument("--hometown", help="家乡")
    parser.add_argument("--field", help="update 时的字段名")
    parser.add_argument("--value", help="update 时的字段值")
    parser.add_argument("--correction", help="纠正文本")
    parser.add_argument("--format", default="json", choices=["json", "prompt"],
                        help="load 时的输出格式")

    args = parser.parse_args()
    dd = Path(args.data_dir)

    if args.action == "init":
        meta = init_meta(dd, args.user_id, name=args.name,
                         major=args.major, grade=args.grade, hometown=args.hometown)
        print(json.dumps(meta, ensure_ascii=False, indent=2))

    elif args.action == "load":
        if args.format == "prompt":
            profile = profile_prompt(dd, args.user_id)
            corrections = corrections_prompt(dd, args.user_id)
            output = profile
            if corrections:
                output += "\n" + corrections
            print(output)
        else:
            meta = load_meta(dd, args.user_id)
            print(json.dumps(meta, ensure_ascii=False, indent=2))

    elif args.action == "update":
        if not args.field or not args.value:
            print("错误：update 需要 --field 和 --value", file=sys.stderr)
            sys.exit(1)
        meta = update_meta(dd, args.user_id, args.field, args.value)
        print(json.dumps(meta, ensure_ascii=False, indent=2))

    elif args.action == "stats":
        stats = stats_meta(dd, args.user_id)
        print(json.dumps(stats, ensure_ascii=False, indent=2))

    elif args.action == "record-correction":
        if not args.correction:
            print("错误：record-correction 需要 --correction", file=sys.stderr)
            sys.exit(1)
        meta = record_correction(dd, args.user_id, args.correction)
        print(json.dumps(meta, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
