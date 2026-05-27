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
