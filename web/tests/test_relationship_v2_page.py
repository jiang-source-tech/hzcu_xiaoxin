import unittest
import os
import sys
from pathlib import Path

os.environ.setdefault("DEEPSEEK_API_KEY", "test-key")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app as app_module


class RelationshipV2PageTest(unittest.TestCase):
    def setUp(self):
        self.client = app_module.app.test_client()

    def test_relationship_test_page_is_disabled(self):
        response = self.client.get("/relationship-test")

        self.assertEqual(response.status_code, 404)

    def test_legacy_relationship_v2_route_stays_absent(self):
        response = self.client.get("/relationship-v2-test")

        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
