import asyncio
import json
import uuid
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import pytest
from factories import group, staff
from sqlalchemy import func, select, text, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from neoavlod.database import Database
from neoavlod.models import (
    Attendance,
    AttendanceChange,
    AttendanceStatus,
    AuditEvent,
    Role,
    Student,
    Subject,
)

pytestmark = pytest.mark.anyio


async def context(session: AsyncSession, person_id: uuid.UUID, role: Role) -> None:
    await session.execute(
        text("SELECT set_config('neoavlod.audit_context',:context,true)"),
        {
            "context": json.dumps(
                {
                    "source": "http",
                    "request_id": str(uuid.uuid4()),
                    "actor": {
                        "id": str(person_id),
                        "name": "Namuna Xodim",
                        "username": "namuna_actor",
                        "role": role.value,
                    },
                }
            )
        },
    )


async def test_domain_deltas_attribution_snapshots_and_secret_exclusion(
    model_database: Database,
) -> None:
    admin = staff(role=Role.SUPERADMIN, first_name="Namuna", last_name="Admin")
    teacher = staff(role=Role.TEACHER, first_name="Namuna", last_name="Ustoz")
    start = datetime.now(UTC)
    async with model_database.session() as session:
        session.add_all([admin, teacher])
        await session.flush()
        await context(session, admin.id, Role.SUPERADMIN)
        subject = Subject(name="Namuna fan")
        session.add(subject)
        await session.flush()
        first = group(subject.id, teacher.id, name="Namuna A")
        second = group(subject.id, teacher.id, name="Namuna B")
        session.add_all([first, second])
        await session.flush()
        pupil = Student(
            first_name="Namuna", last_name="O‘quvchi", group_id=first.id, phone="+998900000011"
        )
        session.add(pupil)
        await session.flush()
        pupil.group_id = second.id
        await session.commit()
    async with model_database.session() as session:
        entries = list((await session.scalars(select(AuditEvent).order_by(AuditEvent.id))).all())
        moved = next(item for item in entries if item.action == "student.group_changed")
        assert moved.actor_id == admin.id
        assert moved.body["actor"]["name"] == "Namuna Xodim"
        assert moved.body["actor"]["role"] == "superadmin"
        assert moved.body["changes"]["group_id"]["before"]["name"] == "Namuna A"
        assert moved.body["changes"]["group_id"]["after"]["id"] == str(second.id)
        assert moved.body["entity"]["name"] == "Namuna O‘quvchi"
        assert moved.occurred_at >= start and moved.occurred_at.tzinfo is not None
        assert moved.local_day == moved.occurred_at.astimezone(ZoneInfo("Asia/Tashkent")).date()
        assert datetime.fromisoformat(moved.body["at"]) == moved.occurred_at
        encoded = json.dumps([item.body for item in entries])
        assert admin.phone is not None and pupil.phone is not None
        assert admin.hashed_password not in encoded and admin.phone not in encoded
        assert pupil.phone not in encoded
        count = len(entries)
        await context(session, admin.id, Role.SUPERADMIN)
        await session.execute(
            update(Subject).where(Subject.id == subject.id).values(name=subject.name)
        )
        await session.commit()
        assert await session.scalar(select(func.count()).select_from(AuditEvent)) == count
    with pytest.raises(RuntimeError):
        async with model_database.session() as session:
            await context(session, admin.id, Role.SUPERADMIN)
            session.add(Subject(name="Rollback namuna"))
            await session.flush()
            raise RuntimeError("Rollback test")
    async with model_database.session() as session:
        assert (
            await session.scalar(select(Subject).where(Subject.name == "Rollback namuna")) is None
        )
        assert await session.scalar(select(func.count()).select_from(AuditEvent)) == count


async def test_audit_immutable_guards_and_business_fail_closed(model_database: Database) -> None:
    async with model_database.session() as session:
        session.add(Subject(name="Namuna immutable"))
        await session.commit()
    for statement in (
        "UPDATE audit.events SET action='forged.action'",
        "DELETE FROM audit.events",
        "TRUNCATE audit.events",
        "DELETE FROM audit.segments",
        "TRUNCATE audit.segments",
        "UPDATE attendance_changes SET reason='forged'",
        "DELETE FROM attendance_changes",
        "TRUNCATE attendance_changes",
    ):
        with pytest.raises(DBAPIError, match="immutable"):
            async with model_database.session() as session:
                await session.execute(text(statement))
                await session.commit()
    async with model_database.engine.begin() as connection:
        await connection.exec_driver_sql("""
        CREATE OR REPLACE FUNCTION audit.capture_subjects() RETURNS trigger
        LANGUAGE plpgsql AS $$ BEGIN
          RAISE EXCEPTION 'Injected audit failure'; END $$;
        """)
    with pytest.raises(DBAPIError, match="Injected audit failure"):
        async with model_database.session() as session:
            session.add(Subject(name="Must roll back"))
            await session.commit()
    async with model_database.session() as session:
        assert await session.scalar(select(Subject).where(Subject.name == "Must roll back")) is None
        assert await session.scalar(select(func.count()).select_from(AuditEvent)) == 1


