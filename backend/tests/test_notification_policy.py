"""Professional snapshots, truthful authors, silent admins and claimed queue races."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from test_attendance_finalization import setup_class_with_students as seed
from test_attendance_outbox_worker import CapturingSender
from test_rbac import Actor, actor, client_for

from neoavlod.attendance_messages import DEFAULT_TEMPLATE
from neoavlod.database import Database
from neoavlod.models import (
    Attendance,
    AttendanceChange,
    Group,
    NotificationOutbox,
    OutboxStatus,
    Role,
)
from neoavlod.services import attendance
from neoavlod.services.outbox import dispatch_pending_outbox

pytestmark = [pytest.mark.anyio, pytest.mark.usefixtures("attendance_clock")]


@pytest.fixture(autouse=True)
def no_live_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    async def noop(*args: object) -> None:
        pass

    monkeypatch.setattr(attendance, "dispatch_pending_outbox_stub", noop)


async def finalized(database: Database) -> tuple[Actor, Group, list[uuid.UUID]]:
    teacher, group, students = await seed(database)
    async with client_for(teacher) as client:
        response = await client.post(
            f"/api/v1/teacher/groups/{group.id}/attendance/finalize",
            json={
                "date": "2026-10-05",
                "items": [
                    {
                        "student_id": str(students[0]),
                        "status": "present",
                        "note": "Ustozning fikri",
                    },
                    {"student_id": str(students[1]), "status": "absent"},
                ],
            },
        )
        assert response.status_code == 200, response.text
    return teacher, group, students


@pytest.mark.parametrize("role", [Role.ADMIN, Role.SUPERADMIN])
@pytest.mark.parametrize(
    "state",
    [OutboxStatus.PENDING, OutboxStatus.PROCESSING, OutboxStatus.FAILED, OutboxStatus.DELIVERED],
)
async def test_admin_corrections_never_send_or_rewrite_snapshot(
    model_database: Database, role: Role, state: OutboxStatus
) -> None:
    _, group, students = await finalized(model_database)
    editor = await actor(model_database, role=role, permissions=["attendance:write"])
    async with model_database.session() as session:
        queued = await session.scalar(
            select(NotificationOutbox)
            .join(Attendance, Attendance.id == NotificationOutbox.attendance_id)
            .where(Attendance.student_id == students[0])
        )
        assert queued is not None
        queued.status = state
        queued.locked_by = uuid.uuid4() if state == OutboxStatus.PROCESSING else None
        queued.locked_until = (
            datetime.now(UTC) + timedelta(seconds=30) if queued.locked_by else None
        )
        frozen = dict(queued.payload)
        key = queued.id
        await session.commit()
    async with client_for(editor) as client:
        response = await client.post(
            f"/api/v1/admin/attendance/groups/{group.id}/attendance/correct",
            json={
                "date": "2026-10-05",
                "reason": "Administrator jurnalni tekshirdi",
                "items": [
                    {"student_id": str(students[0]), "status": "absent", "note": "Adminning fikri"}
                ],
            },
        )
        assert response.status_code == 200, response.text
    sender = CapturingSender()
    assert await dispatch_pending_outbox(model_database, sender=sender) == 0
    assert sender.sent == []
    async with model_database.session() as session:
        queue = (await session.scalars(select(NotificationOutbox))).all()
        assert len(queue) == 2
        selected = next(item for item in queue if item.id == key)
        assert selected.payload == frozen
        assert selected.status == (
            OutboxStatus.DELIVERED if state == OutboxStatus.DELIVERED else OutboxStatus.SKIPPED
        )
        audit = await session.scalar(
            select(AttendanceChange).where(AttendanceChange.action == "correct")
        )
        assert (
            audit is not None
            and audit.actor_id == editor.staff_id
            and audit.reason == "Administrator jurnalni tekshirdi"
        )


async def test_teacher_note_author_and_template_version_survive_admin_status_edits(
    model_database: Database,
) -> None:
    teacher, group, students = await finalized(model_database)
    admin = await actor(model_database, permissions=["attendance:write"])
    endpoint = "/api/v1/admin/attendance/message-template"
    changed = DEFAULT_TEMPLATE + "\nNamuna yangi shablon"
    async with client_for(admin) as client:
        assert (
            await client.put(endpoint, json={"body": changed, "expected_version": 0})
        ).status_code == 200
        assert (
            await client.post(
                f"/api/v1/admin/attendance/groups/{group.id}/attendance/correct",
                json={
                    "date": "2026-10-05",
                    "reason": "Jurnal tekshirildi",
                    "items": [
                        {
                            "student_id": str(students[0]),
                            "status": "absent",
                            "note": "Ustozning fikri",
                        }
                    ],
                },
            )
        ).status_code == 200
    async with client_for(teacher) as client:
        response = await client.post(
            f"/api/v1/teacher/groups/{group.id}/attendance/correct",
            json={
                "date": "2026-10-05",
                "reason": "Kelgan vaqti tekshirildi",
                "items": [
                    {"student_id": str(students[0]), "status": "late", "note": "Ustozning fikri"}
                ],
            },
        )
        assert response.status_code == 200, response.text
    async with model_database.session() as session:
        item = await session.scalar(
            select(NotificationOutbox).where(NotificationOutbox.status == OutboxStatus.PENDING)
        )
        assert item is not None
        text = str(item.payload["message_text"])
        assert "05.10.2026" in text and "09:00–10:30" in text and "Toshkent vaqti" in text
        assert "Kech qoldi" in text and "O‘qituvchi" in str(item.payload["feedback_author"])
        assert "Administrator" not in str(item.payload["feedback_author"])
        assert item.payload["template_version"] == 1
        frozen = dict(item.payload)
    async with client_for(admin) as client:
        assert (
            await client.put(
                endpoint, json={"body": changed + "\nNamuna yana", "expected_version": 1}
            )
        ).status_code == 200
    async with model_database.session() as session:
        item = await session.scalar(
            select(NotificationOutbox).where(NotificationOutbox.status == OutboxStatus.PENDING)
        )
        assert item is not None and item.payload == frozen
    sender = CapturingSender()
    assert await dispatch_pending_outbox(model_database, sender=sender) == 1
    assert sender.sent[0][1] == frozen["message_text"]


async def test_expired_claim_owner_cannot_send_reclaimed_payload(model_database: Database) -> None:
    from neoavlod.services.outbox import claim_pending_outbox_items, process_outbox_item

    await finalized(model_database)
    old_worker, new_worker = uuid.uuid4(), uuid.uuid4()
    async with model_database.session() as session:
        original = (await claim_pending_outbox_items(session, old_worker))[0]
        original.locked_until = datetime.now(UTC) - timedelta(seconds=1)
        await session.commit()
    async with model_database.session() as session:
        current = (await claim_pending_outbox_items(session, new_worker))[0]
    sender = CapturingSender()
    async with model_database.session() as session:
        assert not await process_outbox_item(session, original, sender, worker_id=old_worker)
    assert sender.sent == []
    async with model_database.session() as session:
        assert await process_outbox_item(session, current, sender, worker_id=new_worker)
    assert len(sender.sent) == 1


@pytest.mark.parametrize("role", [Role.ADMIN, Role.TEACHER])
async def test_edit_after_claim_invalidates_old_worker_and_only_teacher_requeues(
    model_database: Database, role: Role
) -> None:
    from neoavlod.services.outbox import claim_pending_outbox_items, process_outbox_item

    teacher, group, students = await finalized(model_database)
    editor = (
        teacher
        if role == Role.TEACHER
        else await actor(model_database, permissions=["attendance:write"])
    )
    worker = uuid.uuid4()
    async with model_database.session() as session:
        original = (await claim_pending_outbox_items(session, worker))[0]
    portal = "teacher" if role == Role.TEACHER else "admin/attendance"
    async with client_for(editor) as client:
        response = await client.post(
            f"/api/v1/{portal}/groups/{group.id}/attendance/correct",
            json={
                "date": "2026-10-05",
                "reason": "Aniq tekshirildi",
                "items": [
                    {"student_id": str(students[0]), "status": "absent", "note": "Yangi fikr"}
                ],
            },
        )
        assert response.status_code == 200, response.text
    sender = CapturingSender()
    async with model_database.session() as session:
        assert not await process_outbox_item(session, original, sender, worker_id=worker)
    assert sender.sent == []
    count = await dispatch_pending_outbox(model_database, sender=sender)
    assert count == (1 if role == Role.TEACHER else 0)
    if sender.sent:
        assert "Kelmadi" in sender.sent[0][1] and "Yangi fikr" in sender.sent[0][1]


async def test_teacher_status_update_attributes_an_inherited_admin_note_truthfully(
    model_database: Database,
) -> None:
    teacher, group, students = await finalized(model_database)
    admin = await actor(
        model_database, permissions=["attendance:write"], first_name="Namuna", last_name="Admin"
    )
    body = {
        "date": "2026-10-05",
        "reason": "Tekshirildi",
        "items": [{"student_id": str(students[0]), "status": "present", "note": "Admin izohi"}],
    }
    async with client_for(admin) as client:
        assert (
            await client.post(
                f"/api/v1/admin/attendance/groups/{group.id}/attendance/correct", json=body
            )
        ).status_code == 200
    body["items"] = [{"student_id": str(students[0]), "status": "absent", "note": "Admin izohi"}]
    async with client_for(teacher) as client:
        assert (
            await client.post(f"/api/v1/teacher/groups/{group.id}/attendance/correct", json=body)
        ).status_code == 200
    async with model_database.session() as session:
        item = await session.scalar(
            select(NotificationOutbox).where(NotificationOutbox.status == OutboxStatus.PENDING)
        )
        assert item is not None and item.payload["feedback_author"] == "Administrator Namuna Admin"
        assert "Izoh (Administrator Namuna Admin): Admin izohi" in str(item.payload["message_text"])
