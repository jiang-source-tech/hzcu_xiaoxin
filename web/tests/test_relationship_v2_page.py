import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class RelationshipV2PageTest(unittest.TestCase):
    def setUp(self):
        self.html = (ROOT / "static" / "relationship-v2-test.html").read_text(
            encoding="utf-8"
        )
        self.app_py = (ROOT / "app.py").read_text(encoding="utf-8")

    def test_relationship_test_is_the_only_relationship_replay_route(self):
        relationship_route = re.search(
            r'@app\.route\("/relationship-test"\).*?send_static_file\("([^"]+)"\)',
            self.app_py,
            re.S,
        )
        v2_route = re.search(
            r'@app\.route\("/relationship-v2-test"\)',
            self.app_py,
        )

        self.assertIsNotNone(relationship_route)
        self.assertIsNone(v2_route)
        self.assertEqual(relationship_route.group(1), "relationship-v2-test.html")

    def test_page_centers_daily_llm_replay(self):
        expected_snippets = [
            "每日 LLM 对话回放",
            "用户 LLM",
            "小芯 LLM",
            "state-strip",
        ]

        for snippet in expected_snippets:
            with self.subTest(snippet=snippet):
                self.assertIn(snippet, self.html)

    def test_page_keeps_manual_review_context(self):
        self.assertIn("manual-review", self.html)
        self.assertIn("state-strip", self.html)

    def test_page_does_not_render_system_judgement_panels(self):
        removed_snippets = [
            "formatViolationDetail",
            "renderQualityPanel",
            "quality-panel",
            "quality_judge",
            "updateSceneVerdict",
            "rule_violations",
            "probes",
            "forbid_patterns",
            "violations",
            "day_summary",
            "day-summary",
        ]

        for snippet in removed_snippets:
            with self.subTest(snippet=snippet):
                self.assertNotIn(snippet, self.html)


    def test_page_exposes_manual_review_and_flushes_final_stream_event(self):
        expected_snippets = [
            "renderManualReviewPanel",
            "manual-review",
            "review_context",
            "flushSseBuffer",
            "processSseBuffer",
        ]

        for snippet in expected_snippets:
            with self.subTest(snippet=snippet):
                self.assertIn(snippet, self.html)

    def test_page_labels_same_day_turns(self):
        expected_snippets = [
            "turn_index",
            "turn_count",
            "Turn",
            "formatTurnLabel",
        ]

        for snippet in expected_snippets:
            with self.subTest(snippet=snippet):
                self.assertIn(snippet, self.html)

    def test_page_renders_idle_gaps_and_limits_manual_review_panels(self):
        expected_snippets = [
            "renderIdleGap",
            "idle-gap",
            "shouldShowManualReview",
            "turn_index === turn_count",
        ]

        for snippet in expected_snippets:
            with self.subTest(snippet=snippet):
                self.assertIn(snippet, self.html)

    def test_page_exposes_pressure_mode_controls(self):
        expected_snippets = [
            'id="modeSelect"',
            'value="mixed"',
            'value="regression"',
            'value="pressure"',
            'id="turnsPerDaySelect"',
            "turns_per_day",
            "mode: mode",
        ]

        for snippet in expected_snippets:
            with self.subTest(snippet=snippet):
                self.assertIn(snippet, self.html)

    def test_page_groups_records_by_day_and_labels_turn_source(self):
        expected_snippets = [
            "showDaySection",
            "day-section",
            "day-body",
            "turn_source",
            "formatTurnSource",
        ]

        for snippet in expected_snippets:
            with self.subTest(snippet=snippet):
                self.assertIn(snippet, self.html)

    def test_page_exposes_memory_audit_panel(self):
        expected_snippets = [
            "renderMemoryAuditPanel",
            "memory-audit",
            "memory_audit",
            "relationship_changes",
            "long_term_memories",
            "记忆审计",
        ]

        for snippet in expected_snippets:
            with self.subTest(snippet=snippet):
                self.assertIn(snippet, self.html)


if __name__ == "__main__":
    unittest.main()
