import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SCENARIOS = ["checkout-latency", "products-errors", "cpu-hot-replica", "db-slowdown"]


def read_text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


class WorkshopDocsTest(unittest.TestCase):
    def test_required_workshop_docs_exist(self) -> None:
        required_paths = [
            "docs/workshop/instructor-guide.md",
            "docs/workshop/student-worksheet.md",
            *[f"docs/workshop/scenarios/{name}.md" for name in SCENARIOS],
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

    def test_each_scenario_card_has_commands_and_expected_evidence(self) -> None:
        for name in SCENARIOS:
            with self.subTest(name=name):
                card = read_text(f"docs/workshop/scenarios/{name}.md")
                self.assertIn(f"make scenario-start NAME={name}", card)
                self.assertIn("make scenario-reset", card)
                self.assertIn("## Expected evidence", card)
                self.assertIn("## If students get stuck", card)

    def test_instructor_guide_references_every_scenario(self) -> None:
        guide = read_text("docs/workshop/instructor-guide.md")
        for name in SCENARIOS:
            self.assertIn(name, guide)


if __name__ == "__main__":
    unittest.main()
