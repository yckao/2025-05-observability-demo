# Workshop Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the observability demo into a polished 60–90 minute instructor-led workshop with repeatable hidden scenarios, Cloudflare-friendly public URLs, Grafana-based profile exploration, fast checks, and lighter code duplication.

**Architecture:** Keep the current Docker Compose topology and FastAPI frontend/backend services. Add a thin named-scenario CLI around the existing hidden fault endpoints, workshop docs around the lesson flow, and a small shared Python helper package for common logging, telemetry, and request metric behavior.

**Tech Stack:** Docker Compose, Make, Python standard library tests (`unittest`), FastAPI, Prometheus client, OpenTelemetry, Grafana dashboards, k6, shell/Python scripts.

---

## File Structure

Create and modify these files:

- `tests/__init__.py`: marks `tests` as an importable test package.
- `tests/test_static_contracts.py`: fast static checks for Make targets, hidden student routes, and core repo paths.
- `tests/test_scenarios.py`: unit tests for the named scenario CLI and Make scenario targets.
- `tests/test_workshop_docs.py`: checks that workshop docs and scenario cards exist and stay linked from the README.
- `tests/test_public_surface.py`: checks Cloudflare-friendly browser links and default public port exposure.
- `tests/test_shared_helpers.py`: checks shared helper behavior and verifies frontend/backend import shared helpers.
- `scripts/scenario.py`: standard-library CLI for listing, starting, resetting, and checking named workshop scenarios.
- `docs/workshop/instructor-guide.md`: timed instructor runbook.
- `docs/workshop/student-worksheet.md`: student handout for the main investigation path plus deeper prompts.
- `docs/workshop/scenarios/checkout-latency.md`: scenario card for slow checkout.
- `docs/workshop/scenarios/products-errors.md`: scenario card for product API errors.
- `docs/workshop/scenarios/cpu-hot-replica.md`: scenario card for CPU-heavy backend replica.
- `docs/workshop/scenarios/db-slowdown.md`: optional database wait scenario card.
- `README.md`: concise landing page that points to workshop docs and uses only student UI plus Grafana as student-facing URLs.
- `.env.example`: adds public URL knobs for Cloudflare Tunnel lessons.
- `Makefile`: adds `check` and named scenario targets.
- `docker-compose.yml`: adds configurable public Grafana URL, removes non-student public port mappings by default, and later switches app build contexts so both services can copy the shared helper package.
- `apps/frontend/app/main.py`: passes `PUBLIC_GRAFANA_URL` into the student template and imports shared helper code.
- `apps/frontend/app/templates/index.html`: replaces direct Pyroscope UI link with a Grafana profiles link.
- `config/grafana/dashboards/student/02-service-drilldown.json`: replaces direct Pyroscope URL with a Grafana Explore link.
- `config/grafana/dashboards/student/04-logs-traces-profiles.json`: replaces direct Pyroscope URL with Grafana-based profile instructions.
- `apps/shared/observability_demo_shared/__init__.py`: shared helper package marker.
- `apps/shared/observability_demo_shared/logging.py`: shared logfmt, JSON logging, and trace ID helpers.
- `apps/shared/observability_demo_shared/request_metrics.py`: shared Prometheus metric construction and byte-count helpers.
- `apps/shared/observability_demo_shared/telemetry.py`: shared OpenTelemetry and Pyroscope setup.
- `apps/backend/Dockerfile`: copies the shared package from the expanded app build context.
- `apps/frontend/Dockerfile`: copies the shared package from the expanded app build context.
- Delete after migration: `apps/backend/app/logging_config.py`, `apps/backend/app/telemetry.py`, `apps/frontend/app/logging_config.py`, `apps/frontend/app/telemetry.py`.

---

## Task 1: Add Fast Static Check Harness

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/test_static_contracts.py`
- Modify: `Makefile`

- [ ] **Step 1: Create the failing static contract test**

Create `tests/__init__.py` as an empty file.

Create `tests/test_static_contracts.py` with this content:

```python
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def make_targets() -> set[str]:
    makefile = read_text("Makefile")
    return set(re.findall(r"^([A-Za-z0-9_.-]+):", makefile, flags=re.MULTILINE))


class StaticContractsTest(unittest.TestCase):
    def test_make_check_target_exists(self) -> None:
        self.assertIn("check", make_targets())

    def test_student_routes_hide_instructor_controls(self) -> None:
        nginx = read_text("config/nginx/nginx.conf")
        self.assertIn(
            "location /api/fault/ {\n      access_log off;\n      return 404;\n    }",
            nginx,
        )
        self.assertIn(
            "location /admin {\n      access_log off;\n      return 404;\n    }",
            nginx,
        )

    def test_core_paths_exist(self) -> None:
        required_paths = [
            "README.md",
            "Makefile",
            "docker-compose.yml",
            "config/nginx/nginx.conf",
            "config/grafana/provisioning/datasources/datasources.yml",
            "config/grafana/dashboards/student/00-start-here.json",
            "apps/frontend/app/main.py",
            "apps/backend/app/main.py",
            "load/k6-consistent.js",
        ]
        missing = [path for path in required_paths if not (ROOT / path).exists()]
        self.assertEqual([], missing)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test and verify it fails for the missing Make target**

Run:

```bash
python3 -m unittest tests.test_static_contracts -v
```

Expected result:

```text
FAIL: test_make_check_target_exists
AssertionError: 'check' not found
```

The other two tests should pass.

- [ ] **Step 3: Add the `check` Make target**

In `Makefile`, replace the existing `.PHONY` line with this line:

```make
.PHONY: up down restart ps logs load-smoke load-steady load-spike load-consistent traffic-start traffic-stop traffic-status traffic-logs fault-reset clean check
```

At the end of `Makefile`, after the `clean` target, add this target. The recipe line must start with a real tab character.

```make
check:
	python3 -m unittest discover -s tests -v
```

- [ ] **Step 4: Run the static contract test again**

Run:

```bash
python3 -m unittest tests.test_static_contracts -v
```

Expected result:

```text
Ran 3 tests
OK
```

- [ ] **Step 5: Run the new aggregate check command**

Run:

```bash
make check
```

Expected result:

```text
Ran 3 tests
OK
```

- [ ] **Step 6: Commit Task 1**

Run:

```bash
git add Makefile tests/__init__.py tests/test_static_contracts.py
git commit -m "test: add static contract checks"
```

---

## Task 2: Add Named Scenario CLI and Make Targets

**Files:**
- Create: `scripts/scenario.py`
- Create: `tests/test_scenarios.py`
- Modify: `Makefile`

- [ ] **Step 1: Write failing tests for scenario definitions and Make targets**

Create `tests/test_scenarios.py` with this content:

```python
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
```

- [ ] **Step 2: Run the scenario tests and verify they fail because the CLI is missing**

Run:

```bash
python3 -m unittest tests.test_scenarios -v
```

Expected result:

```text
FileNotFoundError: scripts/scenario.py
```

- [ ] **Step 3: Create the scenario CLI**

Create `scripts/scenario.py` with this content:

