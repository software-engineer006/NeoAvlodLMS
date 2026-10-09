import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
A, B, C = (letter * 40 for letter in "abc")


class ReleaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.app = self.root / "app"
        self.web = self.root / "web"
        self.bin = self.root / "bin"
        for folder in (
            self.app / "releases",
            self.web,
            self.bin,
            self.root / "nginx/conf.d",
            self.root / "nginx/snippets",
        ):
            folder.mkdir(parents=True)
        (self.app / ".env.production").write_text("test-env")
        self.env = os.environ | {
            "APP_ROOT": str(self.app),
            "WEB_ROOT": str(self.web),
            "BACKUP_ROOT": str(self.root / "backup"),
            "NGINX_CONFIG_ROOT": str(self.root / "nginx"),
            "PATH": f"{self.bin}:{os.environ['PATH']}",
            "CALLS": str(self.root / "calls"),
        }
        self.command(
            "docker",
            """echo "${NEOAVLOD_RELEASE_ID:-inspect} $*" >> "$CALLS"
if [[ "$*" == *"ps --status running -q worker"* ]]; then echo worker; fi
if [[ "$*" == *pg_dump* ]]; then echo backup; fi
if [[ "${FAIL_STEP:-}" == migration && "${NEOAVLOD_RELEASE_ID:-}" == """
            + C
            + """ && "$*" == *"run --rm -T --no-deps migrations" ]]; then exit 1; fi
if [[ "${FAIL_STEP:-}" == import && "$*" == *neoavlod.educenter_import* ]]; then exit 1; fi
""",
        )
        self.command(
            "nginx",
            """if [[ "${FAIL_STEP:-}" == nginx && "$(basename "$(readlink "$APP_ROOT/current")")" == """
            + C
            + """ ]]; then exit 1; fi""",
        )
        self.command("systemctl", "exit 0")
        self.command(
            "curl",
            """if [[ "${FAIL_STEP:-}" == health ]]; then exit 1; fi
if [[ "$*" == *release.txt* ]]; then basename "$(readlink "$WEB_ROOT/current")"; fi""",
        )
        for release in (A, B, C):
            folder = self.app / "releases" / release
            for path in (
                "frontend/release/admin",
                "frontend/release/teacher",
                "nginx/conf.d",
                "nginx/snippets",
            ):
                (folder / path).mkdir(parents=True)
            (folder / "compose.prod.yaml").write_text("source")
            (folder / "nginx/conf.d/eduneo.conf").write_text(release)
            (folder / "nginx/snippets/ssl-params.conf").write_text(release)
            for portal in ("admin", "teacher"):
                (folder / f"frontend/release/{portal}/index.html").write_text(release)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def command(self, name: str, body: str) -> None:
        path = self.bin / name
        path.write_text("#!/bin/bash\nset -eu\n" + body + "\n")
        path.chmod(0o755)

    def run_script(
        self, name: str, *args: str, **extra: str
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", str(ROOT / "scripts/deploy" / name), *args],
            env=self.env | extra,
            text=True,
            capture_output=True,
            check=False,
        )

    def deploy(self, release: str) -> None:
        result = self.run_script("deploy.sh", release)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.app / "current").readlink().name, release)
        self.assertEqual((self.web / "current").readlink().name, release)
        self.assertEqual((self.web / "admin/release.txt").read_text().strip(), release)

    def test_versioned_deploy_backup_and_manual_backend_rollback(self) -> None:
        self.deploy(A)
        self.deploy(B)
        result = self.run_script("rollback.sh")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.app / "current").readlink().name, A)
        self.assertEqual((self.web / "current").readlink().name, A)
        calls = (self.root / "calls").read_text()
        self.assertIn(f"{A} compose", calls)
        self.assertIn("--no-deps --no-build --force-recreate", calls)
        self.assertEqual(len(list((self.root / "backup").glob("*.dump"))), 2)

    def test_missing_frontend_and_path_traversal_never_activate(self) -> None:
        (self.app / "releases" / A / "frontend/release/teacher/index.html").unlink()
        self.assertNotEqual(self.run_script("deploy.sh", A).returncode, 0)
        self.assertNotEqual(self.run_script("deploy.sh", "../../etc").returncode, 0)
        self.assertFalse((self.app / "current").exists())

    def test_migration_and_nginx_failure_restore_both_previous_releases(self) -> None:
        self.deploy(A)
        self.deploy(B)
        for step in ("migration", "nginx"):
            result = self.run_script("deploy.sh", C, FAIL_STEP=step)
            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertEqual((self.app / "current").readlink().name, B)
            self.assertEqual((self.web / "current").readlink().name, B)
            self.assertFalse((self.app / "releases" / C / ".successful").exists())
        self.assertEqual((self.app / ".previous_release").read_text().strip(), A)

    def test_failed_initial_deploy_does_not_report_success(self) -> None:
        result = self.run_script("deploy.sh", C, FAIL_STEP="nginx")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.app / "current").exists())
        self.assertFalse((self.web / "current").exists())
        self.assertIn("stop api worker", (self.root / "calls").read_text())

    def test_private_import_after_migration_before_start_and_repeat_deploy(
        self,
    ) -> None:
        private = self.app / "private/educenter_data"
        private.mkdir(parents=True)
        (private / "plan.sha256").write_text("d" * 64)
        self.deploy(A)
        self.deploy(B)
        calls = (self.root / "calls").read_text().splitlines()
        for release in (A, B):
            lines = [line for line in calls if line.startswith(release)]
            migration = next(
                i
                for i, line in enumerate(lines)
                if line.endswith("--no-deps migrations")
            )
            imported = next(
                i for i, line in enumerate(lines) if "neoavlod.educenter_import" in line
            )
            started = next(
                i for i, line in enumerate(lines) if "--force-recreate" in line
            )
            self.assertLess(migration, imported)
            self.assertLess(imported, started)
            self.assertIn("/import-source:ro", lines[imported])
            self.assertIn("--expected-plan " + "d" * 64, lines[imported])

    def test_import_failure_and_unreviewed_data_restore_previous_release(self) -> None:
        self.deploy(A)
        private = self.app / "private/educenter_data"
        private.mkdir(parents=True)
        for sha in (None, "not-a-hash", "d" * 64):
            if sha is not None:
                (private / "plan.sha256").write_text(sha)
            result = self.run_script("deploy.sh", B, FAIL_STEP="import")
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual((self.app / "current").readlink().name, A)
            self.assertFalse((self.app / "releases" / B / ".successful").exists())

    def test_explicit_missing_import_directory_fails(self) -> None:
        result = self.run_script(
            "deploy.sh", A, EDUCENTER_DATA_DIR=str(self.root / "missing")
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("EDUCENTER_DATA_DIR mavjud emas", result.stderr)
        self.assertFalse((self.app / "current").exists())

    def test_ci_ssh_key_rejects_arbitrary_commands(self) -> None:
        for command in (
            "bash",
            "deploy ../../etc",
            "deploy " + A + "; id",
            "rollback extra",
        ):
            result = self.run_script("ci-entrypoint.sh", SSH_ORIGINAL_COMMAND=command)
            self.assertNotEqual(result.returncode, 0)

    def test_manual_rollback_health_failure_is_not_success(self) -> None:
        self.deploy(A)
        self.deploy(B)
        result = self.run_script("rollback.sh", FAIL_STEP="health")
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("Backend va ikkala frontend tiklandi", result.stdout)
        self.assertEqual((self.app / ".previous_release").read_text().strip(), A)

    def test_server_rejects_stale_pipeline_commit_before_archiving(self) -> None:
        self.command(
            "git",
            f"""echo "git $*" >> "$CALLS"
if [[ "$*" == *"rev-parse origin/main" ]]; then echo {A}; fi""",
        )
        result = self.run_script("server_deploy.sh", B, REPO_ROOT=str(self.root))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("joriy SHA emas", result.stderr)
        self.assertNotIn("archive", (self.root / "calls").read_text())
        self.assertFalse((self.app / "current").exists())

    def test_frontend_verifier_rejects_stale_source_and_modified_assets(self) -> None:
        import hashlib

        folder = self.root / "frontend"
        folder.mkdir()
        (folder / "source.ts").write_text("source")
        digest = hashlib.sha256(b"source.ts\0source\0").hexdigest()
        assets = {}
        for app in ("admin", "teacher"):
            (folder / "release" / app).mkdir(parents=True)
            (folder / "release" / app / "index.html").write_text("real-build")
            assets[app] = {"index.html": hashlib.sha256(b"real-build").hexdigest()}
        (folder / "release/manifest.json").write_text(
            json.dumps({"schema": 1, "source_sha256": digest, "assets": assets})
        )
        command = [
            "python",
            str(ROOT / "scripts/deploy/verify_frontend.py"),
            str(folder),
        ]
        self.assertEqual(
            subprocess.run(command, capture_output=True, check=False).returncode, 0
        )
        (folder / "source.ts").write_text("changed")
        self.assertNotEqual(
            subprocess.run(command, capture_output=True, check=False).returncode, 0
        )
        (folder / "source.ts").write_text("source")
        (folder / "release/admin/index.html").write_text("changed")
        self.assertNotEqual(
            subprocess.run(command, capture_output=True, check=False).returncode, 0
        )


if __name__ == "__main__":
    unittest.main()
