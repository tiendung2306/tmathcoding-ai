import os
from pathlib import Path
import subprocess
import sys
import unittest


class RuntimeSourceBoundaryTests(unittest.TestCase):
    def test_main_import_does_not_load_source_orm_or_database_module(self):
        env = os.environ.copy()
        for key in tuple(env):
            if key.startswith("SOURCE_DB_") or key.startswith("MYSQL_"):
                env.pop(key)
        env.update({
            "PROJECT_NAME": "source-boundary-test",
            "DASHBOARD_DB_HOST": "dashboard",
            "DASHBOARD_DB_USER": "dashboard_app",
            "DASHBOARD_DB_PASSWORD": "test-only",
        })
        script = """
import sys
import app.main
assert 'app.core.database' not in sys.modules
assert 'app.models.dmoj' not in sys.modules
from app.core.config import settings
assert not hasattr(settings, 'SOURCE_DB_PASSWORD')
"""
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=Path(__file__).resolve().parents[1],
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_runtime_modules_do_not_import_legacy_source_database(self):
        app_dir = Path(__file__).resolve().parents[1] / "app"
        forbidden = (
            "from app.core.database import",
            "import app.core.database",
            "from app.models.dmoj import",
            "import app.models.dmoj",
            "source_database",
        )
        runtime_paths = [app_dir / "main.py"]
        runtime_paths.extend((app_dir / "api").rglob("*.py"))
        runtime_paths.extend((app_dir / "services").rglob("*.py"))
        runtime_paths.extend((app_dir / "core").rglob("*.py"))
        violations = [
            f"{path.relative_to(app_dir)}: {needle}"
            for path in runtime_paths
            for needle in forbidden
            if needle in path.read_text(encoding="utf-8")
        ]
        self.assertEqual(violations, [])


if __name__ == "__main__":
    unittest.main()
