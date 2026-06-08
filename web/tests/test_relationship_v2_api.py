import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("DEEPSEEK_API_KEY", "test-key")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app as app_module


class RelationshipV2ApiTest(unittest.TestCase):
    def setUp(self):
        self.client = app_module.app.test_client()

    def post_with_captured_stream(self, payload):
        captured = {}

        def fake_stream(**kwargs):
            captured.update(kwargs)
            yield {
                "event": "complete",
                "data": {
                    "scene_id": "demo",
                    "name": "Demo",
                    "description": "",
                    "seed": 7,
                    "verdict": "PASS",
                    "rule_violations_count": 0,
                    "quality_avg_score": 0,
                    "notes": "",
                    "records": [],
                    "quality_judge": None,
                },
            }

        with patch.object(app_module.scene_runner_v2, "run_scene_streaming", side_effect=fake_stream):
            response = self.client.post(
                "/api/v2/relationship-selfplay/run",
                json=payload,
            )

        body = response.get_data(as_text=True)
        return response, body, captured

    def test_run_accepts_mode_and_turns_per_day(self):
        response, body, captured = self.post_with_captured_stream({
            "scene": "anxious_prospective",
            "seed": 7,
            "skip_judge": True,
            "mode": "mixed",
            "turns_per_day": 12,
            "max_days": 2,
        })

        self.assertEqual(response.status_code, 200)
        self.assertIn("event: complete", body)
        self.assertEqual(captured["scene_id"], "anxious_prospective")
        self.assertEqual(captured["seed"], 7)
        self.assertTrue(captured["skip_quality_judge"])
        self.assertEqual(captured["mode"], "mixed")
        self.assertEqual(captured["turns_per_day"], 12)
        self.assertEqual(captured["max_days"], 2)

    def test_run_defaults_mode_to_regression(self):
        response, body, captured = self.post_with_captured_stream({"turns_per_day": 8})

        self.assertEqual(response.status_code, 200)
        self.assertIn("event: complete", body)
        self.assertEqual(captured["mode"], "regression")

    def test_run_accepts_pressure_mode(self):
        response, body, captured = self.post_with_captured_stream({"mode": "pressure"})

        self.assertEqual(response.status_code, 200)
        self.assertIn("event: complete", body)
        self.assertEqual(captured["mode"], "pressure")

    def test_run_defaults_turns_per_day_to_none(self):
        for payload in (
            {"mode": "mixed"},
            {"mode": "mixed", "turns_per_day": ""},
            {"mode": "mixed", "turns_per_day": "default"},
        ):
            with self.subTest(payload=payload):
                response, body, captured = self.post_with_captured_stream(payload)

                self.assertEqual(response.status_code, 200)
                self.assertIn("event: complete", body)
                self.assertIsNone(captured["turns_per_day"])

    def test_run_accepts_integer_string_turns_per_day(self):
        response, body, captured = self.post_with_captured_stream({"turns_per_day": "12"})

        self.assertEqual(response.status_code, 200)
        self.assertIn("event: complete", body)
        self.assertEqual(captured["turns_per_day"], 12)

    def test_run_rejects_invalid_mode_before_streaming(self):
        with patch.object(app_module.scene_runner_v2, "run_scene_streaming") as run_streaming:
            response = self.client.post(
                "/api/v2/relationship-selfplay/run",
                json={"mode": "wild", "turns_per_day": 8},
            )

        self.assertEqual(response.status_code, 400)
        payload = response.get_json()
        self.assertIn("mode", payload["error"])
        run_streaming.assert_not_called()

    def test_run_rejects_invalid_turns_per_day_before_streaming(self):
        for value in (0, -1, "many", 1.5, True):
            with self.subTest(value=value):
                with patch.object(app_module.scene_runner_v2, "run_scene_streaming") as run_streaming:
                    response = self.client.post(
                        "/api/v2/relationship-selfplay/run",
                        json={"mode": "mixed", "turns_per_day": value},
                    )

                self.assertEqual(response.status_code, 400)
                payload = response.get_json()
                self.assertIn("turns_per_day", payload["error"])
                run_streaming.assert_not_called()

    def test_run_with_real_stream_accepts_pressure_options(self):
        def fake_chat_core(user_id, message, data_dir):
            return {
                "reply": "I hear the concern. Let's sort out the first week step by step.",
                "speech": "I hear the concern. Let's sort out the first week step by step.",
                "expression": "warm",
            }

        with patch.object(
            app_module.scene_runner_v2.user_simulator,
            "generate_user_message",
            return_value="I am worried about the first week course pace.",
        ), patch.object(app_module, "chat_core", side_effect=fake_chat_core):
            response = self.client.post(
                "/api/v2/relationship-selfplay/run",
                json={
                    "scene": "anxious_prospective",
                    "mode": "regression",
                    "turns_per_day": 3,
                    "skip_judge": True,
                    "max_days": 0,
                },
            )

        body = response.get_data(as_text=True)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("unexpected keyword argument", body)
        self.assertRegex(body, r"event: (episode|complete)")


if __name__ == "__main__":
    unittest.main()
