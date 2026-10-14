import asyncio
import uuid
from typing import Any

import pytest
from sqlalchemy import func, select
from test_attendance_finalization import setup_class_with_students as seed
from test_rbac import actor, client_for

from neoavlod.database import Database
from neoavlod.models import Attendance, AttendanceBatch, AttendanceChange, Role
from neoavlod.services import attendance

pytestmark = [pytest.mark.anyio, pytest.mark.usefixtures("attendance_clock")]


@pytest.fixture(autouse=True)
def disable_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    async def no_dispatch(*args: object) -> None:
        pass

    monkeypatch.setattr(attendance, "dispatch_pending_outbox_stub", no_dispatch)


async def test_shared_teacher_admin_records_reason_history_and_retry(
    model_database: Database,
) -> None:
    teacher, group, students = await seed(model_database)
    admin = await actor(model_database, permissions=["attendance:read", "attendance:write"])
    other = await actor(model_database, role=Role.TEACHER)
    boss = await actor(model_database, role=Role.SUPERADMIN)
    base = f"/api/v1/admin/attendance/groups/{group.id}/attendance"
    teacher_base = f"/api/v1/teacher/groups/{group.id}/attendance"
    payload: dict[str, Any] = {
        "date": "2026-10-05",
        "items": [
            {"student_id": str(students[0]), "status": "present"},
            {"student_id": str(students[1]), "status": "absent"},
        ],
    }
    async with client_for(teacher) as client:
        assert (await client.post(teacher_base + "/draft", json=payload)).status_code == 200
    async with client_for(admin) as client:
        assert (await client.get("/api/v1/admin/attendance/groups")).status_code == 200
        pending = (
            await client.get("/api/v1/admin/attendance/pending", params={"date": "2026-10-05"})
        ).json()
        assert [row["id"] for row in pending] == [str(group.id)]
        assert (
            await client.get("/api/v1/admin/attendance/pending", params={"date": "2026-10-06"})
        ).json() == []
        finalized = await client.post(base + "/finalize", json=payload)
        assert finalized.status_code == 200, finalized.text
        assert finalized.json()["edit_deadline"] is None
        assert (
            await client.get("/api/v1/admin/attendance/pending", params={"date": "2026-10-05"})
        ).json() == []
        correction = {
            "date": "2026-10-05",
            "items": [
                {"student_id": str(students[0]), "status": "late", "note": "  10 daqiqa  "},
            ],
        }
        assert (await client.post(base + "/correct", json=correction)).status_code == 422
        correction["reason"] = "Jurnal aniqlashtirildi"
        responses = await asyncio.gather(
            *[client.post(base + "/correct", json=correction) for _ in range(2)]
        )
        assert all(response.status_code == 200 for response in responses)
        assert (
            await client.get(base + "/changes", params={"date": payload["date"]})
        ).status_code == 403
    async with client_for(boss) as client:
        history = await client.get(base + "/changes", params={"date": payload["date"]})
        assert history.status_code == 200, history.text
        assert history.json()["total"] == 5  # 2 drafts + 2 finalizations + one correction
        change = next(row for row in history.json()["items"] if row["action"] == "correct")
        assert change["actor_id"] == str(admin.staff_id) and change["actor_role"] == "admin"
        assert change["old_status"] == "present" and change["new_status"] == "late"
        assert change["old_note"] is None and change["new_note"] == "10 daqiqa"
        assert change["reason"] == correction["reason"] and change["changed_at"]
        paged = (
            await client.get(
                base + "/changes",
                params={
                    "date": payload["date"],
                    "page_size": 2,
                    "page": 2,
                },
            )
        ).json()
        assert len(paged["items"]) == 2 and paged["total"] == 5
    async with client_for(teacher) as client:
        sheet = (await client.get(teacher_base, params={"date": payload["date"]})).json()
        assert (
            sheet["finalized"]
            and next(row for row in sheet["items"] if row["student_id"] == str(students[0]))[
                "status"
            ]
            == "late"
        )
        assert (
            await client.get(teacher_base + "/changes", params={"date": payload["date"]})
        ).status_code == 403
    async with client_for(other) as client:
        assert (
            await client.get(teacher_base + "/changes", params={"date": payload["date"]})
        ).status_code == 403
        assert (await client.post(base + "/correct", json=correction)).status_code == 403
    async with model_database.session() as session:
        assert await session.scalar(select(func.count()).select_from(Attendance)) == 2
        assert await session.scalar(select(func.count()).select_from(AttendanceBatch)) == 1
        assert await session.scalar(select(func.count()).select_from(AttendanceChange)) == 5