```python
#!/usr/bin/env python3
import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

DEFAULT_ADMIN_URL = "http://localhost:8088"
REPLICAS = ("backend-1", "backend-2", "backend-3")

SCENARIOS: dict[str, dict[str, Any]] = {
    "checkout-latency": {
        "title": "Checkout latency on one backend replica",
        "description": "backend-2 adds latency and jitter only to /api/checkout.",
        "steps": [
            {
                "method": "POST",
                "target": "backend-2",
                "path": "/api/fault/configure",
                "body": {
                    "scope": "/api/checkout",
                    "latency_ms": 1500,
                    "jitter_ms": 300,
                    "error_rate": 0,
                    "error_status": 503,
                    "cpu_ms": 0,
                    "db_delay_ms": 0,
                },
            }
        ],
    },
    "products-errors": {
        "title": "Intermittent product API errors",
        "description": "backend-1 returns intermittent 503 responses for /api/products.",
        "steps": [
            {
                "method": "POST",
                "target": "backend-1",
                "path": "/api/fault/configure",
                "body": {
                    "scope": "/api/products",
                    "latency_ms": 0,
                    "jitter_ms": 0,
                    "error_rate": 35,
                    "error_status": 503,
                    "cpu_ms": 0,
                    "db_delay_ms": 0,
                },
            }
        ],
    },
    "cpu-hot-replica": {
        "title": "CPU-heavy backend replica",
        "description": "backend-3 burns CPU on matching backend API requests.",
        "steps": [
            {
                "method": "POST",
                "target": "backend-3",
                "path": "/api/fault/configure",
                "body": {
                    "scope": "/api/",
                    "latency_ms": 0,
                    "jitter_ms": 0,
                    "error_rate": 0,
                    "error_status": 503,
                    "cpu_ms": 750,
                    "db_delay_ms": 0,
                },
            }
        ],
    },
    "db-slowdown": {
        "title": "Database wait during checkout",
        "description": "backend-2 waits before checkout database work to mimic a DB slowdown symptom.",
        "steps": [
            {
                "method": "POST",
                "target": "backend-2",
                "path": "/api/fault/configure",
                "body": {
                    "scope": "/api/checkout",
                    "latency_ms": 0,
                    "jitter_ms": 0,
                    "error_rate": 0,
                    "error_status": 503,
                    "cpu_ms": 0,
                    "db_delay_ms": 1200,
                },
            }
        ],
    },
}


@dataclass(frozen=True)
class HttpRequestPlan:
    method: str
    url: str
    body: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        parsed = urllib.parse.urlparse(self.url)
        return {
            "method": self.method,
            "url": self.url,
            "url_path": parsed.path + (f"?{parsed.query}" if parsed.query else ""),
            "body": self.body,
        }


def normalize_admin_url(admin_url: str) -> str:
    return admin_url.rstrip("/")


def fault_url(admin_url: str, path: str, target: str) -> str:
    separator = "&" if "?" in path else "?"
    return f"{normalize_admin_url(admin_url)}{path}{separator}target={urllib.parse.quote(target)}"


def reset_plans(admin_url: str) -> list[HttpRequestPlan]:
    return [HttpRequestPlan("GET", fault_url(admin_url, "/api/fault/reset", replica)) for replica in REPLICAS]


def status_plans(admin_url: str) -> list[HttpRequestPlan]:
    return [HttpRequestPlan("GET", fault_url(admin_url, "/api/fault/status", replica)) for replica in REPLICAS]


def scenario_plans(name: str, admin_url: str) -> list[HttpRequestPlan]:
    if name not in SCENARIOS:
        raise KeyError(name)
    plans: list[HttpRequestPlan] = []
    for step in SCENARIOS[name]["steps"]:
        plans.append(
            HttpRequestPlan(
                method=step["method"],
                url=fault_url(admin_url, step["path"], step["target"]),
                body=step.get("body"),
            )
        )
    return plans


def planned_requests(action: str, name: str | None = None, admin_url: str = DEFAULT_ADMIN_URL) -> list[HttpRequestPlan]:
    if action == "start":
        if name is None:
            raise ValueError("scenario name is required for start")
        return reset_plans(admin_url) + scenario_plans(name, admin_url)
    if action == "reset":
        return reset_plans(admin_url)
    if action == "status":
        return status_plans(admin_url)
    raise ValueError(f"unknown action: {action}")


def execute_plan(plan: HttpRequestPlan, timeout_seconds: int) -> dict[str, Any]:
    data = None
    headers = {"Accept": "application/json"}
    if plan.body is not None:
        data = json.dumps(plan.body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(plan.url, data=data, headers=headers, method=plan.method)
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        text = response.read().decode("utf-8")
        try:
            body: Any = json.loads(text)
        except json.JSONDecodeError:
            body = text
        return {
            "method": plan.method,
            "url": plan.url,
            "status": response.status,
            "body": body,
        }


def execute_plans(plans: list[HttpRequestPlan], timeout_seconds: int) -> list[dict[str, Any]]:
    results = []
    for plan in plans:
        try:
            results.append(execute_plan(plan, timeout_seconds))
        except urllib.error.URLError as exc:
            raise SystemExit(f"scenario command failed for {plan.url}: {exc}") from exc
    return results


def print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage observability demo workshop scenarios.")
    parser.add_argument("--admin-url", default=DEFAULT_ADMIN_URL, help="Instructor fault console URL.")
    parser.add_argument("--timeout", type=int, default=5, help="HTTP timeout in seconds.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="List scenario names.")
    list_parser.add_argument("--json", action="store_true", help="Print machine-readable scenario metadata.")

    start_parser = subparsers.add_parser("start", help="Reset all replicas, then start a named scenario.")
    start_parser.add_argument("name", choices=SCENARIOS.keys())
    start_parser.add_argument("--dry-run", action="store_true", help="Print planned requests without sending them.")

    reset_parser = subparsers.add_parser("reset", help="Reset all backend replicas.")
    reset_parser.add_argument("--dry-run", action="store_true", help="Print planned requests without sending them.")

    status_parser = subparsers.add_parser("status", help="Read fault status for all backend replicas.")
    status_parser.add_argument("--dry-run", action="store_true", help="Print planned requests without sending them.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "list":
        if args.json:
            print_json({"scenarios": SCENARIOS})
        else:
            for name, metadata in SCENARIOS.items():
                print(f"{name}\t{metadata['title']}")
        return 0

    scenario_name = getattr(args, "name", None)
    plans = planned_requests(args.command, scenario_name, args.admin_url)
    if getattr(args, "dry_run", False):
        print_json(
            {
                "mode": "dry-run",
                "action": args.command,
                "scenario": scenario_name,
                "requests": [plan.as_dict() for plan in plans],
            }
        )
        return 0

    results = execute_plans(plans, args.timeout)
    print_json({"mode": "executed", "action": args.command, "scenario": scenario_name, "results": results})
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
```

Make it executable:

```bash
chmod +x scripts/scenario.py
```

- [ ] **Step 4: Add Make scenario targets**

Update the `.PHONY` line in `Makefile` to include scenario targets:

```make
.PHONY: up down restart ps logs load-smoke load-steady load-spike load-consistent traffic-start traffic-stop traffic-status traffic-logs fault-reset clean check scenario-list scenario-start scenario-status scenario-reset
```

Add these targets after `fault-reset`. Recipe lines must begin with real tab characters.

```make
scenario-list:
	python3 scripts/scenario.py list

scenario-start:
	@test -n "$(NAME)" || (echo "usage: make scenario-start NAME=checkout-latency" >&2; exit 2)
	python3 scripts/scenario.py start "$(NAME)"

scenario-status:
	python3 scripts/scenario.py status

scenario-reset:
	python3 scripts/scenario.py reset
```

- [ ] **Step 5: Run scenario tests**

Run:

```bash
python3 -m unittest tests.test_scenarios -v
```

Expected result:

```text
Ran 4 tests
OK
```

- [ ] **Step 6: Run aggregate checks**

Run:

```bash
make check
```

Expected result:

```text
Ran 7 tests
OK
```

- [ ] **Step 7: Commit Task 2**

Run:

```bash
git add Makefile scripts/scenario.py tests/test_scenarios.py
git commit -m "feat: add named workshop scenarios"
```

