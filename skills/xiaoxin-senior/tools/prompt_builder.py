#!/usr/bin/env python3
"""小芯 System Prompt 构建器

从 prompts/ 目录下的组件文件组合生成完整的 SKILL.md。
支持命令行调用和 Python import 两种使用方式。

参考 yourself-skill/tools/skill_writer.py 的 combine 模式。

Usage:
    python tools/prompt_builder.py --action list          # 列出所有组件
    python tools/prompt_builder.py --action combine       # 生成 SKILL.md
"""

import argparse
import sys
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
SKILL_FILE = Path(__file__).resolve().parent.parent / "SKILL.md"

# 组件加载顺序（按 Layer 0 → 5 → 附录）
COMPONENT_ORDER = [
    # Layer 0: 硬规则（最高优先级）
    "hard_rules.md",
    # Layer 1: 身份锚定
    "identity.md",
    # Layer 2: 对话风格
    "speech_style.md",
    # Layer 3: 心智模型
    "mental_models.md",
    # Layer 4: 知识域
    "knowledge_domains.md",
    # Layer 5: 回答工作流
    "response_workflow.md",
    # 附录
    "example_dialogues.md",
    "embedded_adaptation.md",
    # 外部协议（已有，可选加载）
    "memory_protocol.md",
    "growth_protocol.md",
]

# SKILL.md 的 YAML frontmatter（元数据，不参与 prompt 组合）
FRONTMATTER = """---
name: xiaoxin-senior
description: |
  小芯——浙大城市学院信息与电气工程学院的数字吉祥物。亲切学长型数字人，
  诞生于信电学院，陪伴新生从入学到毕业一起成长。
  具备记忆系统（记谁忘什么）和成长追踪（见证变化、阶段感知）。
  触发词：「小芯」「信电学院」「学长」「新生」「聊聊专业」「竞赛」
  适用场景：嵌入式语音交互设备（开发板+屏幕+麦克风+扬声器）
---"""

# SKILL.md 开头（标题 + 引言）
SKILL_HEADER = """# 小芯 · 信电学院数字学长

> 「嗨，我是小芯！信电学院走出来的数字学长，一起聊聊？」"""


def load_component(filename: str) -> str | None:
    """加载单个 prompt 组件文件，返回内容（不含 frontmatter 处理）。"""
    filepath = PROMPTS_DIR / filename
    if not filepath.exists():
        return None
    content = filepath.read_text(encoding="utf-8")
    return content.strip()


def list_components() -> list[dict]:
    """列出所有组件文件及其状态。"""
    result = []
    for filename in COMPONENT_ORDER:
        filepath = PROMPTS_DIR / filename
        exists = filepath.exists()
        size = filepath.stat().st_size if exists else 0
        result.append({
            "file": filename,
            "exists": exists,
            "size_bytes": size,
            "size_kb": round(size / 1024, 1),
        })
    return result


def build_prompt(with_frontmatter: bool = True) -> str:
    """组合所有组件生成完整的 SKILL.md 内容。

    Args:
        with_frontmatter: 是否包含 YAML frontmatter（写入 SKILL.md 时为 True，
                         运行时注入 system prompt 时为 False）

    Returns:
        完整的 prompt 文本
    """
    parts = []

    if with_frontmatter:
        parts.append(FRONTMATTER)
        parts.append("")
        parts.append(
            "<!-- 本文件由 tools/prompt_builder.py 自动生成。"
            "如需修改，请编辑 prompts/ 下的组件文件，然后运行: python tools/prompt_builder.py --action combine -->"
        )
        parts.append("")

    parts.append(SKILL_HEADER)
    parts.append("")

    loaded = 0
    skipped = 0

    for filename in COMPONENT_ORDER:
        content = load_component(filename)
        if content is None:
            skipped += 1
            print(f"[WARN] 组件文件不存在，跳过: prompts/{filename}", file=sys.stderr)
            continue

        parts.append(content)
        parts.append("")
        loaded += 1

    if skipped > 0:
        print(f"[INFO] 已加载 {loaded} 个组件，跳过 {skipped} 个", file=sys.stderr)

    return "\n".join(parts).rstrip() + "\n"


def write_skill_md() -> bool:
    """将组合后的 prompt 写入 SKILL.md。"""
    content = build_prompt(with_frontmatter=True)
    SKILL_FILE.write_text(content, encoding="utf-8")
    size_kb = round(len(content.encode("utf-8")) / 1024, 1)
    print(f"[OK] 已生成 SKILL.md ({size_kb} KB)")
    print(f"     路径: {SKILL_FILE}")
    return True


def cmd_list():
    """CLI: 列出组件状态。"""
    components = list_components()
    print(f"组件目录: {PROMPTS_DIR}\n")
    print(f"{'状态':<6} {'大小':>8}   {'文件'}")
    print("-" * 50)
    for c in components:
        status = "[OK]" if c["exists"] else "[MISS]"
        size_str = f"{c['size_kb']} KB" if c["exists"] else "-"
        print(f"{status:<6} {size_str:>8}   {c['file']}")
    total = sum(c["size_bytes"] for c in components if c["exists"])
    loaded = sum(1 for c in components if c["exists"])
    print("-" * 50)
    print(f"共 {loaded}/{len(components)} 个组件, 合计 {round(total/1024, 1)} KB")


def cmd_combine():
    """CLI: 生成 SKILL.md。"""
    write_skill_md()


def main():
    parser = argparse.ArgumentParser(
        description="小芯 System Prompt 构建器 - 从 prompts/ 组件组合生成 SKILL.md"
    )
    parser.add_argument(
        "--action",
        required=True,
        choices=["list", "combine"],
        help="list: 列出组件状态; combine: 组合生成 SKILL.md",
    )
    args = parser.parse_args()

    if args.action == "list":
        cmd_list()
    elif args.action == "combine":
        cmd_combine()


if __name__ == "__main__":
    main()