async def test_admin_all_dates_rbac_csrf_validation_and_atomic_audit(
    model_database: Database,
) -> None:
    _, group, students = await seed(model_database)
    reader = await actor(model_database, permissions=["attendance:read"])
    boss = await actor(model_database, role=Role.SUPERADMIN)
    base = f"/api/v1/admin/attendance/groups/{group.id}/attendance"
    payload: dict[str, Any] = {
        "date": "2026-09-01",
        "items": [
            {"student_id": str(students[0]), "status": "present"},
        ],
    }
    async with client_for(reader) as client:
        sheet = await client.get(base, params={"date": payload["date"]})
        assert sheet.status_code == 200 and not sheet.json()["can_edit"]
        for action in ("draft", "finalize", "correct"):
            assert (await client.post(base + "/" + action, json=payload)).status_code == 403
    async with client_for(boss) as client:
        assert (
            await client.post(base + "/draft", json=payload, headers={"X-CSRF-Token": "bad"})
        ).status_code == 403
        assert (
            await client.post(base + "/draft", json={**payload, "date": "2026-10-06"})
        ).status_code == 409
        # An incomplete finalization must roll back both inserted attendance and audit.
        assert (await client.post(base + "/finalize", json=payload)).status_code == 422
        assert (await client.get(base + "/changes", params={"date": payload["date"]})).json()[
            "total"
        ] == 0
        assert (await client.post(base + "/draft", json=payload)).status_code == 200
        updated = {
            **payload,
            "items": [
                {"student_id": str(students[0]), "status": "absent"},
                {"student_id": str(uuid.uuid4()), "status": "present"},
            ],
            "reason": "Tekshiruv",
        }
        assert (await client.post(base + "/draft", json=updated)).status_code == 422
        updated["items"] = updated["items"][:1]
        updated["reason"] = "   "
        assert (await client.post(base + "/draft", json=updated)).status_code == 422
        updated["reason"] = "Sabab"
        assert (await client.post(base + "/draft", json=updated)).status_code == 200
    async with model_database.session() as session:
        assert await session.scalar(select(func.count()).select_from(Attendance)) == 1
        assert await session.scalar(select(func.count()).select_from(AttendanceChange)) == 2


async def test_concurrent_teacher_admin_finalization_is_single_batch(
    model_database: Database,
) -> None:
    teacher, group, students = await seed(model_database)
    boss = await actor(model_database, role=Role.SUPERADMIN)
    payload: dict[str, Any] = {
        "date": "2026-10-05",
        "items": [{"student_id": str(student), "status": "present"} for student in students],
    }
    async with client_for(teacher) as teacher_client, client_for(boss) as admin_client:
        responses = await asyncio.gather(
            teacher_client.post(
                f"/api/v1/teacher/groups/{group.id}/attendance/finalize", json=payload
            ),
            admin_client.post(
                f"/api/v1/admin/attendance/groups/{group.id}/attendance/finalize", json=payload
            ),
        )
        assert all(response.status_code == 200 for response in responses)
    async with model_database.session() as session:
        assert await session.scalar(select(func.count()).select_from(Attendance)) == 2
        assert await session.scalar(select(func.count()).select_from(AttendanceBatch)) == 1
        assert await session.scalar(select(func.count()).select_from(AttendanceChange)) == 4