---

## Task 3: Add Workshop Docs, Scenario Cards, and README Landing Page

**Files:**
- Create: `tests/test_workshop_docs.py`
- Create: `docs/workshop/instructor-guide.md`
- Create: `docs/workshop/student-worksheet.md`
- Create: `docs/workshop/scenarios/checkout-latency.md`
- Create: `docs/workshop/scenarios/products-errors.md`
- Create: `docs/workshop/scenarios/cpu-hot-replica.md`
- Create: `docs/workshop/scenarios/db-slowdown.md`
- Modify: `README.md`

- [ ] **Step 1: Write failing docs contract tests**

Create `tests/test_workshop_docs.py` with this content:

```python
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
```

- [ ] **Step 2: Run docs tests and verify they fail because workshop docs are missing**

Run:

```bash
python3 -m unittest tests.test_workshop_docs -v
```

Expected result:

```text
FAIL: test_required_workshop_docs_exist
```

- [ ] **Step 3: Create the workshop instructor guide**

Create `docs/workshop/instructor-guide.md` with this content:

```markdown
# Observability Demo Instructor Guide

This guide runs a 60–90 minute instructor-led workshop with one shared stack. Students use the student app and Grafana. The instructor controls hidden scenarios locally.

## Public surfaces for students

Share only these URLs with students:

- Student UI: your public URL for port `8080`.
- Grafana: your public URL for port `3000`.

Do not share the instructor console URL or fault endpoints.

## Instructor preflight

Run these commands before class:

```bash
make check
make up
make traffic-start
make scenario-reset
```

Open Grafana and confirm these dashboards load:

- `00 Start Here`
- `01 Operations Overview`
- `02 Service Drilldown`
- `03 Checkout Journey`
- `04 Logs, Traces, Profiles`

Confirm the student app can generate traffic:

```bash
curl -fsS http://localhost:8080/health
curl -fsS http://localhost:8080/api/health
```

Confirm hidden controls stay hidden from the student port:

```bash
curl -i http://localhost:8080/admin
curl -i http://localhost:8080/api/fault/status
```

Both responses should be `404`.

## Timing plan

| Time | Segment | Instructor actions | Student activity |
| --- | --- | --- | --- |
| 0–10 min | Orientation | Explain app topology and the two student URLs. | Open student UI and Grafana. |
| 10–20 min | Baseline | Keep `make traffic-start` running. Show RED and USE signals. | Fill in baseline observations. |
| 20–40 min | Scenario 1 | Run `make scenario-start NAME=checkout-latency`. | Investigate latency by route and replica. |
| 40–55 min | Correlation | Open logs and traces from Grafana. | Record the strongest evidence. |
| 55–70 min | Scenario 2 | Run `make scenario-reset`, then `make scenario-start NAME=products-errors` or `make scenario-start NAME=cpu-hot-replica`. | Investigate errors or saturation. |
| 70–85 min | Optional challenge | Run `make scenario-reset`, then `make scenario-start NAME=db-slowdown`. | Advanced students compare app latency with DB symptoms. |
| 85–90 min | Recap | Run `make scenario-reset`. Summarize methods. | Share hypotheses and lessons. |

For a 60 minute class, skip the optional challenge and recap after Scenario 2.

## Scenario commands

List scenarios:

```bash
make scenario-list
```

Start a scenario:

```bash
make scenario-start NAME=checkout-latency
```

Check current fault state:

```bash
make scenario-status
```

Reset all replicas:

```bash
make scenario-reset
```

## Scenario order

Recommended main path:

1. `checkout-latency`
2. `products-errors`
3. `cpu-hot-replica`
4. `db-slowdown` as the optional deeper challenge

Scenario cards:

- [checkout-latency](scenarios/checkout-latency.md)
- [products-errors](scenarios/products-errors.md)
- [cpu-hot-replica](scenarios/cpu-hot-replica.md)
- [db-slowdown](scenarios/db-slowdown.md)

## Facilitation prompts

Use these prompts before giving hints:

- What changed first: traffic, errors, latency, or saturation?
- Is the symptom global, service-specific, route-specific, or replica-specific?
- Which dashboard panel gives the strongest evidence?
- Which log line or trace supports the metric signal?
- What would you check next if this were production?

## Recovery

Return to baseline:

```bash
make scenario-reset
make traffic-stop
make traffic-start
```

If dashboards are empty, wait two scrape intervals, then generate traffic:

```bash
make load-smoke
```

If Grafana cannot show profiles, confirm the Pyroscope datasource exists in Grafana. Pyroscope is intentionally internal to Docker Compose; students should use Grafana for profiles.

If the stack is unhealthy, restart it:

```bash
make restart
make traffic-start
make scenario-reset
```
```

- [ ] **Step 4: Create the student worksheet**

Create `docs/workshop/student-worksheet.md` with this content:

```markdown
# Observability Demo Student Worksheet

Your instructor will provide two URLs:

- Student UI: use this to generate user activity.
- Grafana: use this to investigate metrics, logs, traces, and profiles.

Start in Grafana with the `00 Start Here` dashboard.

## Baseline

Open the student UI and click a few traffic buttons. In Grafana, record what normal looks like.

| Question | Observation |
| --- | --- |
| Which services are receiving traffic? | |
| Which routes are active? | |
| What is the approximate p95 latency? | |
| Are errors present? | |
| Which backend replicas are serving requests? | |

## Investigation loop

Use this loop for each hidden scenario:

1. Look for a symptom in `01 Operations Overview`.
2. Decide whether the symptom is latency, traffic, errors, or saturation.
3. Open `02 Service Drilldown` and narrow by service and replica.
4. Check logs for the affected service or route.
5. Use a trace ID to inspect a trace in Tempo when a request is slow or failed.
6. Use Grafana profile views when CPU looks high.
7. Write a hypothesis and the evidence that supports it.

## Scenario notes

| Field | Notes |
| --- | --- |
| Symptom type | |
| Affected service | |
| Affected route | |
| Affected replica | |
| Best metric evidence | |
| Best log evidence | |
| Best trace evidence | |
| Profile evidence, if CPU-related | |
| Final hypothesis | |

## Optional deeper challenge

For experienced students:

- Compare route-level latency with replica-level latency.
- Find one log line that includes a useful `trace_id`.
- Explain why a high error rate and high latency require different first responses.
- Explain whether a symptom looks like application code, database wait, or infrastructure saturation.
```

- [ ] **Step 5: Create the `checkout-latency` scenario card**

Create `docs/workshop/scenarios/checkout-latency.md` with this content:

```markdown
# Scenario: checkout-latency

## Instructor setup

```bash
make scenario-reset
make scenario-start NAME=checkout-latency
```

## Story for students

Customers say checkout sometimes feels slow. The rest of the shop appears mostly healthy.

## Student-visible symptoms

- Higher p95 latency on checkout traffic.
- The symptom is stronger on one backend replica.
- Slow traces include frontend to backend spans for checkout.

## Investigation path

1. Open `01 Operations Overview` and identify latency as the main symptom.
2. Open `02 Service Drilldown` and filter to `backend`.
3. Compare replicas and routes.
4. Open `03 Checkout Journey` to follow the user flow.
5. Use logs with trace IDs to open a slow trace in Tempo.

## Expected evidence

- `demo_http_request_duration_seconds` increases for `/api/checkout`.
- `backend-2` is the affected replica.
- Error rate stays near baseline.
- Traces show slow checkout backend work.

## If students get stuck

Ask: Is every route slow, or only checkout? Is every backend replica slow, or one replica?

## Reset

```bash
make scenario-reset
```
```

- [ ] **Step 6: Create the `products-errors` scenario card**

