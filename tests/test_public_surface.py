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
            if "localhost:4040" in text or "http://localhost:4040" in text:
                offenders.append(relative_path)
        self.assertEqual([], offenders)

    def test_browser_facing_files_keep_profile_navigation_inside_grafana(self) -> None:
        offenders = []
        for relative_path in BROWSER_FACING_FILES:
            text = read_text(relative_path)
            if "Open Pyroscope" in text or "open Pyroscope" in text:
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
