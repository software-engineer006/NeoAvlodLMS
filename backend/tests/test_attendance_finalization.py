import uuid
from datetime import date, time
from decimal import Decimal

import pytest
from factories import parent, student
from sqlalchemy import select
from test_rbac import Actor, actor, client_for

from neoavlod.database import Database
from neoavlod.models import (
    AttendanceBatch,
    Group,
    NotificationOutbox,
    Role,
    Subject,
)
from neoavlod.models.common import Status

pytestmark = pytest.mark.anyio
TEACHER_BASE = "/api/v1/teacher/groups"
ADMIN_BASE = "/api/v1/admin/attendance"


async def setup_class_with_students(
    database: Database,
) -> tuple[Actor, Group, list[uuid.UUID]]:
    teach_actor = await actor(database, role=Role.TEACHER)
    async with database.session() as session:
        sub = Subject(name=f"Fan_{uuid.uuid4().hex[:8]}")
        session.add(sub)
        await session.flush()

        grp = Group(
            name="Matematika Final Guruh",
            subject_id=sub.id,
            teacher_id=teach_actor.staff_id,
            monthly_price=Decimal("400000.00"),
            max_students=10,
            days_of_week=[1, 3, 5],
            start_time=time(9, 0),
            end_time=time(10, 30),
            room_number="101",
            status=Status.ACTIVE,
        )
        session.add(grp)
        await session.flush()

        p1 = parent(first_name="Ota1", phone="+998901111111", telegram_id=12345678)
        p2 = parent(first_name="Ota2", phone="+998902222222")  # telegram_id None
        session.add_all([p1, p2])
        await session.flush()

        s1 = student(grp.id, p1.id, first_name="Ali")
        s2 = student(grp.id, p2.id, first_name="Vali")
        session.add_all([s1, s2])
        await session.commit()
        return teach_actor, grp, [s1.id, s2.id]


async def test_all_active_students_required_for_finalization(
    model_database: Database,
) -> None:
    teach_actor, grp, st_ids = await setup_class_with_students(model_database)
    d = "2026-10-05"

    async with client_for(teach_actor) as client:
        # Mark only 1 student out of 2 active students
        await client.post(
            f"{TEACHER_BASE}/{grp.id}/attendance/draft",
            json={
                "date": d,
                "items": [{"student_id": str(st_ids[0]), "status": "present"}],
            },
        )

        # Attempt to finalize without marking student 2 -> 422
        bad_final = await client.post(
            f"{TEACHER_BASE}/{grp.id}/attendance/finalize",
            json={"date": d},
        )
        assert bad_final.status_code == 422
        assert "Barcha faol talabalar" in bad_final.json()["detail"]

        # Finalize by providing student 2 in the finalize payload -> 200
        ok_final = await client.post(
            f"{TEACHER_BASE}/{grp.id}/attendance/finalize",
            json={
                "date": d,
                "items": [{"student_id": str(st_ids[1]), "status": "late", "note": "Kechikdi"}],
            },
        )
        assert ok_final.status_code == 200
        sheet = ok_final.json()
        assert sheet["finalized"] is True
        assert sheet["finalized_at"] is not None


async def test_idempotent_finalization_and_outbox_creation(
    model_database: Database,
) -> None:
    teach_actor, grp, st_ids = await setup_class_with_students(model_database)
    d = "2026-10-05"

    async with client_for(teach_actor) as client:
        # Finalize with both students
        res = await client.post(
            f"{TEACHER_BASE}/{grp.id}/attendance/finalize",
            json={
                "date": d,
                "items": [
                    {"student_id": str(st_ids[0]), "status": "present"},
                    {"student_id": str(st_ids[1]), "status": "absent", "note": "Kasal"},
                ],
            },
        )
        assert res.status_code == 200
        assert res.json()["finalized"] is True

        # Check DB for AttendanceBatch and NotificationOutbox
        async with model_database.session() as session:
            batches = (
                await session.scalars(
                    select(AttendanceBatch).where(
                        AttendanceBatch.group_id == grp.id,
                        AttendanceBatch.date == date(2026, 10, 5),
                    )
                )
            ).all()
            assert len(batches) == 1

            outbox = list((await session.scalars(select(NotificationOutbox))).all())
            assert len(outbox) == 2
            # Student 1's parent has telegram_id -> pending
            s1_outbox = next(o for o in outbox if o.telegram_id == 12345678)
            assert s1_outbox.status == "pending"
            assert "Ali" in str(s1_outbox.payload)

            # Student 2's parent has no telegram_id -> skipped
            s2_outbox = next(o for o in outbox if o.telegram_id is None)
            assert s2_outbox.status == "skipped"

        # Idempotent call: finalize again -> returns 200, no duplicates created
        repeat_res = await client.post(
            f"{TEACHER_BASE}/{grp.id}/attendance/finalize",
            json={"date": d},
        )
        assert repeat_res.status_code == 200
        assert repeat_res.json()["finalized"] is True

        # Verify DB still has exactly 1 batch and 2 outbox items
        async with model_database.session() as session:
            batches2 = (
                await session.scalars(
                    select(AttendanceBatch).where(
                        AttendanceBatch.group_id == grp.id,
                        AttendanceBatch.date == date(2026, 10, 5),
                    )
                )
            ).all()
            assert len(batches2) == 1

            outbox2 = (await session.scalars(select(NotificationOutbox))).all()
            assert len(outbox2) == 2


async def test_admin_attendance_history_filtering_and_permissions(
    model_database: Database,
) -> None:
    teach_actor, grp, st_ids = await setup_class_with_students(model_database)
    d = "2026-10-05"

    # Finalize attendance
    async with client_for(teach_actor) as client:
        await client.post(
            f"{TEACHER_BASE}/{grp.id}/attendance/finalize",
            json={
                "date": d,
                "items": [
                    {"student_id": str(st_ids[0]), "status": "present"},
                    {"student_id": str(st_ids[1]), "status": "absent", "note": "Kasal"},
                ],
            },
        )

    admin_actor = await actor(model_database, role=Role.ADMIN, permissions=["attendance:read"])
    super_actor = await actor(model_database, role=Role.SUPERADMIN)

    # Teacher gets 403 on admin history route
    async with client_for(teach_actor) as client:
        assert (await client.get(ADMIN_BASE)).status_code == 403

    # Admin with attendance:read gets 200
    async with client_for(admin_actor) as client:
        res = await client.get(ADMIN_BASE)
        assert res.status_code == 200
        data = res.json()
        assert data["total"] >= 2
        items = data["items"]
        assert any(i["group_id"] == str(grp.id) for i in items)

        # Filter by date
        date_res = (await client.get(ADMIN_BASE, params={"date": d})).json()
        assert all(i["date"] == d for i in date_res["items"])

        # Filter by group_id
        grp_res = (await client.get(ADMIN_BASE, params={"group_id": str(grp.id)})).json()
        assert all(i["group_id"] == str(grp.id) for i in grp_res["items"])

        # Filter by status
        pres_res = (await client.get(ADMIN_BASE, params={"status": "present"})).json()
        assert all(i["status"] == "present" for i in pres_res["items"])

        # Filter by teacher_id
        teach_res = (
            await client.get(ADMIN_BASE, params={"teacher_id": str(teach_actor.staff_id)})
        ).json()
        assert all(i["teacher_id"] == str(teach_actor.staff_id) for i in teach_res["items"])

    # Superadmin also has access
    async with client_for(super_actor) as client:
        assert (await client.get(ADMIN_BASE)).status_code == 200
