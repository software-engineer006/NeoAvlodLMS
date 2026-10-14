import asyncio
import uuid
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import func, select
from test_attendance_finalization import setup_class_with_students as seed
from test_rbac import Actor, actor, client_for

from neoavlod.database import Database
from neoavlod.models import (
    Attendance,
    AttendanceBatch,
    Group,
    NotificationOutbox,
    OutboxStatus,
    Role,
)
from neoavlod.services import attendance
from neoavlod.services.outbox import format_attendance_message

pytestmark = [pytest.mark.anyio, pytest.mark.usefixtures("attendance_clock")]


@pytest.fixture(autouse=True)
def disable_notification_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    async def no_dispatch(*args: object) -> None:
        pass

    monkeypatch.setattr(attendance, "dispatch_pending_outbox_stub", no_dispatch)


@pytest.mark.parametrize(
    ("now", "target", "editable"),
    [
        (datetime(2026, 10, 5, 10, tzinfo=UTC), date(2026, 10, 5), True),
        (datetime(2026, 10, 6, 10, tzinfo=UTC), date(2026, 10, 5), True),
        (datetime(2026, 10, 7, 18, 59, 59, 999999, tzinfo=UTC), date(2026, 10, 5), True),
        (datetime(2026, 10, 7, 19, tzinfo=UTC), date(2026, 10, 5), False),
        (datetime(2026, 10, 5, 10, tzinfo=UTC), date(2026, 10, 6), False),
        (datetime(2026, 10, 5, 19, tzinfo=UTC), date(2026, 10, 6), True),
    ],
)
def test_window_uses_tashkent_calendar(
    monkeypatch: pytest.MonkeyPatch, now: datetime, target: date, editable: bool
) -> None:
    monkeypatch.setattr(attendance, "attendance_now", lambda: now)
    allowed, deadline, reason = attendance.edit_window(target)
    assert allowed is editable
    assert deadline.date() == date.fromordinal(target.toordinal() + 2)
    offset = deadline.utcoffset()
    assert offset is not None and offset.total_seconds() == 18000
    assert (reason is None) is editable


async def finalize_fixture(database: Database) -> tuple[Actor, Group, list[uuid.UUID], str]:
    teacher, group, students = await seed(database)
    base = f"/api/v1/teacher/groups/{group.id}/attendance"
    payload = {
        "date": "2026-10-05",
        "items": [
            {"student_id": str(students[0]), "status": "present"},
            {"student_id": str(students[1]), "status": "absent"},
        ],
    }
    async with client_for(teacher) as client:
        result = await client.post(base + "/finalize", json=payload)
        assert result.status_code == 200, result.text
    return teacher, group, students, base


async def test_finalized_correction_preserves_batch_updates_stats_and_pending_payload(
    model_database: Database, monkeypatch: pytest.MonkeyPatch
) -> None:
    teacher, group, students, base = await finalize_fixture(model_database)
    monkeypatch.setattr(attendance, "attendance_now", lambda: datetime(2026, 10, 7, 18, tzinfo=UTC))
    async with model_database.session() as session:
        batch = await session.scalar(select(AttendanceBatch))
        assert batch
        original = (batch.id, batch.finalized_at)
    payload = {
        "date": "2026-10-05",
        "reason": "Darsdagi qatnashuv qayta tekshirildi",
        "items": [
            {"student_id": str(students[0]), "status": "absent", "note": "  Tuzatildi  "},
        ],
    }
    async with client_for(teacher) as client:
        response = await client.post(base + "/correct", json=payload)
        assert response.status_code == 200, response.text
        sheet = response.json()
        assert sheet["finalized"] and sheet["can_edit"]
        assert sheet["edit_deadline"].startswith("2026-10-07T23:59:59")
        assert sheet["edit_disabled_reason"] is None
        item = next(i for i in sheet["items"] if i["student_id"] == str(students[0]))
        assert item["status"] == "absent" and item["note"] == "Tuzatildi"
        assert (await client.post(base + "/correct", json=payload)).status_code == 200
        history = (await client.get(base + "/history", params={"month": "2026-10"})).json()
        assert history["summary"]["absent_count"] == 2
        assert history["summary"]["present_count"] == 0
    async with model_database.session() as session:
        batch = await session.scalar(select(AttendanceBatch))
        assert batch and (batch.id, batch.finalized_at) == original
        outbox = list((await session.scalars(select(NotificationOutbox))).all())
        assert len(outbox) == 2
        updated = next(o for o in outbox if o.telegram_id is not None)
        assert updated.payload["status"] == "absent" and updated.payload["correction"]
        assert "Davomat tuzatildi" in format_attendance_message(updated.payload)


