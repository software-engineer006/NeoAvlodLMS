"""Exercise transitions on isolated files, including invalid and concurrent writes."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "task_manager.py"
FIXTURE = """# Tasks
- [ ] 001 — Birinchi.
  - Qabul: test.
  - Dalil: kutilmoqda.
- [ ] 002 — Ikkinchi.
  - Qabul: test.
  - Dalil: kutilmoqda.
"""


class TaskManagerTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "TASKS.md"
        self.path.write_text(FIXTURE, encoding="utf-8")

    def run_cli(self, *args, success=True):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--file", str(self.path), *args],
            capture_output=True, text=True, cwd=self.directory.name,
        )
        self.assertEqual(result.returncode, 0 if success else 1, result.stderr)
        return result

    def test_sequence_and_evidence(self):
        self.run_cli("validate")
        self.run_cli("start", "001")
        self.run_cli("done", "001", "--evidence", "pytest o‘tdi")
        self.assertIn("pytest o‘tdi", self.path.read_text())
        self.assertIn("002", self.run_cli("next").stdout)
        self.run_cli("resume")
        self.run_cli("done", "002", "--evidence", "ok")
        self.assertIn("yakunlangan", self.run_cli("resume").stdout)

    def test_resume_is_idempotent(self):
        self.run_cli("resume")
        first = self.path.read_bytes()
        self.run_cli("resume")
        self.assertEqual(first, self.path.read_bytes())

    def test_cannot_skip_or_start_twice(self):
        original = self.path.read_bytes()
        self.run_cli("start", "002", success=False)
        self.assertEqual(original, self.path.read_bytes())
        self.run_cli("start", "001")
        self.run_cli("start", "002", success=False)
        self.run_cli("start", "001", success=False)

    def test_cannot_complete_pending_or_wrong_task(self):
        self.run_cli("done", "001", "--evidence", "ok", success=False)
        self.run_cli("resume")
        self.run_cli("done", "002", "--evidence", "ok", success=False)

    def test_invalid_evidence_does_not_change_file(self):
        self.run_cli("resume")
        original = self.path.read_bytes()
        for evidence in (" ", "test\n- [x] 002 — injected", "test\rinjected"):
            self.run_cli("done", "001", "--evidence", evidence, success=False)
            self.assertEqual(original, self.path.read_bytes())

    def test_invalid_states_are_rejected(self):
        for document in (
            "# Empty\n",
            FIXTURE.replace("002", "001"),
            FIXTURE.replace("002", "003"),
            FIXTURE.replace("- [ ]", "- [?]", 1),
            FIXTURE.replace("- [ ]", "- [/]"),
            FIXTURE.replace("- [ ] 002", "- [x] 002"),
            FIXTURE.replace("- [ ] 002", "- [/] 002"),
        ):
            self.path.write_text(document, encoding="utf-8")
            self.run_cli("validate", success=False)

    def test_missing_evidence_field_is_rejected(self):
        self.path.write_text(FIXTURE.replace("  - Dalil: kutilmoqda.\n", ""))
        self.run_cli("resume")
        original = self.path.read_bytes()
        self.run_cli("done", "001", "--evidence", "ok", success=False)
        self.assertEqual(original, self.path.read_bytes())

    def test_list_is_machine_readable(self):
        tasks = json.loads(self.run_cli("list").stdout)
        self.assertEqual([task["id"] for task in tasks], ["001", "002"])

    def test_host_execution_is_rejected_without_mutating_state(self):
        environment = dict(os.environ)
        environment.pop("NEOAVLOD_IN_DOCKER", None)
        original = self.path.read_bytes()
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--file", str(self.path), "resume"],
            capture_output=True, text=True, env=environment,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("Docker", result.stderr)
        self.assertEqual(original, self.path.read_bytes())

    def test_concurrent_start_has_one_winner(self):
        command = [sys.executable, str(SCRIPT), "--file", str(self.path), "start", "001"]
        processes = [subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE) for _ in range(4)]
        for process in processes:
            process.communicate(timeout=10)
        self.assertEqual(sorted(p.returncode for p in processes), [0, 1, 1, 1])
        self.run_cli("validate")

    def test_file_mode_and_other_content_preserved(self):
        self.path.chmod(0o640)
        self.run_cli("resume")
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o640)
        self.assertTrue(self.path.read_text().startswith("# Tasks\n"))


if __name__ == "__main__":
    unittest.main()
