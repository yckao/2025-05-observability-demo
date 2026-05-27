import importlib.util
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCENARIO_PATH = ROOT / "scripts" / "scenario.py"


def load_scenario_module():
    spec = importlib.util.spec_from_file_location("scenario", SCENARIO_PATH)
    if spec is None or spec.loader is None:
        raise AssertionError("could not load scripts/scenario.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["scenario"] = module
    spec.loader.exec_module(module)
    return module


def make_targets() -> set[str]:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    return set(re.findall(r"^([A-Za-z0-9_.-]+):", makefile, flags=re.MULTILINE))


class ScenarioCliTest(unittest.TestCase):
    def test_expected_scenarios_are_defined(self) -> None:
        scenario = load_scenario_module()
        self.assertEqual(
            ["checkout-latency", "products-errors", "cpu-hot-replica", "db-slowdown"],
            list(scenario.SCENARIOS.keys()),
        )

    def test_start_plan_resets_all_replicas_before_applying_fault(self) -> None:
        scenario = load_scenario_module()
        plans = scenario.planned_requests("start", "checkout-latency", "http://demo-admin")
        self.assertEqual(4, len(plans))
        self.assertEqual(
            [
                "http://demo-admin/api/fault/reset?target=backend-1",
                "http://demo-admin/api/fault/reset?target=backend-2",
                "http://demo-admin/api/fault/reset?target=backend-3",
            ],
            [plan.url for plan in plans[:3]],
        )
        self.assertEqual("POST", plans[3].method)
        self.assertEqual("http://demo-admin/api/fault/configure?target=backend-2", plans[3].url)
        self.assertEqual("/api/checkout", plans[3].body["scope"])
        self.assertEqual(1500, plans[3].body["latency_ms"])

    def test_dry_run_outputs_json_plan(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(SCENARIO_PATH), "start", "products-errors", "--dry-run"],
            cwd=ROOT,
            check=True,
            text=True,
            capture_output=True,
        )
        payload = json.loads(completed.stdout)
        self.assertEqual("products-errors", payload["scenario"])
        self.assertEqual("dry-run", payload["mode"])
        self.assertEqual("/api/fault/configure?target=backend-1", payload["requests"][-1]["url_path"])
        self.assertEqual(35, payload["requests"][-1]["body"]["error_rate"])

    def test_makefile_exposes_scenario_targets(self) -> None:
        targets = make_targets()
        for target in ["scenario-list", "scenario-start", "scenario-status", "scenario-reset"]:
            self.assertIn(target, targets)


if __name__ == "__main__":
    unittest.main()
