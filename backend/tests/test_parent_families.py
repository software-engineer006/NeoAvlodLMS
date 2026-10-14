"""Explicit family linkage; each child's attendance stays private and distinct."""

import asyncio
import uuid
from datetime import UTC, datetime

import pytest
from httpx import Response
from sqlalchemy import func, select, update
from test_attendance_outbox_worker import CapturingSender
from test_rbac import actor, client_for
from test_teacher_api import setup_two_teachers_with_classes

from neoavlod.database import Database
from neoavlod.models import (
    AuditEvent,
    NotificationOutbox,
    OutboxStatus,
    Parent,
    Student,
    SystemSettings,
)
from neoavlod.services import attendance
from neoavlod.services.outbox import dispatch_pending_outbox

pytestmark = pytest.mark.anyio


async def test_shared_parent_selection_parallel_children_and_exact_audit(
    model_database: Database,
) -> None:
    _, first, _, _, pupil_id, other_id = await setup_two_teachers_with_classes(model_database)
    editor = await actor(model_database, permissions=["students:edit", "students:create"])
    reader = await actor(model_database, permissions=["students:read"])
    async with model_database.session() as session:
        pupil = await session.get(Student, pupil_id)
        assert pupil is not None and pupil.parent_id is not None
        parent_id = pupil.parent_id
    async with client_for(reader) as client:
        assert (await client.get("/api/v1/admin/lookups/parents")).status_code == 403
    async with client_for(editor) as client:
        response = await client.patch(
            f"/api/v1/admin/students/{other_id}", json={"parent_id": str(parent_id)}
        )
        assert response.status_code == 200, response.text
        assert response.json()["parent"]["child_count"] == 2
        options = (await client.get("/api/v1/admin/lookups/parents", params={"q": "Ota1"})).json()[
            "items"
        ]
        assert len(options) == 1 and options[0]["child_count"] == 2
        assert not ({"telegram_id", "auth_uuid", "auth_expires_at"} & set(options[0]))
        assert (
            await client.patch(
                f"/api/v1/admin/students/{other_id}", json={"parent_id": str(uuid.uuid4())}
            )
        ).status_code == 404
        assert (
            await client.patch(
                f"/api/v1/admin/students/{other_id}",
                json={"parent_id": str(parent_id), "parent": {"first_name": "Wrong"}},
            )
        ).status_code == 422

        async def add(name: str) -> Response:
            return await client.post(
                "/api/v1/admin/students",
                json={"first_name": name, "group_id": str(first.id), "parent_id": str(parent_id)},
            )

        responses = await asyncio.gather(add("Namuna yangi A"), add("Namuna yangi B"))
        assert all(response.status_code == 201 for response in responses)
    async with model_database.session() as session:
        assert await session.scalar(select(func.count()).select_from(Parent)) == 2
        assert (
            await session.scalar(
                select(func.count()).select_from(Student).where(Student.parent_id == parent_id)
            )
            == 4
        )
        events = (
            await session.scalars(
                select(AuditEvent).where(
                    AuditEvent.actor_id == editor.staff_id, AuditEvent.action == "student.update"
                )
            )
        ).all()
        assert any(
            event.body["changes"].get("parent_id", {}).get("after", {}).get("id") == str(parent_id)
            for event in events
        )
        session.add(SystemSettings(id=1, bot_username="namuna_bot"))
        await session.commit()
    async with client_for(editor) as client:
        link = (await client.post(f"/api/v1/admin/students/{pupil_id}/parent/telegram-link")).json()
        other = (await client.get(f"/api/v1/admin/students/{other_id}")).json()
        assert other["parent"]["telegram_link"]["deep_link"] == link["deep_link"]
        assert other["parent"]["child_count"] == 4


async def test_one_parent_telegram_gets_each_child_and_old_guardian_queue_is_skipped(
    model_database: Database, attendance_clock: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    (
        first_teacher,
        first,
        second_teacher,
        second,
        pupil_id,
        other_id,
    ) = await setup_two_teachers_with_classes(model_database)
    editor = await actor(model_database, permissions=["students:edit"])

    async def no_dispatch(*args: object, **kwargs: object) -> None:
        pass

    monkeypatch.setattr(attendance, "dispatch_pending_outbox_stub", no_dispatch)
    async with model_database.session() as session:
        pupil = await session.get(Student, pupil_id)
        other = await session.get(Student, other_id)
        assert pupil is not None and pupil.parent_id is not None and other is not None
        parent_id, former_parent_id = pupil.parent_id, other.parent_id
        guardian = await session.get(Parent, parent_id)
        assert guardian is not None
        guardian.telegram_id = 123456789
        await session.commit()
    async with client_for(editor) as client:
        assert (
            await client.patch(
                f"/api/v1/admin/students/{other_id}", json={"parent_id": str(parent_id)}
            )
        ).status_code == 200
    for teacher, group, child, status in [
        (first_teacher, first, pupil_id, "present"),
        (second_teacher, second, other_id, "absent"),
    ]:
        async with client_for(teacher) as client:
            response = await client.post(
                f"/api/v1/teacher/groups/{group.id}/attendance/finalize",
                json={
                    "date": "2026-10-05",
                    "items": [{"student_id": str(child), "status": status}],
                },
            )
            assert response.status_code == 200, response.text
    sender = CapturingSender()
    assert await dispatch_pending_outbox(model_database, sender=sender) == 2
    assert [chat for chat, _ in sender.sent] == [123456789, 123456789]
    assert any("Ali Aliyev" in message for _, message in sender.sent)
    assert any("Vali Valiyev" in message for _, message in sender.sent)
    assert await dispatch_pending_outbox(model_database, sender=sender) == 0
    async with model_database.session() as session:
        item = await session.scalar(select(NotificationOutbox).limit(1))
        assert item is not None
        item.status = OutboxStatus.PENDING
        item.available_at = datetime.now(UTC)
        item.idempotency_key = f"namuna_{uuid.uuid4()}"
        pupil = await session.get(Student, pupil_id)
        assert pupil is not None
        # Both messages now have a former guardian even if their snapshot chat ID remains.
        await session.execute(update(Student).values(parent_id=former_parent_id))
        await session.commit()
    assert await dispatch_pending_outbox(model_database, sender=sender) == 0
    assert len(sender.sent) == 2
    async with model_database.session() as session:
        skipped = await session.scalar(
            select(NotificationOutbox).where(NotificationOutbox.status == OutboxStatus.SKIPPED)
        )
        assert skipped is not None and skipped.last_error == "Ota-ona biriktirishi o‘zgargan"
