"""Checks must fail visibly when unimplemented or when a quality gate fails."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1]


class CheckScriptTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.skills = self.root / "scripts" / "agent_skills"
        self.skills.mkdir(parents=True)
        for path in SOURCE.glob("*.sh"):
            shutil.copy2(path, self.skills / path.name)

    def test_missing_components_fail_from_another_directory(self):
        for name, message in (
            ("check_backend.sh", "Backend hali yaratilmagan"),
            ("check_frontend.sh", "Frontend hali yaratilmagan"),
            ("run_migrations.sh", "Alembic hali yaratilmagan"),
        ):
            result = subprocess.run(
                ["bash", str(self.skills / name)], cwd="/",
                capture_output=True, text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(message, result.stderr)

    def test_backend_failure_stops_later_gates(self):
        backend = self.root / "backend"
        backend.mkdir()
        (backend / "pyproject.toml").touch()
        interpreter = self.root / "fake-python"
        log = self.root / "calls"
        interpreter.write_text(
            '#!/usr/bin/env bash\n'
            'printf "%s\\n" "$*" >> "$TEST_CALL_LOG"\n'
            'if [[ "$*" == "-m ruff "* ]]; then exit 7; fi\n',
            encoding="utf-8",
        )
        interpreter.chmod(0o755)
        result = subprocess.run(
            ["bash", str(self.skills / "check_backend.sh")], cwd="/",
            capture_output=True, text=True,
            env={**os.environ, "BACKEND_PYTHON": str(interpreter), "TEST_CALL_LOG": str(log)},
        )
        self.assertEqual(result.returncode, 7)
        calls = log.read_text()
        self.assertIn("-m compileall", calls)
        self.assertIn("-m ruff", calls)
        self.assertNotIn("-m mypy", calls)
        self.assertNotIn("-m pytest", calls)


if __name__ == "__main__":
    unittest.main()
