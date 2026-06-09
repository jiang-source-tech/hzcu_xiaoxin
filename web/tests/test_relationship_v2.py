"""关系闭环自对话测试 v2 CLI.

用法:
    python test_relationship_v2.py --scene anxious_prospective
    python test_relationship_v2.py --seed 42                  # 可复现
    python test_relationship_v2.py --max-days 3               # 只跑前 N 天
    python test_relationship_v2.py --skip-judge               # 跳过质量裁判
    python test_relationship_v2.py --json                     # JSON 输出
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import unittest
from unittest import mock
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DEEPSEEK_API_KEY", "test-key")

from scene_runner import load_all_scenes, run_suite  # noqa: E402

RESULT_DIR = Path(__file__).resolve().parents[1] / "test_results"
DISABLED_MESSAGE = "relationship-test 已下线；请使用 /test 进行日常对话压测。"


def print_report(report: dict[str, Any]) -> None:
    """Print a human-readable report to stdout."""
    print("\n" + "=" * 64)
    print("  关系闭环自对话测试 v2")
    print(f"  时间: {report['generated_at']}")
    print(f"  Seed: {report['seed']}")
    print(f"  结果: {report['passed']} PASS / {report['warned']} WARN / {report['failed']} FAIL")
    print("=" * 64)

    for result in report["results"]:
        verdict_icon = {"PASS": "[PASS]", "WARN": "[WARN]", "FAIL": "[FAIL]"}[result["verdict"]]
        print(f"\n{verdict_icon} {result['name']} ({result['scene_id']})")
        print(f"  质量均分: {result['quality_avg_score']} | 规则违规: {result['rule_violations_count']}")

        # Quality scores
        qj = result.get("quality_judge") or {}
        qs = qj.get("scores", {})
        if qs:
            score_str = " | ".join(f"{k}: {v}" for k, v in qs.items() if v is not None)
            print(f"  评分: {score_str}")

        # Episode summary
        for r in result["records"]:
            hook = r.get("next_hook") or {}
            state = r.get("state") or {}
            tag = "G" if r["action"] == "greeting" else "C"
            print(f"  Day {r['day']} [{tag}] stage={state.get('user_stage')} "
                  f"hook={hook.get('topic')} active={hook.get('active')}")
            if r["user_message"]:
                print(f"    用户: {r['user_message'][:80]}")
            print(f"    小芯: {r['xiaoxin_reply'][:80]}")
            for v in r.get("violations", []):
                print(f"    ! {v['type']}: {v.get('evidence', '')}")

        print(f"  {result.get('notes', '')}")


def save_report(report: dict[str, Any]) -> Path:
    """Save report JSON to test_results directory."""
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = RESULT_DIR / f"relationship_v2_{stamp}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    return path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    scenes = load_all_scenes()
    scene_ids = [s["scene_id"] for s in scenes]

    parser = argparse.ArgumentParser(description="小芯关系闭环自对话测试 v2")
    parser.add_argument(
        "--scene", required=True, choices=scene_ids,
        help="要运行的单个场景",
    )
    parser.add_argument("--seed", type=int, default=None, help="随机种子，用于复现")
    parser.add_argument("--max-days", type=int, default=None, help="只运行 day <= N 的 episode")
    parser.add_argument("--skip-judge", action="store_true", help="跳过质量裁判 LLM（仅规则评估）")
    parser.add_argument("--json", action="store_true", help="仅输出 JSON 报告")
    parser.add_argument("--no-save", action="store_true", help="不保存报告到文件")
    return parser.parse_args(argv)


class RelationshipV2CliArgsTest(unittest.TestCase):
    def test_all_scene_is_not_a_cli_choice(self):
        with self.assertRaises(SystemExit):
            parse_args(["--scene", "all"])

    def test_cli_is_disabled_before_running_suite(self):
        with mock.patch(__name__ + ".run_suite") as run_suite:
            exit_code = main(["--scene", "anxious_prospective"])

        self.assertEqual(exit_code, 2)
        run_suite.assert_not_called()


def main(argv: list[str] | None = None) -> int:
    print(DISABLED_MESSAGE)
    return 2

    args = parse_args(argv)

    report = run_suite(
        scene_id=args.scene,
        seed=args.seed,
        skip_quality_judge=args.skip_judge,
        max_days=args.max_days,
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
