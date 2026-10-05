import subprocess
import sys
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import CheckConstraint, Connection, inspect, text

from neoavlod.database import Base, Database

ROOT = Path(__file__).resolve().parents[1]


def check_names(connection: Connection, table: str) -> set[str]:
    return {
        str(item["name"])
        for item in inspect(connection).get_check_constraints(table)
        if item["name"] is not None
    }


def migration(*args: str) -> str:
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", str(ROOT / "alembic.ini"), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout


@pytest.mark.anyio
async def test_initial_migration_upgrade_downgrade_and_schema_match(
    test_database: Database,
) -> None:
    # The fixture rejects every URL except the disposable Compose test database.
    try:
        migration("upgrade", "head")
        async with test_database.engine.connect() as connection:
            tables = await connection.run_sync(lambda sync: inspect(sync).get_table_names())
            assert set(tables) == set(Base.metadata.tables) | {"alembic_version"}
            assert (
                await connection.execute(text("SELECT version_num FROM alembic_version"))
            ).scalar_one() == ScriptDirectory.from_config(
                Config(str(ROOT / "alembic.ini"))
            ).get_current_head()
            for name in ("staff", "groups", "students", "otp_challenges"):
                constraints = await connection.run_sync(check_names, name)
                expected = {
                    str(item.name)
                    for item in Base.metadata.tables[name].constraints
                    if isinstance(item, CheckConstraint)
                }
                assert constraints == expected, f"Check constraint mismatch on {name}"
        migration("current", "--check-heads")
        migration("check")
        migration("downgrade", "base")
        async with test_database.engine.connect() as connection:
            tables = await connection.run_sync(lambda sync: inspect(sync).get_table_names())
            assert not (set(tables) & set(Base.metadata.tables))
        migration("upgrade", "head")
        migration("check")
    finally:
        migration("downgrade", "base")


def test_offline_migration_sql_contains_schema_without_credentials() -> None:
    sql = migration("upgrade", "head", "--sql")
    assert "CREATE TABLE staff" in sql
    assert "CREATE TABLE notification_outbox" in sql
    assert "postgresql+asyncpg://" not in sql
