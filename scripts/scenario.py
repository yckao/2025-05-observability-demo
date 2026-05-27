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
