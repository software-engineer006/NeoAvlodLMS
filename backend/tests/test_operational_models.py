from datetime import UTC, date, datetime, timedelta
from typing import cast

import pytest
from factories import parent, staff, student
from sqlalchemy import Table
from sqlalchemy.exc import IntegrityError
from test_learning_models import seed_group

from neoavlod.database import Database
from neoavlod.models import (
    Attendance,
    AttendanceBatch,
    AttendanceStatus,
    AuthSession,
    NotificationOutbox,
    OTPChallenge,
    OTPPurpose,
    Portal,
    RefreshToken,
    Student,
    SystemSettings,
)

pytestmark = pytest.mark.anyio


async def seed_attendance(database: Database) -> Attendance:
    learning_group = await seed_group(database)
    async with database.session() as session:
        guardian = parent()
        session.add(guardian)
        await session.flush()
        learner = student(learning_group.id, guardian.id)
        session.add(learner)
        await session.flush()
        entry = Attendance(
            group_id=learning_group.id,
            student_id=learner.id,
            date=date.today(),
            status=AttendanceStatus.PRESENT,
            marked_by=learning_group.teacher_id,
        )
        session.add(entry)
        await session.commit()
        return entry


async def test_attendance_and_finalization_are_unique(model_database: Database) -> None:
    entry = await seed_attendance(model_database)
    with pytest.raises(IntegrityError):
        async with model_database.session() as session:
            session.add(
                Attendance(
                    group_id=entry.group_id,
                    student_id=entry.student_id,
                    date=entry.date,
                    status=AttendanceStatus.LATE,
                    marked_by=entry.marked_by,
                )
            )
            await session.flush()
    async with model_database.session() as session:
        batch = AttendanceBatch(
            group_id=entry.group_id, date=entry.date, finalized_by=entry.marked_by
        )
        session.add(batch)
        await session.commit()
    with pytest.raises(IntegrityError):
        async with model_database.session() as session:
            session.add(
                AttendanceBatch(
                    group_id=entry.group_id, date=entry.date, finalized_by=entry.marked_by
                )
            )
            await session.flush()


async def test_settings_singleton_and_version_constraints(model_database: Database) -> None:
    async with model_database.session() as session:
        session.add(SystemSettings(parameters={"locale": "uz"}))
        await session.commit()
    with pytest.raises(IntegrityError):
        async with model_database.session() as session:
            session.add(SystemSettings(id=2))
            await session.flush()
    with pytest.raises(IntegrityError):
        async with model_database.session() as session:
            await session.execute(cast(Table, SystemSettings.__table__).update().values(version=-1))


async def test_otp_hash_attempts_and_expiry(model_database: Database) -> None:
    async with model_database.session() as session:
        person = staff()
        session.add(person)
        await session.commit()
    now = datetime.now(UTC)
    valid = {
        "staff_id": person.id,
        "portal": Portal.TEACHER,
        "purpose": OTPPurpose.LOGIN,
        "code_hash": "a" * 64,
        "expires_at": now + timedelta(minutes=5),
    }
    for invalid in (
        {"attempts": 6},
        {"code_hash": "123456"},
        {"expires_at": now - timedelta(days=1)},
    ):
        with pytest.raises(IntegrityError):
            async with model_database.session() as session:
                await session.execute(
                    cast(Table, OTPChallenge.__table__).insert().values(**(valid | invalid))
                )


async def test_session_refresh_uniqueness_and_revocation_storage(model_database: Database) -> None:
    async with model_database.session() as session:
        person = staff()
        session.add(person)
        await session.flush()
        now = datetime.now(UTC)
        auth = AuthSession(
            staff_id=person.id,
            portal=Portal.TEACHER,
            access_token_hash="a" * 64,
            csrf_token_hash="b" * 64,
            access_expires_at=now + timedelta(minutes=15),
            expires_at=now + timedelta(days=7),
        )
        session.add(auth)
        await session.flush()
        refresh = RefreshToken(session_id=auth.id, token_hash="c" * 64, expires_at=auth.expires_at)
        session.add(refresh)
        await session.commit()
        auth.revoked_at = now
        await session.commit()
    with pytest.raises(IntegrityError):
        async with model_database.session() as session:
            session.add(
                RefreshToken(session_id=auth.id, token_hash="c" * 64, expires_at=auth.expires_at)
            )
            await session.flush()


async def test_outbox_idempotency_and_payload_shape(model_database: Database) -> None:
    entry = await seed_attendance(model_database)
    async with model_database.session() as session:
        learner = await session.get(Student, entry.student_id)
        assert learner is not None
        values = {
            "idempotency_key": "attendance-1",
            "attendance_id": entry.id,
            "parent_id": learner.parent_id,
            "payload": {"message": "Dars davomati"},
        }
        session.add(NotificationOutbox(**values))
        await session.commit()
    with pytest.raises(IntegrityError):
        async with model_database.session() as session:
            session.add(NotificationOutbox(**values))
            await session.flush()
    with pytest.raises(IntegrityError):
        async with model_database.session() as session:
            invalid = values | {"idempotency_key": "invalid-payload", "payload": ["bad"]}
            await session.execute(
                cast(Table, NotificationOutbox.__table__).insert().values(**invalid)
            )