Create `docs/workshop/scenarios/products-errors.md` with this content:

```markdown
# Scenario: products-errors

## Instructor setup

```bash
make scenario-reset
make scenario-start NAME=products-errors
```

## Story for students

Some product page requests fail, but the application still responds successfully part of the time.

## Student-visible symptoms

- 5xx error ratio increases for product requests.
- Logs include backend error events with trace IDs.
- Successful traffic continues on other routes and replicas.

## Investigation path

1. Open `01 Operations Overview` and identify errors as the main symptom.
2. Open `02 Service Drilldown` and filter to `backend`.
3. Compare route and status labels.
4. Open logs for backend services.
5. Use a failed request trace ID to inspect the trace.

## Expected evidence

- Error ratio increases for `/api/products`.
- `backend-1` is the affected replica.
- Backend JSON error logs include status `503`.
- Trace IDs from failed responses connect logs to Tempo.

## If students get stuck

Ask: Which route has 5xx responses? Are the failures evenly spread across replicas?

## Reset

```bash
make scenario-reset
```
```

- [ ] **Step 7: Create the `cpu-hot-replica` scenario card**

Create `docs/workshop/scenarios/cpu-hot-replica.md` with this content:

```markdown
# Scenario: cpu-hot-replica

## Instructor setup

```bash
make scenario-reset
make scenario-start NAME=cpu-hot-replica
```

## Story for students

The service feels slower under normal traffic even though errors are not the first obvious symptom.

## Student-visible symptoms

- One backend replica shows high CPU utilization.
- Latency can increase while error rate stays near baseline.
- Grafana profile views show CPU-heavy application work.

## Investigation path

1. Open `01 Operations Overview` and compare latency with saturation.
2. Open `02 Service Drilldown` and filter to `backend`.
3. Find the backend replica with high CPU utilization.
4. Open `04 Logs, Traces, Profiles`.
5. Use Grafana profile exploration with the Pyroscope datasource.

## Expected evidence

- `backend-3` is the affected replica.
- Container CPU utilization is higher for that replica.
- Request latency can rise without matching 5xx growth.
- Profiles point to CPU burn in the backend process.

## If students get stuck

Ask: Which signal changed besides latency? What does the affected replica have in common across metrics and profiles?

## Reset

```bash
make scenario-reset
```
```

- [ ] **Step 8: Create the `db-slowdown` scenario card**

Create `docs/workshop/scenarios/db-slowdown.md` with this content:

```markdown
# Scenario: db-slowdown

## Instructor setup

```bash
make scenario-reset
make scenario-start NAME=db-slowdown
```

## Story for students

Checkout is slow, but CPU is not the most convincing explanation.

## Student-visible symptoms

- Checkout latency rises on one backend replica.
- Error rate remains near baseline.
- Traces show time spent around backend checkout and database work.

## Investigation path

1. Open `01 Operations Overview` and identify latency as the main symptom.
2. Open `03 Checkout Journey` to follow frontend, backend, and database spans.
3. Compare CPU utilization with request duration.
4. Use logs and traces to decide whether this looks CPU-bound or wait-bound.

## Expected evidence

- `backend-2` is the affected replica.
- `/api/checkout` latency rises.
- CPU is not the strongest signal.
- Trace timing points toward waiting around checkout database work.

## If students get stuck

Ask: If latency is high but CPU is not high, what kind of waiting could explain it?

## Reset

```bash
make scenario-reset
```
```

- [ ] **Step 9: Replace README with concise workshop landing page**

Replace `README.md` with this content:

```markdown
# Observability Demo

Local teaching lab for an instructor-led observability workshop. The stack includes a small frontend, backend replicas, CockroachDB, Grafana, Prometheus, Loki, Tempo, Pyroscope, Grafana Alloy, k6 traffic, dashboards, and hidden instructor fault injection.

## Workshop docs

- [Instructor guide](docs/workshop/instructor-guide.md)
- [Student worksheet](docs/workshop/student-worksheet.md)
- [Scenario cards](docs/workshop/scenarios/)

## Architecture

```text
Students
  |
Nginx load balancer
  |
Frontend replicas: frontend-1, frontend-2, frontend-3
  |
Backend replicas: backend-1, backend-2, backend-3
  |
CockroachDB replicas: crdb-1, crdb-2, crdb-3

Telemetry collection:
Apps / Docker / cAdvisor / CockroachDB
  |
Grafana Alloy
  |
Prometheus, Loki, Tempo, Pyroscope
  |
Grafana
```

All observability storage is local Docker volume storage. No cloud account is required for the stack itself.

## Student-facing URLs

For the main workshop path, students need only two URLs:

| Surface | Local URL | Notes |
| --- | --- | --- |
| Student application | http://localhost:8080 | Generate traffic and see failed-request trace IDs. |
| Grafana | http://localhost:3000 | Dashboards, logs, traces, and profiles. Login: `admin` / `admin`. |

Pyroscope runs internally and is queried through Grafana. Students should not need a separate Pyroscope URL.

The instructor fault console is local-only by default:

| Surface | Local URL | Notes |
| --- | --- | --- |
| Instructor fault console | http://localhost:8088 | Do not share with students. |

## Start

```bash
make up
make traffic-start
```

Then open:

```text
http://localhost:8080
http://localhost:3000
```

## Cloudflare Tunnel notes

If you expose the workshop through Cloudflare Tunnel, expose only:

- port `8080` for the student application
- port `3000` for Grafana

Set `PUBLIC_GRAFANA_URL` in `.env` so the student UI links to your public Grafana URL instead of the local default.

Example:

```dotenv
PUBLIC_GRAFANA_URL=https://grafana.example.com
```

## Common commands

```bash
make up
make down
make restart
make ps
make logs
make check
```

Traffic:

```bash
make load-smoke
make load-steady
make load-spike
make load-consistent
make traffic-start
make traffic-logs
make traffic-stop
```

Named workshop scenarios:

```bash
make scenario-list
make scenario-start NAME=checkout-latency
make scenario-status
make scenario-reset
```

Clean all local data:

```bash
make clean
```

## Default lesson flow

1. Start the stack and background traffic.
2. Share the student UI and Grafana URLs.
3. Have students record a baseline in `00 Start Here` and `01 Operations Overview`.
4. Run a hidden named scenario.
5. Students investigate with metrics, logs, traces, and Grafana profile views.
6. Reset the scenario and recap.

Use the [instructor guide](docs/workshop/instructor-guide.md) for timing, prompts, scenario order, expected evidence, and recovery steps.

## Notes

- Alloy replaces Promtail and acts as the single local collector/agent.
- Application traces use OpenTelemetry OTLP to Alloy.
- Application metrics are exposed on `/metrics` and scraped by Alloy.
- Frontend, backend, and database containers have cgroup CPU and memory quotas so cAdvisor can show utilization against explicit limits.
- Container logs are collected by Alloy from Docker JSON log files and sent to Loki.
- Continuous profiles are sent from the Python SDK to Pyroscope and explored through Grafana.
- CockroachDB is used so the local database layer has three replicas without PostgreSQL replication setup.
```

- [ ] **Step 10: Run docs tests**

Run:

```bash
python3 -m unittest tests.test_workshop_docs -v
```

Expected result:

```text
Ran 4 tests
OK
```

- [ ] **Step 11: Run aggregate checks**

Run:

```bash
make check
```

Expected result:

```text
Ran 11 tests
OK
```

- [ ] **Step 12: Commit Task 3**

Run:

```bash
git add README.md docs/workshop tests/test_workshop_docs.py
git commit -m "docs: add instructor-led workshop materials"
```

---

## Task 4: Make the Public Surface Cloudflare-Friendly and Grafana-Only for Profiles

