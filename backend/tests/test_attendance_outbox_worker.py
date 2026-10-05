import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from factories import parent, student
from test_learning_models import seed_group

from neoavlod.database import Database
from neoavlod.errors import DomainError
from neoavlod.models import (
    Attendance,
    AttendanceStatus,
    NotificationOutbox,
    OutboxStatus,
    Parent,
    Student,
)
from neoavlod.services.outbox import (
    OutboxWorker,
    claim_pending_outbox_items,
    dispatch_pending_outbox,
    format_attendance_message,
)
from neoavlod.settings import Settings

pytestmark = pytest.mark.anyio


class CapturingSender:
    def __init__(self, should_fail: bool = False) -> None:
        self.sent: list[tuple[int, str]] = []
        self.should_fail = should_fail

    async def send_message(self, telegram_id: int, message: str) -> None:
        if self.should_fail:
            raise DomainError("Telegram xizmati vaqtincha mavjud emas", 503)
        self.sent.append((telegram_id, message))


def test_format_attendance_message() -> None:
    payload = {
        "student_name": "Ali Valiyev",
        "group_name": "Python Bootcamp",
        "date": "2026-10-05",
        "status": "present",
        "status_label": "Bor",
        "note": "Faol qatnashdi",
    }
    msg = format_attendance_message(payload)
    assert "📋 Davomat bildirishnomasi" in msg
    assert "Farzandingiz: Ali Valiyev" in msg
    assert "Guruh: Python Bootcamp" in msg
    assert "Sana: 2026-10-05" in msg
    assert "Holati: Bor" in msg
    assert "Izoh: Faol qatnashdi" in msg


async def setup_attendance_fixture(
    database: Database,
    *,
    parent_telegram_id: int | None = 998877,
) -> tuple[Parent, Student, Attendance]:
    learning_group = await seed_group(database)
    async with database.session() as session, session.begin():
        guardian = parent(telegram_id=parent_telegram_id)
        session.add(guardian)
        await session.flush()
        learner = student(learning_group.id, guardian.id)
        session.add(learner)
        await session.flush()
        att = Attendance(
            group_id=learning_group.id,
            student_id=learner.id,
            date=datetime.now(UTC).date(),
            status=AttendanceStatus.PRESENT,
            marked_by=learning_group.teacher_id,
        )
        session.add(att)
    return guardian, learner, att


async def test_dispatch_outbox_to_connected_parent(model_database: Database) -> None:
    guardian, learner, att = await setup_attendance_fixture(
        model_database, parent_telegram_id=998877
    )
    sender = CapturingSender()

    async with model_database.session() as session, session.begin():
        outbox_item = NotificationOutbox(
            idempotency_key=f"att_test_{att.id}",
            attendance_id=att.id,
            parent_id=guardian.id,
            telegram_id=guardian.telegram_id,
            payload={
                "student_name": f"{learner.first_name} {learner.last_name}",
                "group_name": "Guruh-1",
                "date": att.date.isoformat(),
                "status": "present",
                "status_label": "Bor",
            },
            status=OutboxStatus.PENDING,
        )
        session.add(outbox_item)

    dispatched = await dispatch_pending_outbox(model_database, sender=sender)
    assert dispatched == 1
    assert len(sender.sent) == 1
    chat_id, text = sender.sent[0]
    assert chat_id == 998877
    assert "Davomat bildirishnomasi" in text

    async with model_database.session() as session:
        record = await session.get(NotificationOutbox, outbox_item.id)
        assert record is not None
        assert record.status == OutboxStatus.DELIVERED
        assert record.delivered_at is not None
        assert record.attempts == 1