async def test_attendance_canonical_capture_no_duplicate_and_fallback(
    model_database: Database,
) -> None:
    teacher = staff(role=Role.TEACHER, first_name="Namuna", last_name="Ustoz")
    async with model_database.session() as session:
        subject = Subject(name="Davomat namuna")
        session.add_all([teacher, subject])
        await session.flush()
        classroom = group(subject.id, teacher.id)
        session.add(classroom)
        await session.flush()
        pupil = Student(first_name="Namuna", last_name="O‘quvchi", group_id=classroom.id)
        session.add(pupil)
        await session.flush()
        await context(session, teacher.id, Role.TEACHER)
        mark = Attendance(
            group_id=classroom.id,
            student_id=pupil.id,
            date=date(2026, 10, 14),
            status=AttendanceStatus.PRESENT,
            marked_by=teacher.id,
        )
        session.add(mark)
        await session.flush()
        session.add(
            AttendanceChange(
                attendance_id=mark.id,
                actor_id=teacher.id,
                actor_name="Namuna Ustoz",
                actor_role="teacher",
                action="draft",
                old_status=None,
                new_status="present",
            )
        )
        await session.commit()
    async with model_database.session() as session:
        records = list(
            (
                await session.scalars(
                    select(AuditEvent).where(AuditEvent.entity_id == str(mark.id))
                )
            ).all()
        )
        assert len(records) == 1 and records[0].action == "attendance.draft"
        await context(session, teacher.id, Role.TEACHER)
        current = await session.get(Attendance, mark.id)
        assert current is not None
        current.status = AttendanceStatus.LATE
        current.note = "7 daqiqa"
        session.add(
            AttendanceChange(
                attendance_id=mark.id,
                actor_id=teacher.id,
                actor_name="Namuna Ustoz",
                actor_role="teacher",
                action="correct",
                old_status="present",
                new_status="late",
                old_note=None,
                new_note="7 daqiqa",
                reason="Jurnal tekshirildi",
            )
        )
        await session.commit()
    async with model_database.session() as session:
        records = list(
            (
                await session.scalars(
                    select(AuditEvent)
                    .where(AuditEvent.entity_id == str(mark.id))
                    .order_by(AuditEvent.id)
                )
            ).all()
        )
        assert len(records) == 2
        assert records[-1].body["details"]["reason"] == "Jurnal tekshirildi"
        assert records[-1].body["changes"]["status"] == {"before": "present", "after": "late"}
    with pytest.raises(DBAPIError, match="reason required"):
        async with model_database.session() as session:
            await context(session, teacher.id, Role.TEACHER)
            await session.execute(
                update(Attendance)
                .where(Attendance.id == mark.id)
                .values(status=AttendanceStatus.ABSENT)
            )
            await session.commit()
    with pytest.raises(DBAPIError, match="reason required"):
        async with model_database.session() as session:
            session.add(
                AttendanceChange(
                    attendance_id=mark.id,
                    actor_id=teacher.id,
                    actor_name="Namuna Ustoz",
                    actor_role="teacher",
                    action="correct",
                    old_status="late",
                    new_status="absent",
                )
            )
            await session.commit()
    async with model_database.session() as session:
        assert (
            await session.scalar(select(Attendance.status).where(Attendance.id == mark.id))
            == AttendanceStatus.LATE
        )


async def test_compact_large_lists_and_capability_redaction(model_database: Database) -> None:
    capability = "https://t.me/namuna_bot?start=staff_do-not-store-this"
    async with model_database.session() as session:
        session.add(Subject(name="Link namuna", description=capability))
        await session.commit()
        item = await session.scalar(select(AuditEvent))
        assert item is not None and capability not in json.dumps(item.body)
        result = await session.scalar(
            text("SELECT audit.compact(CAST(:value AS jsonb))"),
            {"value": json.dumps(list(range(10000)))},
        )
        assert result["count"] == 10000 and len(result["sha256"]) == 64


async def test_concurrent_events_and_tashkent_second_boundary(model_database: Database) -> None:
    async def create(index: int) -> None:
        async with model_database.session() as session:
            session.add(Subject(name=f"Parallel namuna {index}"))
            await session.commit()

    await asyncio.gather(*(create(index) for index in range(8)))
    async with model_database.session() as session:
        entries = list((await session.scalars(select(AuditEvent))).all())
        assert len(entries) == 8 and len({entry.id for entry in entries}) == 8
        for stamp, expected_day in (
            (datetime(2026, 10, 14, 18, 59, 59, 999999, tzinfo=UTC), date(2026, 10, 14)),
            (datetime(2026, 10, 14, 19, 0, 0, tzinfo=UTC), date(2026, 10, 15)),
        ):
            event_id = await session.scalar(
                text("""
            SELECT audit.emit('test.boundary',NULL,NULL,NULL,'{}',
                '{}',NULL,:stamp,'{}')
            """),
                {"stamp": stamp},
            )
            row = await session.get(AuditEvent, event_id)
            assert row is not None and row.local_day == expected_day
            assert row.occurred_at == stamp
        await session.commit()


async def test_actor_snapshot_survives_staff_removal(model_database: Database) -> None:
    person = staff(first_name="Namuna", last_name="Snapshot", role=Role.SUPERADMIN)
    async with model_database.session() as session:
        session.add(person)
        await session.flush()
        await context(session, person.id, Role.SUPERADMIN)
        session.add(Subject(name="Snapshot namuna"))
        await session.flush()
        await session.delete(person)
        await session.commit()
    async with model_database.session() as session:
        record = await session.scalar(
            select(AuditEvent).where(AuditEvent.action == "subject.insert")
        )
        assert record is not None and record.actor_id == person.id
        assert record.body["actor"]["name"] == "Namuna Xodim"
        assert await session.get(type(person), person.id) is None