**Files:**
- Create: `tests/test_public_surface.py`
- Modify: `.env.example`
- Modify: `docker-compose.yml`
- Modify: `apps/frontend/app/main.py`
- Modify: `apps/frontend/app/templates/index.html`
- Modify: `config/grafana/dashboards/student/02-service-drilldown.json`
- Modify: `config/grafana/dashboards/student/04-logs-traces-profiles.json`
- Modify: `README.md`
- Modify: `docs/workshop/instructor-guide.md`

- [ ] **Step 1: Write failing tests for public links and port exposure**

Create `tests/test_public_surface.py` with this content:

```python
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

BROWSER_FACING_FILES = [
    "README.md",
    "docs/workshop/instructor-guide.md",
    "docs/workshop/student-worksheet.md",
    "apps/frontend/app/templates/index.html",
    "config/grafana/dashboards/student/02-service-drilldown.json",
    "config/grafana/dashboards/student/04-logs-traces-profiles.json",
]

FORBIDDEN_DEFAULT_PORT_MAPPINGS = [
    '"4040:4040"',
    '"9090:9090"',
    '"3100:3100"',
    '"3200:3200"',
    '"8081:8080"',
    '"26257:26257"',
    '"12345:12345"',
    '"4317:4317"',
    '"4318:4318"',
]


def read_text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


class PublicSurfaceTest(unittest.TestCase):
    def test_browser_facing_files_do_not_link_to_pyroscope_localhost(self) -> None:
        offenders = []
        for relative_path in BROWSER_FACING_FILES:
            text = read_text(relative_path)
            if "localhost:" "4040" in text or "http://localhost:" "4040" in text:
                offenders.append(relative_path)
        self.assertEqual([], offenders)

    def test_default_compose_exposes_only_student_app_instructor_console_and_grafana(self) -> None:
        compose = read_text("docker-compose.yml")
        for mapping in FORBIDDEN_DEFAULT_PORT_MAPPINGS:
            self.assertNotIn(mapping, compose)
        self.assertIn('"8080:80"', compose)
        self.assertIn('"8088:8088"', compose)
        self.assertIn('"3000:3000"', compose)

    def test_frontend_uses_configurable_public_grafana_url(self) -> None:
        compose = read_text("docker-compose.yml")
        frontend = read_text("apps/frontend/app/main.py")
        template = read_text("apps/frontend/app/templates/index.html")
        self.assertIn("PUBLIC_GRAFANA_URL", compose)
        self.assertIn("PUBLIC_GRAFANA_URL", frontend)
        self.assertIn("grafana_url", template)
        self.assertIn("Open Profiles in Grafana", template)

    def test_grafana_keeps_pyroscope_as_internal_datasource(self) -> None:
        datasources = read_text("config/grafana/provisioning/datasources/datasources.yml")
        self.assertIn("uid: pyroscope", datasources)
        self.assertIn("url: http://pyroscope:4040", datasources)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run public surface tests and verify they fail on current links and ports**

Run:

```bash
python3 -m unittest tests.test_public_surface -v
```

Expected result:

```text
FAIL: test_browser_facing_files_do_not_link_to_pyroscope_localhost
FAIL: test_default_compose_exposes_only_student_app_instructor_console_and_grafana
FAIL: test_frontend_uses_configurable_public_grafana_url
```

- [ ] **Step 3: Add public URL settings to `.env.example`**

Append this content to `.env.example`:

```dotenv

