import subprocess
import sys

import pytest
from sqlalchemy import func, select, text
from test_migrations import ROOT, migration

from neoavlod.database import Base, Database
from neoavlod.models import AuditEvent, Subject


@pytest.mark.anyio
async def test_populated_audit_cannot_be_destroyed_by_downgrade(test_database: Database) -> None:
    try:
        migration("upgrade", "head")
        async with test_database.session() as session:
            session.add(Subject(name="Downgrade dalili namuna"))
            await session.commit()
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "alembic",
                "-c",
                str(ROOT / "alembic.ini"),
                "downgrade",
                "0010_import_receipts",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode != 0 and "Audit evidence exists" in result.stderr
        async with test_database.session() as session:
            assert await session.scalar(select(func.count()).select_from(AuditEvent)) == 1
            assert await session.scalar(select(Subject.name)) == "Downgrade dalili namuna"
    finally:
        # Only the fixture-guarded disposable test database; never a runtime operation.
        async with test_database.engine.begin() as connection:
            await connection.run_sync(Base.metadata.drop_all)
            await connection.execute(text("DROP TABLE IF EXISTS alembic_version"))
            await connection.execute(text("DROP SCHEMA IF EXISTS audit CASCADE"))
