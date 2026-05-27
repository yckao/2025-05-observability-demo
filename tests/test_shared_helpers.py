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