async def test_unconnected_parent_handling(model_database: Database) -> None:
    guardian, learner, att = await setup_attendance_fixture(
        model_database, parent_telegram_id=None
    )
    sender = CapturingSender()

    async with model_database.session() as session, session.begin():
        outbox_item = NotificationOutbox(
            idempotency_key=f"att_test_unconnected_{att.id}",
            attendance_id=att.id,
            parent_id=guardian.id,
            telegram_id=None,
            payload={
                "student_name": f"{learner.first_name} {learner.last_name}",
                "group_name": "Guruh-1",
                "date": att.date.isoformat(),
                "status": "present",
                "status_label": "Bor",
            },
            status=OutboxStatus.PENDING,
        )
        session.add(outbox_item)

    # First dispatch: parent still not connected -> item becomes SKIPPED
    dispatched = await dispatch_pending_outbox(model_database, sender=sender)
    assert dispatched == 0
    assert len(sender.sent) == 0

    async with model_database.session() as session:
        record = await session.get(NotificationOutbox, outbox_item.id)
        assert record is not None
        assert record.status == OutboxStatus.SKIPPED

    # Now parent connects their Telegram account
    async with model_database.session() as session, session.begin():
        parent_db = await session.get(Parent, guardian.id)
        assert parent_db is not None
        parent_db.telegram_id = 445566
        # Mark item PENDING again to simulate retry after connection
        item_db = await session.get(NotificationOutbox, outbox_item.id)
        assert item_db is not None
        item_db.status = OutboxStatus.PENDING

    # Second dispatch: picks up parent's telegram_id and delivers
    dispatched2 = await dispatch_pending_outbox(model_database, sender=sender)
    assert dispatched2 == 1
    assert len(sender.sent) == 1
    assert sender.sent[0][0] == 445566


async def test_retry_and_exponential_backoff_on_failure(model_database: Database) -> None:
    guardian, learner, att = await setup_attendance_fixture(
        model_database, parent_telegram_id=998877
    )
    failing_sender = CapturingSender(should_fail=True)

    async with model_database.session() as session, session.begin():
        outbox_item = NotificationOutbox(
            idempotency_key=f"att_test_fail_{att.id}",
            attendance_id=att.id,
            parent_id=guardian.id,
            telegram_id=guardian.telegram_id,
            payload={
                "student_name": f"{learner.first_name} {learner.last_name}",
                "group_name": "Guruh-1",
                "date": att.date.isoformat(),
                "status": "absent",
                "status_label": "Yo‘q",
            },
            status=OutboxStatus.PENDING,
        )
        session.add(outbox_item)

    now = datetime.now(UTC)
    # Attempt 1
    dispatched = await dispatch_pending_outbox(
        model_database, sender=failing_sender, max_attempts=3
    )
    assert dispatched == 0

    async with model_database.session() as session:
        record = await session.get(NotificationOutbox, outbox_item.id)
        assert record is not None
        assert record.attempts == 1
        assert record.status == OutboxStatus.PENDING
        assert record.available_at > now
        assert "vaqtincha mavjud emas" in (record.last_error or "")

    # Fast forward available_at to test next attempt
    async with model_database.session() as session, session.begin():
        rec = await session.get(NotificationOutbox, outbox_item.id)
        assert rec is not None
        rec.available_at = datetime.now(UTC) - timedelta(seconds=1)

    # Attempt 2
    await dispatch_pending_outbox(model_database, sender=failing_sender, max_attempts=3)
    async with model_database.session() as session:
        record2 = await session.get(NotificationOutbox, outbox_item.id)
        assert record2 is not None
        assert record2.attempts == 2
        assert record2.status == OutboxStatus.PENDING

    # Fast forward available_at to test final attempt
    async with model_database.session() as session, session.begin():
        rec2 = await session.get(NotificationOutbox, outbox_item.id)
        assert rec2 is not None
        rec2.available_at = datetime.now(UTC) - timedelta(seconds=1)

    # Attempt 3 (reaches max_attempts)
    await dispatch_pending_outbox(model_database, sender=failing_sender, max_attempts=3)
    async with model_database.session() as session:
        record3 = await session.get(NotificationOutbox, outbox_item.id)
        assert record3 is not None
        assert record3.attempts == 3
        assert record3.status == OutboxStatus.FAILED


