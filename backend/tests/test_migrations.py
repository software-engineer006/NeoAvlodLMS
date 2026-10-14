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
            audit_tables = await connection.run_sync(
                lambda sync: inspect(sync).get_table_names(schema="audit")
            )
            owned_tables = set(tables) | {f"audit.{name}" for name in audit_tables}
            assert owned_tables == set(Base.metadata.tables) | {"alembic_version"}
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


@pytest.mark.anyio
async def test_enrollment_backfill_is_repeatable_and_downgrade_protects_courses(
    test_database: Database,
) -> None:
    from factories import group

    from neoavlod.models import Subject

    try:
        migration("upgrade", "0012_audit_archive")
        async with test_database.session() as session:
            teacher = staff(role=Role.TEACHER)
            subject = Subject(id=uuid.uuid4(), name="Namuna kurs")
            session.add(teacher)
            await session.flush()
            await session.execute(
                text("INSERT INTO subjects(id,name) VALUES (:id,:name)"),
                {"id": subject.id, "name": subject.name},
            )
            first = group(subject.id, teacher.id, name="Namuna birinchi")
            second = group(subject.id, teacher.id, name="Namuna ikkinchi")
            for course in (first, second):
                course.id = uuid.uuid4()
                await session.execute(
                    text(
                        "INSERT INTO groups(id,name,subject_id,teacher_id,monthly_price,"
                        "max_students,days_of_week) VALUES (:id,:name,:subject,:teacher,"
                        ":price,:capacity,CAST(:days AS jsonb))"
                    ),
                    {
                        "id": course.id,
                        "name": course.name,
                        "subject": subject.id,
                        "teacher": teacher.id,
                        "price": course.monthly_price,
                        "capacity": course.max_students,
                        "days": json.dumps(course.days_of_week),
                    },
                )
            pupil_id = uuid.uuid4()
            await session.execute(
                text(
                    "INSERT INTO students(id,first_name,last_name,group_id,auth_uuid) "
                    "VALUES (:id,'Namuna','O‘quvchi',:group,:auth)"
                ),
                {"id": pupil_id, "group": first.id, "auth": uuid.uuid4()},
            )
            await session.commit()
            first_id, second_id = first.id, second.id
        migration("upgrade", "0013_student_enrollments")
        migration("upgrade", "0013_student_enrollments")
        async with test_database.session() as session:
            memberships = (
                await session.execute(
                    text("SELECT student_id,group_id FROM student_group_enrollments")
                )
            ).all()
            assert len(memberships) == 1
            assert memberships[0].student_id == pupil_id
            assert memberships[0].group_id == first_id
            await session.execute(
                text(
                    "INSERT INTO student_group_enrollments(id,student_id,group_id) "
                    "VALUES (:id,:student,:group)"
                ),
                {"id": uuid.uuid4(), "student": pupil_id, "group": second_id},
            )
            await session.commit()
        with pytest.raises(AssertionError, match="Membership data exists"):
            migration("downgrade", "0012_audit_archive")
    finally:
        async with test_database.engine.begin() as connection:
            await connection.run_sync(Base.metadata.drop_all)
            await connection.execute(text("DROP TABLE IF EXISTS alembic_version"))


@pytest.mark.anyio
async def test_refresh_migration_preserves_populated_history_and_guards_downgrade(
    test_database: Database,
) -> None:
    try:
        migration("upgrade", "0016_attendance_template")
        subject_id = uuid.uuid4()
        async with test_database.session() as session:
            await session.execute(
                text("INSERT INTO subjects(id,name) VALUES (:id,'Namuna kurs')"), {"id": subject_id}
            )
            await session.commit()
        migration("upgrade", "head")
        migration("upgrade", "head")
        migration("check")
        from test_audit_archive import restricted_database

        from neoavlod.models import AttendanceMessageTemplate, Room, StudentGroupEnrollment

        restricted = await restricted_database(test_database, "neoavlod_app")
        try:
            async with restricted.session() as session:
                session.add(Room(name="Namuna restricted217"))
                await session.commit()
                assert await session.scalar(select(Room.id))
                assert await session.scalar(select(StudentGroupEnrollment.id)) is None
                assert await session.get(AttendanceMessageTemplate, 1) is None
        finally:
            await restricted.close()
        async with test_database.session() as session:
            await session.execute(
                text("UPDATE subjects SET archived_at=now() WHERE id=:id"), {"id": subject_id}
            )
            await session.commit()
        with pytest.raises(AssertionError, match="Archived dataset exists"):
            migration("downgrade", "0016_attendance_template")
        async with test_database.session() as session:
            assert (
                await session.scalar(
                    text("SELECT count(*) FROM subjects WHERE id=:id AND archived_at IS NOT NULL"),
                    {"id": subject_id},
                )
                == 1
            )
    finally:
        async with test_database.engine.begin() as connection:
            await connection.run_sync(Base.metadata.drop_all)
            await connection.execute(text("DROP TABLE IF EXISTS alembic_version"))
