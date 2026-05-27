import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCENARIO_PATH = ROOT / "scripts" / "scenario.py"


def read_text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def load_scenario_module():
    spec = importlib.util.spec_from_file_location("scenario", SCENARIO_PATH)
    if spec is None or spec.loader is None:
        raise AssertionError("could not load scripts/scenario.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["scenario"] = module
    spec.loader.exec_module(module)
    return module


def scenario_names() -> list[str]:
    return list(load_scenario_module().SCENARIOS.keys())


class WorkshopDocsTest(unittest.TestCase):
    def test_required_workshop_docs_exist(self) -> None:
        required_paths = [
            "docs/workshop/instructor-guide.md",
            "docs/workshop/student-worksheet.md",
            *[f"docs/workshop/scenarios/{name}.md" for name in scenario_names()],
        ]
        missing = [path for path in required_paths if not (ROOT / path).exists()]
        self.assertEqual([], missing)

    def test_readme_links_to_workshop_docs_and_commands(self) -> None:
        readme = read_text("README.md")
        for expected in [
            "docs/workshop/instructor-guide.md",
            "docs/workshop/student-worksheet.md",
            "make scenario-list",
            "make scenario-start NAME=checkout-latency",
            "make scenario-reset",
        ]:
            self.assertIn(expected, readme)

    def test_student_facing_urls_do_not_include_instructor_console(self) -> None:
        readme = read_text("README.md")
        student_section = readme.split("## Student-facing URLs", 1)[1].split("\n## ", 1)[0]
        self.assertNotIn("Instructor fault console", student_section)
        self.assertNotIn("localhost:8088", student_section)
        self.assertIn("## Instructor-only local URL", readme)

    def test_workshop_traffic_commands_run_long_enough_and_reset_first(self) -> None:
        readme = read_text("README.md")
        guide = read_text("docs/workshop/instructor-guide.md")
        workshop_traffic_command = "make traffic-start TRAFFIC_DURATION=2h"
        self.assertIn(workshop_traffic_command, readme)
        self.assertIn(
            "make up\nmake scenario-reset\nmake traffic-start TRAFFIC_DURATION=2h",
            guide,
        )
        self.assertIn(
            "make scenario-reset\nmake traffic-stop\nmake traffic-start TRAFFIC_DURATION=2h",
            guide,
        )
        self.assertIn(
            "make restart\nmake scenario-reset\nmake traffic-start TRAFFIC_DURATION=2h",
            guide,
        )

    def test_each_scenario_card_has_commands_and_expected_evidence(self) -> None:
        for name in scenario_names():
            with self.subTest(name=name):
                card = read_text(f"docs/workshop/scenarios/{name}.md")
                self.assertIn(f"make scenario-start NAME={name}", card)
                self.assertIn("make scenario-reset", card)
                self.assertIn("## Expected evidence", card)
                self.assertIn("## If students get stuck", card)

    def test_each_scenario_card_matches_configured_target_and_scope(self) -> None:
        scenario = load_scenario_module()
        for name, metadata in scenario.SCENARIOS.items():
            with self.subTest(name=name):
                card = read_text(f"docs/workshop/scenarios/{name}.md")
                for step in metadata["steps"]:
                    self.assertIn(step["target"], card)
                    scope = step.get("body", {}).get("scope")
                    if scope:
                        self.assertIn(scope, card)

    def test_instructor_guide_references_every_scenario(self) -> None:
        guide = read_text("docs/workshop/instructor-guide.md")
        for name in scenario_names():
            self.assertIn(name, guide)


if __name__ == "__main__":
    unittest.main()
