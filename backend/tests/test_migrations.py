import json
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from factories import staff
from sqlalchemy import CheckConstraint, Connection, inspect, select, text

from neoavlod.database import Base, Database
from neoavlod.models import Role, Staff

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
            assert "otp_challenges" not in tables
            for name in ("staff", "groups", "students"):
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


@pytest.mark.anyio
async def test_attendance_migration_grants_existing_admins_and_preserves_data(
    test_database: Database,
) -> None:
    try:
        migration("upgrade", "0006_real_roster_fields")
        admin = staff(role=Role.ADMIN, permissions=["groups:read"], telegram_id=111000)
        teacher = staff(role=Role.TEACHER, permissions=[], telegram_id=111001)
        async with test_database.session() as session:
            # Insert through the old schema: current ORM defaults may include columns
            # introduced after 0006, while this test exercises the entire upgrade.
            for person in (admin, teacher):
                person.id = uuid.uuid4()
                person.auth_uuid = uuid.uuid4()
                await session.execute(
                    text("""
                    INSERT INTO staff (id, first_name, last_name, phone, username,
                        hashed_password, role, permissions, auth_uuid, telegram_id)
                    VALUES (:id, :first_name, :last_name, :phone, :username,
                        :hashed_password, :role, CAST(:permissions AS jsonb),
                        :auth_uuid, :telegram_id)
                """),
                    {
                        "id": person.id,
                        "first_name": person.first_name,
                        "last_name": person.last_name,
                        "phone": person.phone,
                        "username": person.username,
                        "hashed_password": person.hashed_password,
                        "role": person.role.value,
                        "permissions": json.dumps(person.permissions),
                        "auth_uuid": person.auth_uuid,
                        "telegram_id": person.telegram_id,
                    },
                )
            await session.commit()
        migration("upgrade", "head")
        migration("upgrade", "head")
        async with test_database.session() as session:
            people = {person.id: person for person in (await session.scalars(select(Staff))).all()}
            assert set(people[admin.id].permissions) == {
                "groups:read",
                "attendance:read",
                "attendance:write",
                "messages:send",
            }
            assert people[teacher.id].permissions == []
            assert not people[teacher.id].telegram_reconnect_required
            assert not people[admin.id].telegram_reconnect_required
            assert people[admin.id].telegram_id == 111000 and people[admin.id].telegram_connected
            assert people[teacher.id].telegram_id == 111001
            assert people[teacher.id].telegram_connected
            assert people[admin.id].hashed_password == admin.hashed_password
        migration("check")
    finally:
        migration("downgrade", "base")