async def test_restart_and_lease_recovery(model_database: Database) -> None:
    guardian, learner, att = await setup_attendance_fixture(
        model_database, parent_telegram_id=998877
    )
    sender = CapturingSender()

    # Simulate crashed worker: item locked in PROCESSING, but lease expired 10 seconds ago
    past = datetime.now(UTC) - timedelta(seconds=10)
    crashed_worker = uuid.uuid4()
    async with model_database.session() as session, session.begin():
        outbox_item = NotificationOutbox(
            idempotency_key=f"att_test_crash_{att.id}",
            attendance_id=att.id,
            parent_id=guardian.id,
            telegram_id=guardian.telegram_id,
            payload={
                "student_name": f"{learner.first_name} {learner.last_name}",
                "group_name": "Guruh-1",
                "date": att.date.isoformat(),
                "status": "late",
                "status_label": "Kechikdi",
            },
            status=OutboxStatus.PROCESSING,
            locked_by=crashed_worker,
            locked_until=past,
            attempts=1,
        )
        session.add(outbox_item)

    # Restarted worker dispatches
    dispatched = await dispatch_pending_outbox(model_database, sender=sender)
    assert dispatched == 1
    assert len(sender.sent) == 1

    async with model_database.session() as session:
        record = await session.get(NotificationOutbox, outbox_item.id)
        assert record is not None
        assert record.status == OutboxStatus.DELIVERED
        assert record.delivered_at is not None
        assert record.locked_until is None


async def test_concurrent_claim_isolation(model_database: Database) -> None:
    guardian, _, att = await setup_attendance_fixture(
        model_database, parent_telegram_id=998877
    )

    item_ids: list[uuid.UUID] = []
    async with model_database.session() as session, session.begin():
        for i in range(10):
            item = NotificationOutbox(
                idempotency_key=f"att_concurrent_{att.id}_{i}",
                attendance_id=att.id,
                parent_id=guardian.id,
                telegram_id=guardian.telegram_id,
                payload={"student_name": f"Student {i}"},
                status=OutboxStatus.PENDING,
            )
            session.add(item)
            item_ids.append(item.id)

    worker_1 = uuid.uuid4()
    worker_2 = uuid.uuid4()

    async def claim_batch(worker_id: uuid.UUID) -> list[uuid.UUID]:
        async with model_database.session() as session:
            claimed = await claim_pending_outbox_items(session, worker_id, limit=5)
            return [c.id for c in claimed]

    results = await asyncio.gather(claim_batch(worker_1), claim_batch(worker_2))
    batch_1, batch_2 = results[0], results[1]

    # Both workers claimed distinct subsets
    set_1 = set(batch_1)
    set_2 = set(batch_2)
    assert set_1.isdisjoint(set_2)
    assert len(set_1) + len(set_2) == 10


async def test_outbox_worker_single_iteration(model_database: Database) -> None:
    guardian, learner, att = await setup_attendance_fixture(
        model_database, parent_telegram_id=998877
    )
    sender = CapturingSender()
    settings = Settings()

    async with model_database.session() as session, session.begin():
        item = NotificationOutbox(
            idempotency_key=f"att_worker_single_{att.id}",
            attendance_id=att.id,
            parent_id=guardian.id,
            telegram_id=guardian.telegram_id,
            payload={
                "student_name": f"{learner.first_name} {learner.last_name}",
                "group_name": "Guruh-1",
                "date": att.date.isoformat(),
                "status": "present",
                "status_label": "Bor",
            },
            status=OutboxStatus.PENDING,
        )
        session.add(item)

    worker = OutboxWorker(
        model_database,
        settings=settings,
        sender=sender,
    )
    processed = await worker.run_single_iteration()
    assert processed == 1
    assert len(sender.sent) == 1
