import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("DEEPSEEK_API_KEY", "test-key")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app as app_module


class RelationshipSelfPlayApiTest(unittest.TestCase):
    def setUp(self):
        self.client = app_module.app.test_client()

    def test_personas_endpoint_returns_runner_personas(self):
        response = self.client.get("/api/relationship-selfplay/personas")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        ids = {item["id"] for item in payload["personas"]}
        self.assertIn("anxious_prospective", ids)
        self.assertIn("reject_old_topic", ids)
        anxious = next(item for item in payload["personas"] if item["id"] == "anxious_prospective")
        self.assertEqual(anxious["name"], "焦虑准新生")
        self.assertEqual(anxious["steps"], 5)

    def test_run_endpoint_runs_single_persona_in_deterministic_mode(self):
        response = self.client.post(
            "/api/relationship-selfplay/run",
            json={"persona": "anxious_prospective", "live": False},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["mode"], "deterministic")
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["failed"], 0)
        result = payload["results"][0]
        self.assertEqual(result["persona"], "anxious_prospective")
        self.assertEqual(result["relationship_score"], 10)
        self.assertIn("课程节奏", result["records"][1]["xiaoxin_reply"])
        self.assertIn("state", result["records"][1])
        self.assertIn("next_hook", result["records"][1])

    def test_run_endpoint_rejects_unknown_persona(self):
        response = self.client.post(
            "/api/relationship-selfplay/run",
            json={"persona": "missing_persona"},
        )

        self.assertEqual(response.status_code, 400)
        payload = response.get_json()
        self.assertIn("error", payload)


if __name__ == "__main__":
    unittest.main()