# Public URL used by the student UI when linking to Grafana.
# For Cloudflare Tunnel workshops, set this to the public Grafana hostname.
PUBLIC_GRAFANA_URL=http://localhost:3000
```

- [ ] **Step 4: Add `PUBLIC_GRAFANA_URL` to frontend services in Compose**

In every frontend replica environment block in `docker-compose.yml`, add this line:

```yaml
      PUBLIC_GRAFANA_URL: ${PUBLIC_GRAFANA_URL:-http://localhost:3000}
```

Each frontend environment block should contain these keys after the edit:

```yaml
      SERVICE_NAME: frontend
      REPLICA_ID: frontend-1
      BACKEND_URL: http://load-balancer/api
      PUBLIC_GRAFANA_URL: ${PUBLIC_GRAFANA_URL:-http://localhost:3000}
      OTEL_EXPORTER_OTLP_ENDPOINT: http://alloy:4317
      PYROSCOPE_SERVER_ADDRESS: http://pyroscope:4040
```

Use the matching `REPLICA_ID` for `frontend-2` and `frontend-3`.

- [ ] **Step 5: Configure Grafana root URL from the same public URL**

In the `grafana` service `environment` block in `docker-compose.yml`, add:

```yaml
      GF_SERVER_ROOT_URL: ${PUBLIC_GRAFANA_URL:-http://localhost:3000}
```

The block should include:

```yaml
      GF_SECURITY_ADMIN_USER: admin
      GF_SECURITY_ADMIN_PASSWORD: admin
      GF_USERS_DEFAULT_THEME: light
      GF_FEATURE_TOGGLES_ENABLE: traceqlEditor correlations traceToProfiles
      GF_SERVER_ROOT_URL: ${PUBLIC_GRAFANA_URL:-http://localhost:3000}
```

- [ ] **Step 6: Remove non-student default public port mappings from Compose**

In `docker-compose.yml`, remove these `ports` blocks and leave the services reachable on the Docker network:

From `crdb-1`, remove:

```yaml
    ports:
      - "26257:26257"
      - "8081:8080"
```

From `alloy`, remove:

```yaml
    ports:
      - "12345:12345"
      - "4317:4317"
      - "4318:4318"
```

From `prometheus`, remove:

```yaml
    ports:
      - "9090:9090"
```

From `loki`, remove:

```yaml
    ports:
      - "3100:3100"
```

From `tempo`, remove:

```yaml
    ports:
      - "3200:3200"
```

From `pyroscope`, remove:

```yaml
    ports:
      - "4040:4040"
```

Keep these mappings:

```yaml
    ports:
      - "8080:80"
      - "8088:8088"
```

for `load-balancer`, and:

```yaml
    ports:
      - "3000:3000"
```

for `grafana`.

- [ ] **Step 7: Pass Grafana URL from frontend app into the template**

In `apps/frontend/app/main.py`, add this constant after `BACKEND_URL`:

```python
PUBLIC_GRAFANA_URL = os.getenv("PUBLIC_GRAFANA_URL", "http://localhost:3000").rstrip("/")
```

In the `index` route template context, add `grafana_url`:

```python
@app.get("/")
def index(request: Request):
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "replica": REPLICA_ID,
            "backend_url": BACKEND_URL,
            "grafana_url": PUBLIC_GRAFANA_URL,
        },
    )
```

- [ ] **Step 8: Replace the student UI Pyroscope button with a Grafana profiles button**

In `apps/frontend/app/templates/index.html`, replace:

```html
    <a class="button secondary" href="http://localhost:3000" target="_blank" rel="noreferrer">Open Grafana</a>
    <a class="button secondary" href="<direct-pyroscope-local-url>" target="_blank" rel="noreferrer">Open Pyroscope</a>
```

with:

```html
    <a class="button secondary" href="{{ grafana_url }}" target="_blank" rel="noreferrer">Open Grafana</a>
    <a class="button secondary" href="{{ grafana_url }}/d/obs-demo-traces-profiles/04-logs-traces-profiles" target="_blank" rel="noreferrer">Open Profiles in Grafana</a>
```

- [ ] **Step 9: Replace direct Pyroscope links in Grafana dashboard JSON**

In `config/grafana/dashboards/student/02-service-drilldown.json`, replace the link object with title `Open Pyroscope` with this object:

```json
{"asDropdown": false, "icon": "external link", "includeVars": true, "keepTime": true, "tags": [], "targetBlank": true, "title": "Explore Profiles in Grafana", "tooltip": "Open Grafana Explore and select the Pyroscope datasource", "type": "link", "url": "/explore"}
```

In `config/grafana/dashboards/student/04-logs-traces-profiles.json`, replace the link object with title `Open Pyroscope` with this object:

```json
{"asDropdown": false, "icon": "external link", "includeVars": false, "keepTime": true, "tags": [], "targetBlank": true, "title": "Explore Profiles in Grafana", "tooltip": "Open Grafana Explore and select the Pyroscope datasource", "type": "link", "url": "/explore"}
```

In the same `04-logs-traces-profiles.json` file, replace the text panel content that currently says `open Pyroscope` with this content:

```text
Trace workflow:\n1. Generate traffic with /shop or make load-steady.\n2. Watch for slow or failed requests on the student page.\n3. Use Logs With Trace IDs and click the derived Tempo link.\n4. In Tempo, inspect frontend -> backend -> SQL spans.\n5. If CPU utilization is high, use Grafana Explore with the Pyroscope datasource and select backend.* or frontend.* profiles.
```

- [ ] **Step 10: Update docs wording for Grafana-only profiles**

In `README.md`, ensure the student-facing URL table has only student application and Grafana rows, and keep this sentence:

```markdown
Pyroscope runs internally and is queried through Grafana. Students should not need a separate Pyroscope URL.
```

In `docs/workshop/instructor-guide.md`, keep this recovery note:

```markdown
If Grafana cannot show profiles, confirm the Pyroscope datasource exists in Grafana. Pyroscope is intentionally internal to Docker Compose; students should use Grafana for profiles.
```

- [ ] **Step 11: Run public surface tests**

Run:

```bash
python3 -m unittest tests.test_public_surface -v
```

Expected result:

```text
Ran 4 tests
OK
```

- [ ] **Step 12: Validate Compose syntax**

Run:

```bash
docker compose config --quiet
```

Expected result: no output and exit code `0`.

- [ ] **Step 13: Run aggregate checks**

Run:

```bash
make check
```

Expected result:

```text
Ran 15 tests
OK
```

- [ ] **Step 14: Commit Task 4**

Run:

```bash
git add .env.example README.md docker-compose.yml apps/frontend/app/main.py apps/frontend/app/templates/index.html config/grafana/dashboards/student/02-service-drilldown.json config/grafana/dashboards/student/04-logs-traces-profiles.json docs/workshop/instructor-guide.md tests/test_public_surface.py
git commit -m "feat: use Grafana as the public profile surface"
```

---

## Task 5: Extract Shared Python Logging, Telemetry, and Request Metric Helpers

**Files:**
- Create: `tests/test_shared_helpers.py`
- Create: `apps/shared/observability_demo_shared/__init__.py`
- Create: `apps/shared/observability_demo_shared/logging.py`
- Create: `apps/shared/observability_demo_shared/request_metrics.py`
- Create: `apps/shared/observability_demo_shared/telemetry.py`
- Modify: `docker-compose.yml`
- Modify: `apps/backend/Dockerfile`
- Modify: `apps/frontend/Dockerfile`
- Modify: `apps/backend/app/main.py`
- Modify: `apps/frontend/app/main.py`
- Delete: `apps/backend/app/logging_config.py`
- Delete: `apps/backend/app/telemetry.py`
- Delete: `apps/frontend/app/logging_config.py`
- Delete: `apps/frontend/app/telemetry.py`

- [ ] **Step 1: Write failing tests for shared helper extraction**

Create `tests/test_shared_helpers.py` with this content:

```python
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHARED_PATH = ROOT / "apps" / "shared"


class SharedHelpersTest(unittest.TestCase):
    def test_logfmt_formatting_quotes_spaces_and_equals(self) -> None:
        sys.path.insert(0, str(SHARED_PATH))
        try:
            from observability_demo_shared.logging import format_logfmt

            self.assertEqual(
                'level=info path=/api/products message="slow request" detail="a=b"',
                format_logfmt(
                    {
                        "level": "info",
                        "path": "/api/products",
                        "message": "slow request",
                        "detail": "a=b",
                    }
                ),
            )
        finally:
            sys.path.remove(str(SHARED_PATH))

    def test_services_import_shared_helpers(self) -> None:
        for relative_path in ["apps/backend/app/main.py", "apps/frontend/app/main.py"]:
            with self.subTest(path=relative_path):
                text = (ROOT / relative_path).read_text(encoding="utf-8")
                self.assertIn("observability_demo_shared", text)
                self.assertNotIn("from .logging_config", text)
                self.assertNotIn("from .telemetry", text)

    def test_old_duplicate_helper_modules_are_removed(self) -> None:
        removed_paths = [
            "apps/backend/app/logging_config.py",
            "apps/backend/app/telemetry.py",
            "apps/frontend/app/logging_config.py",
            "apps/frontend/app/telemetry.py",
        ]
        existing = [path for path in removed_paths if (ROOT / path).exists()]
        self.assertEqual([], existing)

    def test_dockerfiles_copy_shared_package(self) -> None:
        for relative_path in ["apps/backend/Dockerfile", "apps/frontend/Dockerfile"]:
            with self.subTest(path=relative_path):
                text = (ROOT / relative_path).read_text(encoding="utf-8")
                self.assertIn("COPY shared/observability_demo_shared ./observability_demo_shared", text)

    def test_compose_build_context_can_see_shared_package(self) -> None:
        compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
        self.assertIn("context: ./apps", compose)
        self.assertIn("dockerfile: frontend/Dockerfile", compose)
        self.assertIn("dockerfile: backend/Dockerfile", compose)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run shared helper tests and verify they fail**

Run:

```bash
python3 -m unittest tests.test_shared_helpers -v
```

Expected result:

```text
FAIL or ERROR in multiple shared helper extraction tests
```

- [ ] **Step 3: Create the shared package marker**

Create directory `apps/shared/observability_demo_shared`.

Create `apps/shared/observability_demo_shared/__init__.py` with this content:

```python
"""Shared helpers for the observability demo services."""
```

- [ ] **Step 4: Create shared logging helpers**

Create `apps/shared/observability_demo_shared/logging.py` with this content:

```python
import json
import logging
import sys
from typing import Any

try:
    from opentelemetry import trace
except Exception:  # pragma: no cover - local static tests may not install app dependencies
    trace = None


def configure_logging(logger_name: str) -> logging.Logger:
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        stream=sys.stdout,
        force=True,
    )
    return logging.getLogger(logger_name)


def current_trace_id() -> str:
    if trace is None:
        return "none"
    span_context = trace.get_current_span().get_span_context()
    if not span_context.is_valid:
        return "none"
    return f"{span_context.trace_id:032x}"


def format_logfmt(fields: dict[str, Any]) -> str:
    return " ".join(f"{key}={_format_value(value)}" for key, value in fields.items())


def _format_value(value: Any) -> str:
    text = str(value)
    if text == "" or any(char.isspace() or char in {'"', '='} for char in text):
        return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return text


def emit_logfmt(logger: logging.Logger, **fields: Any) -> None:
    logger.info(format_logfmt(fields))


def emit_json(logger: logging.Logger, **fields: Any) -> None:
    logger.warning(json.dumps(fields, separators=(",", ":"), default=str))
```

- [ ] **Step 5: Create shared request metric helpers**

Create `apps/shared/observability_demo_shared/request_metrics.py` with this content:

```python
from dataclasses import dataclass

from fastapi import Request
from fastapi.responses import Response
from prometheus_client import Counter, Gauge, Histogram


@dataclass(frozen=True)
class HttpMetrics:
    requests: Counter
    duration: Histogram
    request_bytes: Counter
    response_bytes: Counter
    build_info: Gauge


def create_http_metrics(service_name: str, replica_id: str) -> HttpMetrics:
    metrics = HttpMetrics(
        requests=Counter(
            "demo_http_requests_total",
            "HTTP requests handled by demo services.",
            ["service", "replica", "method", "route", "status"],
        ),
        duration=Histogram(
            "demo_http_request_duration_seconds",
            "HTTP request duration for demo services.",
            ["service", "replica", "method", "route", "status"],
            buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
        ),
        request_bytes=Counter(
            "demo_http_request_bytes_total",
            "Approximate HTTP request bytes received by demo services.",
            ["service", "replica", "method", "route", "status"],
        ),
        response_bytes=Counter(
            "demo_http_response_bytes_total",
            "Approximate HTTP response bytes sent by demo services.",
            ["service", "replica", "method", "route", "status"],
        ),
        build_info=Gauge(
            "demo_build_info",
            "Build and replica information for demo services.",
            ["service", "replica"],
        ),
    )
    metrics.build_info.labels(service_name, replica_id).set(1)
    return metrics


def header_int(headers, name: str) -> int:
    try:
        return max(0, int(headers.get(name, "0") or 0))
    except ValueError:
        return 0


def headers_size(headers) -> int:
    return sum(len(key) + len(value) + 4 for key, value in headers.items())


def request_bytes(request: Request) -> int:
    return len(request.method) + len(str(request.url)) + headers_size(request.headers) + header_int(
        request.headers, "content-length"
    )


async def count_response_bytes(response: Response) -> tuple[Response, int]:
    body = getattr(response, "body", None)
    if body is None:
        chunks = [chunk async for chunk in response.body_iterator]
        body = b"".join(chunks)
        headers = dict(response.headers)
        headers.pop("transfer-encoding", None)
        headers["content-length"] = str(len(body))
        response = Response(
            content=body,
            status_code=response.status_code,
            headers=headers,
            media_type=response.media_type,
            background=response.background,
        )
    return response, len(body) + headers_size(response.headers)
```

- [ ] **Step 6: Create shared telemetry helpers**

Create `apps/shared/observability_demo_shared/telemetry.py` with this content:

```python
import logging
import os

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


def configure_tracing(
    app: FastAPI,
    *,
    default_service_name: str,
    instrument_psycopg2: bool = False,
) -> None:
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://alloy:4317")
    service_name = os.getenv("SERVICE_NAME", default_service_name)
    replica_id = os.getenv("REPLICA_ID", f"{default_service_name}-unknown")

    resource = Resource.create(
        {
            "service.name": service_name,
            "service.instance.id": replica_id,
            "deployment.environment": "local",
        }
    )
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint, insecure=True)))
    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(app, tracer_provider=provider, excluded_urls="/metrics")
    RequestsInstrumentor().instrument()

    if instrument_psycopg2:
        from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor

        Psycopg2Instrumentor().instrument()


def configure_profiling(*, default_service_name: str, logger_name: str) -> None:
    server_address = os.getenv("PYROSCOPE_SERVER_ADDRESS")
    if not server_address:
        return

    try:
        import pyroscope

        pyroscope.configure(
            application_name=f"{os.getenv('SERVICE_NAME', default_service_name)}.{os.getenv('REPLICA_ID', 'unknown')}",
            server_address=server_address,
            tags={
                "service": os.getenv("SERVICE_NAME", default_service_name),
                "replica": os.getenv("REPLICA_ID", "unknown"),
                "environment": "local",
            },
        )
    except Exception as exc:  # pragma: no cover - profiling should not break the app
        logging.getLogger(logger_name).warning("profiling_setup_failed error=%s", exc)
```

- [ ] **Step 7: Expand app build contexts so Dockerfiles can copy the shared package**

In `docker-compose.yml`, replace the frontend anchor build line:

```yaml
    build: ./apps/frontend
```

with:

```yaml
    build:
      context: ./apps
      dockerfile: frontend/Dockerfile
```

Replace the backend anchor build line:

```yaml
    build: ./apps/backend
```

with:

```yaml
    build:
      context: ./apps
      dockerfile: backend/Dockerfile
```

- [ ] **Step 8: Update backend Dockerfile**

Replace `apps/backend/Dockerfile` with this content:

```dockerfile
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY shared/observability_demo_shared ./observability_demo_shared
COPY backend/app ./app

EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers", "--no-access-log"]
```

- [ ] **Step 9: Update frontend Dockerfile**

Replace `apps/frontend/Dockerfile` with this content:

```dockerfile
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY frontend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY shared/observability_demo_shared ./observability_demo_shared
COPY frontend/app ./app

EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers", "--no-access-log"]
```

- [ ] **Step 10: Update backend imports and metric initialization**

In `apps/backend/app/main.py`, replace these imports:

```python
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
```

with:

```python
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
```

Replace these local imports:

```python
from .logging_config import configure_logging, current_trace_id, emit_json, emit_logfmt
from .telemetry import configure_profiling, configure_tracing
```

with:

```python
from observability_demo_shared.logging import configure_logging, current_trace_id, emit_json, emit_logfmt
from observability_demo_shared.request_metrics import (
    count_response_bytes,
    create_http_metrics,
    headers_size,
    request_bytes,
)
from observability_demo_shared.telemetry import configure_profiling, configure_tracing
```

Replace the metric declarations from `HTTP_REQUESTS = Counter(...)` through `BUILD_INFO.labels(SERVICE_NAME, REPLICA_ID).set(1)` with:

```python
HTTP_METRICS = create_http_metrics(SERVICE_NAME, REPLICA_ID)
HTTP_REQUESTS = HTTP_METRICS.requests
HTTP_DURATION = HTTP_METRICS.duration
HTTP_REQUEST_BYTES = HTTP_METRICS.request_bytes
HTTP_RESPONSE_BYTES = HTTP_METRICS.response_bytes
BUILD_INFO = HTTP_METRICS.build_info
```

Replace:

```python
logger = configure_logging()
```

with:

```python
logger = configure_logging("backend")
```

Replace:

```python
configure_tracing(app)
configure_profiling()
```

with:

```python
configure_tracing(app, default_service_name="backend", instrument_psycopg2=True)
configure_profiling(default_service_name="backend", logger_name="backend")
```

Delete these helper functions from `apps/backend/app/main.py`:

```python
def _header_int(headers, name: str) -> int:
    try:
        return max(0, int(headers.get(name, "0") or 0))
    except ValueError:
        return 0


def _headers_size(headers) -> int:
    return sum(len(key) + len(value) + 4 for key, value in headers.items())


def _request_bytes(request: Request) -> int:
    return len(request.method) + len(str(request.url)) + _headers_size(request.headers) + _header_int(
        request.headers, "content-length"
    )


async def _count_response_bytes(response: Response) -> tuple[Response, int]:
    body = getattr(response, "body", None)
    if body is None:
        chunks = [chunk async for chunk in response.body_iterator]
        body = b"".join(chunks)
        headers = dict(response.headers)
        headers.pop("transfer-encoding", None)
        headers["content-length"] = str(len(body))
        response = Response(
            content=body,
            status_code=response.status_code,
            headers=headers,
            media_type=response.media_type,
            background=response.background,
        )
    return response, len(body) + _headers_size(response.headers)
```

Replace backend references:

```python
response_bytes = len(response.body) + _headers_size(response.headers)
response, response_bytes = await _count_response_bytes(response)
_request_bytes(request)
```

with:

```python
response_bytes = len(response.body) + headers_size(response.headers)
response, response_bytes = await count_response_bytes(response)
request_bytes(request)
```

- [ ] **Step 11: Update frontend imports and metric initialization**

In `apps/frontend/app/main.py`, replace this import:

```python
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
```

with:

```python
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
```

Replace these local imports:

```python
from .logging_config import configure_logging, current_trace_id, emit_logfmt
from .telemetry import configure_profiling, configure_tracing
```

with:

```python
from observability_demo_shared.logging import configure_logging, current_trace_id, emit_logfmt
from observability_demo_shared.request_metrics import count_response_bytes, create_http_metrics, request_bytes
from observability_demo_shared.telemetry import configure_profiling, configure_tracing
```

Replace the metric declarations from `HTTP_REQUESTS = Counter(...)` through `BUILD_INFO.labels(SERVICE_NAME, REPLICA_ID).set(1)` with:

```python
HTTP_METRICS = create_http_metrics(SERVICE_NAME, REPLICA_ID)
HTTP_REQUESTS = HTTP_METRICS.requests
HTTP_DURATION = HTTP_METRICS.duration
HTTP_REQUEST_BYTES = HTTP_METRICS.request_bytes
HTTP_RESPONSE_BYTES = HTTP_METRICS.response_bytes
BUILD_INFO = HTTP_METRICS.build_info
```

Replace:

```python
logger = configure_logging()
```

with:

```python
logger = configure_logging("frontend")
```

Replace:

```python
configure_tracing(app)
configure_profiling()
```

with:

```python
configure_tracing(app, default_service_name="frontend")
configure_profiling(default_service_name="frontend", logger_name="frontend")
```

Delete these helper functions from `apps/frontend/app/main.py`:

```python
def _header_int(headers, name: str) -> int:
    try:
        return max(0, int(headers.get(name, "0") or 0))
    except ValueError:
        return 0


def _headers_size(headers) -> int:
    return sum(len(key) + len(value) + 4 for key, value in headers.items())


def _request_bytes(request: Request) -> int:
    return len(request.method) + len(str(request.url)) + _headers_size(request.headers) + _header_int(
        request.headers, "content-length"
    )


async def _count_response_bytes(response: Response) -> tuple[Response, int]:
    body = getattr(response, "body", None)
    if body is None:
        chunks = [chunk async for chunk in response.body_iterator]
        body = b"".join(chunks)
        headers = dict(response.headers)
        headers.pop("transfer-encoding", None)
        headers["content-length"] = str(len(body))
        response = Response(
            content=body,
            status_code=response.status_code,
            headers=headers,
            media_type=response.media_type,
            background=response.background,
        )
    return response, len(body) + _headers_size(response.headers)
```

Replace frontend references:

```python
response, response_bytes = await _count_response_bytes(response)
_request_bytes(request)
```

with:

```python
response, response_bytes = await count_response_bytes(response)
request_bytes(request)
```

- [ ] **Step 12: Delete old duplicate helper modules**

Run:

```bash
rm apps/backend/app/logging_config.py apps/backend/app/telemetry.py apps/frontend/app/logging_config.py apps/frontend/app/telemetry.py
```

- [ ] **Step 13: Run shared helper tests**

Run:

```bash
python3 -m unittest tests.test_shared_helpers -v
```

Expected result:

```text
Ran 5 tests
OK
```

- [ ] **Step 14: Run all checks**

Run:

```bash
make check
```

Expected result:

```text
Ran 20 tests
OK
```

- [ ] **Step 15: Validate Compose syntax after build context changes**

Run:

```bash
docker compose config --quiet
```

Expected result: no output and exit code `0`.

- [ ] **Step 16: Commit Task 5**

Run:

```bash
git add docker-compose.yml apps/backend/Dockerfile apps/frontend/Dockerfile apps/shared apps/backend/app/main.py apps/frontend/app/main.py tests/test_shared_helpers.py
git rm apps/backend/app/logging_config.py apps/backend/app/telemetry.py apps/frontend/app/logging_config.py apps/frontend/app/telemetry.py
git commit -m "refactor: share service observability helpers"
```

---

## Task 6: Final Verification and Cleanup

**Files:**
- Modify only if a verification command reveals a concrete mismatch.

- [ ] **Step 1: Run the full fast check suite**

Run:

```bash
make check
```

Expected result:

```text
Ran 20 tests
OK
```

- [ ] **Step 2: Validate Docker Compose configuration**

Run:

```bash
docker compose config --quiet
```

Expected result: no output and exit code `0`.

- [ ] **Step 3: Verify scenario CLI dry-run output**

Run:

```bash
python3 scripts/scenario.py list
python3 scripts/scenario.py start checkout-latency --dry-run
python3 scripts/scenario.py reset --dry-run
python3 scripts/scenario.py status --dry-run
```

Expected `list` output contains:

```text
checkout-latency	Checkout latency on one backend replica
products-errors	Intermittent product API errors
cpu-hot-replica	CPU-heavy backend replica
db-slowdown	Database wait during checkout
```

Expected dry-run commands print JSON with `"mode": "dry-run"` and request URLs under `/api/fault/`.

- [ ] **Step 4: Check for forbidden public Pyroscope links**

Run:

```bash
grep -RIn "localhost:40""40\|http://localhost:40""40" README.md docs apps config/grafana/dashboards || true
```

Expected result: no output.

- [ ] **Step 5: Check git status for accidental generated files**

Run:

```bash
git status --short
```

Expected result: only intentional source, docs, config, and test changes are present. Remove any `__pycache__` or `.pyc` files before the final commit.

- [ ] **Step 6: Optional local stack smoke test when Docker resources are available**

Run:

```bash
make up
make traffic-start
make scenario-reset
make scenario-start NAME=checkout-latency
curl -i http://localhost:8080/admin
curl -i http://localhost:8080/api/fault/status
curl -fsS http://localhost:8080/health
curl -fsS http://localhost:8080/api/health
make scenario-reset
make traffic-stop
```

Expected results:

- `/admin` on port `8080` returns `404`.
- `/api/fault/status` on port `8080` returns `404`.
- `/health` returns JSON with frontend health.
- `/api/health` returns JSON with backend and database health.
- Scenario commands return JSON with backend replica status.

If you start the stack for this smoke test and do not need it afterward, run:

```bash
make down
```

- [ ] **Step 7: Final commit if verification caused cleanup edits**

If Step 1 through Step 5 required any edits, commit them:

```bash
git add -A
git commit -m "chore: finalize workshop refactor verification"
```

If no files changed after Task 5, do not create an empty commit.

---

## Self-Review Notes

Spec coverage:

- Workshop spine is covered by Task 3.
- Named scenario workflow is covered by Task 2 and scenario cards in Task 3.
- Cloudflare-friendly two-URL public surface is covered by Task 4.
- Grafana-only profile exploration is covered by Task 4.
- Light shared helper refactor is covered by Task 5.
- Fast validation with `make check` is covered by Task 1 and expanded in Tasks 2–5.
- Hidden student route checks are covered by Task 1 and final smoke checks in Task 6.

Placeholder scan:

- The plan contains concrete file paths, commands, expected outputs, and code snippets for every created source/test/doc file.
- No task depends on an unspecified external service other than the optional Docker smoke test.

Type consistency:

- Scenario tests use `planned_requests`, `SCENARIOS`, and `HttpRequestPlan` exactly as defined in `scripts/scenario.py`.
- Shared helper tests use `format_logfmt`, which is defined in `observability_demo_shared.logging`.
- Frontend/backend imports match the shared package path copied by the updated Dockerfiles.
