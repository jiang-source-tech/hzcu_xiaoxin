"""关系闭环自对话压测 CLI.

用法:
    python test_relationship_self_play.py --persona anxious_prospective
    python test_relationship_self_play.py --persona all
    python test_relationship_self_play.py --persona all --days 3
    python test_relationship_self_play.py --persona competition_newbie --live
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any


if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

os.environ.setdefault("DEEPSEEK_API_KEY", "test-key")

WEB_DIR = Path(__file__).resolve().parent
RESULT_DIR = WEB_DIR / "test_results"

from relationship_self_play_runner import PERSONAS  # noqa: E402
from relationship_self_play_runner import ScriptedClient  # noqa: E402
from relationship_self_play_runner import evaluate_expectations  # noqa: E402
from relationship_self_play_runner import relation_violations  # noqa: E402
from relationship_self_play_runner import run_persona  # noqa: E402
from relationship_self_play_runner import run_suite  # noqa: E402


def print_report(report: dict[str, Any]) -> None:
    print("\n" + "=" * 64)
    print("关系闭环自对话压测")
    print(f"模式: {report['mode']} | 通过: {report['passed']}/{report['total']}")
    print("=" * 64)
    for result in report["results"]:
        marker = "PASS" if not result["violations"] else "FAIL"
        print(f"\n[{marker}] {result['name']} ({result['persona']}) score={result['relationship_score']}")
        print(f"  {result['description']}")
        for record in result["records"]:
            hook = record.get("next_hook") or {}
            state = record.get("state") or {}
            print(
                f"  Day {record['day']} {record['action']}: "
                f"stage={state.get('user_stage')} topic={state.get('recent_topic')} "
                f"hook={hook.get('topic')} active={hook.get('active')}"
            )
            print(f"    小信: {record['xiaoxin_reply']}")
            for violation in record["violations"]:
                print(f"    - {violation['type']}: {violation.get('evidence', '')}")


def save_report(report: dict[str, Any]) -> Path:
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = RESULT_DIR / f"relationship_self_play_{stamp}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    return path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="小信关系闭环自对话压测")
    parser.add_argument(
        "--persona",
        default="all",
        choices=["all", *PERSONAS.keys()],
        help="要运行的关系 persona，默认 all",
    )
    parser.add_argument("--days", type=int, default=None, help="只运行 day <= N 的步骤")
    parser.add_argument("--live", action="store_true", help="调用真实模型，默认使用离线模拟回复")
    parser.add_argument("--data-dir", type=Path, default=None, help="指定测试数据目录，默认使用临时目录")
    parser.add_argument("--json", action="store_true", help="只输出 JSON 报告")
    parser.add_argument("--no-save", action="store_true", help="不保存报告到 web/test_results")
    parser.add_argument("--show-app-log", action="store_true", help="显示 /api/chat 内部调试日志")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if args.data_dir:
        data_dir = args.data_dir
        data_dir.mkdir(parents=True, exist_ok=True)
        report = run_suite(
            args.persona,
            data_dir,
            live=args.live,
            max_days=args.days,
            show_app_log=args.show_app_log,
        )
    else:
        with tempfile.TemporaryDirectory(prefix="xiaoxin_relationship_") as tmp:
            report = run_suite(
                args.persona,
                Path(tmp),
                live=args.live,
                max_days=args.days,
                show_app_log=args.show_app_log,
            )

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_report(report)

    if not args.no_save:
        path = save_report(report)
        if not args.json:
            print(f"\n报告已保存: {path}")

    return 0 if report["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
