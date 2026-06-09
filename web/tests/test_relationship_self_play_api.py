import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("DEEPSEEK_API_KEY", "test-key")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app as app_module


class RelationshipSelfPlayApiTest(unittest.TestCase):
    def setUp(self):
        self.client = app_module.app.test_client()

    def test_personas_endpoint_is_disabled(self):
        response = self.client.get("/api/relationship-selfplay/personas")

        self.assertEqual(response.status_code, 410)
        self.assertIn("已下线", response.get_json()["error"])

    def test_run_endpoint_is_disabled_before_runner(self):
        with patch.object(app_module.relationship_runner, "run_suite") as run_suite:
            response = self.client.post(
                "/api/relationship-selfplay/run",
                json={"persona": "anxious_prospective", "live": False},
            )

        self.assertEqual(response.status_code, 410)
        self.assertIn("已下线", response.get_json()["error"])
        run_suite.assert_not_called()


if __name__ == "__main__":
    unittest.main()
