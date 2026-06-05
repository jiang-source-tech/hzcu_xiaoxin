import unittest
from pathlib import Path


TEST_HTML = Path(__file__).resolve().parents[1] / "static" / "relationship-test.html"


class RelationshipTestPageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = TEST_HTML.read_text(encoding="utf-8")

    def test_page_has_relationship_test_controls(self):
        self.assertIn('id="personaSelect"', self.html)
        self.assertIn('id="modeToggle"', self.html)
        self.assertIn('id="daysSelect"', self.html)
        self.assertIn('id="runButton"', self.html)

    def test_page_loads_personas_and_runs_report_api(self):
        self.assertIn("/api/relationship-selfplay/personas", self.html)
        self.assertIn("/api/relationship-selfplay/run", self.html)
        self.assertIn("fetchPersonas", self.html)
        self.assertIn("runRelationshipTest", self.html)

    def test_page_surfaces_state_hook_and_violations(self):
        self.assertIn("next_hook", self.html)
        self.assertIn("state", self.html)
        self.assertIn("violations", self.html)
        self.assertIn("companion_action", self.html)


if __name__ == "__main__":
    unittest.main()