async def test_expired_future_and_foreign_writes_are_rejected_atomically(
    model_database: Database, monkeypatch: pytest.MonkeyPatch
) -> None:
    teacher, group, students, base = await finalize_fixture(model_database)
    other = await actor(model_database, role=Role.TEACHER)
    boss = await actor(model_database, role=Role.SUPERADMIN)
    payload = {
        "date": "2026-10-05",
        "items": [
            {"student_id": str(students[0]), "status": "absent"},
        ],
    }
    async with client_for(other) as client:
        assert (await client.post(base + "/correct", json=payload)).status_code == 404
    async with client_for(boss) as client:
        assert (await client.post(base + "/correct", json=payload)).status_code == 403
    monkeypatch.setattr(attendance, "attendance_now", lambda: datetime(2026, 10, 7, 19, tzinfo=UTC))
    async with client_for(teacher) as client:
        sheet = (await client.get(base, params={"date": "2026-10-05"})).json()
        assert not sheet["can_edit"] and "muddat tugagan" in sheet["edit_disabled_reason"]
        for endpoint in ("draft", "correct", "finalize"):
            assert (await client.post(base + "/" + endpoint, json=payload)).status_code == 409
            future = {**payload, "date": "2026-10-09"}
            assert (await client.post(base + "/" + endpoint, json=future)).status_code == 409
    async with model_database.session() as session:
        record = await session.scalar(
            select(Attendance).where(Attendance.student_id == students[0])
        )
        assert record and record.status == "present"
        assert await session.scalar(select(func.count()).select_from(Attendance)) == 2


async def test_invalid_or_duplicate_items_roll_back_and_unfinalized_cannot_be_corrected(
    model_database: Database,
) -> None:
    teacher, group, students, base = await finalize_fixture(model_database)
    valid = {"student_id": str(students[0]), "status": "absent"}
    invalid = {"student_id": str(uuid.uuid4()), "status": "present"}
    async with client_for(teacher) as client:
        for items in ([valid, invalid], [valid, valid]):
            response = await client.post(
                base + "/correct", json={"date": "2026-10-05", "items": items}
            )
            assert response.status_code == 422
        response = await client.post(
            base + "/correct", json={"date": "2026-10-04", "items": [valid]}
        )
        assert response.status_code == 409
    async with model_database.session() as session:
        record = await session.scalar(
            select(Attendance).where(Attendance.student_id == students[0])
        )
        assert record and record.status == "present"
        assert await session.scalar(select(func.count()).select_from(NotificationOutbox)) == 2


async def test_delivered_notification_gets_one_correction_on_concurrent_retries(
    model_database: Database,
) -> None:
    teacher, group, students, base = await finalize_fixture(model_database)
    async with model_database.session() as session:
        delivered = await session.scalar(
            select(NotificationOutbox).where(NotificationOutbox.telegram_id.is_not(None))
        )
        assert delivered
        delivered.status = OutboxStatus.DELIVERED
        await session.commit()
    payload = {
        "date": "2026-10-05",
        "reason": "Kechikish vaqti aniqlashtirildi",
        "items": [
            {"student_id": str(students[0]), "status": "late", "note": "Aniqlashtirildi"},
        ],
    }
    async with client_for(teacher) as client:
        responses = await asyncio.gather(
            *[client.post(base + "/correct", json=payload) for _ in range(2)]
        )
        assert all(r.status_code == 200 for r in responses)
    async with model_database.session() as session:
        outbox = list((await session.scalars(select(NotificationOutbox))).all())
        assert len(outbox) == 3
        assert sum(o.payload.get("correction") is True for o in outbox) == 1
        assert await session.scalar(select(func.count()).select_from(AttendanceBatch)) == 1
