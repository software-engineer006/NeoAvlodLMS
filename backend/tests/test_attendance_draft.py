import uuid
from datetime import date, time
from decimal import Decimal

import pytest
from factories import parent, student
from test_rbac import Actor, actor, client_for

from neoavlod.database import Database
from neoavlod.models import Attendance, AttendanceBatch, Group, Role, Subject
from neoavlod.models.common import Status

pytestmark = pytest.mark.anyio
BASE = "/api/v1/teacher/groups"


async def setup_teacher_and_class(
    database: Database,
) -> tuple[Actor, Group, list[uuid.UUID]]:
    teach_actor = await actor(database, role=Role.TEACHER)
    async with database.session() as session:
        sub = Subject(name=f"Fan_{uuid.uuid4().hex[:8]}")
        session.add(sub)
        await session.flush()

        grp = Group(
            name="Matematika Guruh",
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

        p1 = parent(first_name="Ota1", phone="+998901111111")
        p2 = parent(first_name="Ota2", phone="+998902222222")
        session.add_all([p1, p2])
        await session.flush()

        s1 = student(grp.id, p1.id, first_name="Ali")
        s2 = student(grp.id, p2.id, first_name="Vali")
        session.add_all([s1, s2])
        await session.commit()
        return teach_actor, grp, [s1.id, s2.id]


async def test_teacher_only_attendance_draft_security(model_database: Database) -> None:
    teach_actor, grp, st_ids = await setup_teacher_and_class(model_database)
    other_teacher = await actor(model_database, role=Role.TEACHER)
    admin_actor = await actor(model_database, role=Role.ADMIN, permissions=["attendance:read"])
    super_actor = await actor(model_database, role=Role.SUPERADMIN)

    payload = {
        "date": "2026-10-05",
        "items": [
            {"student_id": str(st_ids[0]), "status": "present", "note": "Darsda"},
        ],
    }

    # Admin and superadmin cannot write attendance drafts (teacher portal only)
    async with client_for(admin_actor) as client:
        res = await client.post(f"{BASE}/{grp.id}/attendance/draft", json=payload)
        assert res.status_code == 403

    async with client_for(super_actor) as client:
        res = await client.post(f"{BASE}/{grp.id}/attendance/draft", json=payload)
        assert res.status_code == 403

    # Foreign teacher cannot write attendance for another teacher's group -> 404
    async with client_for(other_teacher) as client:
        res = await client.post(f"{BASE}/{grp.id}/attendance/draft", json=payload)
        assert res.status_code == 404
        assert "Guruh topilmadi" in res.json()["detail"]

    # Own teacher can write
    async with client_for(teach_actor) as client:
        res = await client.post(f"{BASE}/{grp.id}/attendance/draft", json=payload)
        assert res.status_code == 200
        sheet = res.json()
        assert sheet["group_id"] == str(grp.id)
        assert sheet["finalized"] is False
        assert len(sheet["items"]) == 2  # Both active students listed


async def test_draft_validation_statuses_notes_and_foreign_students(
    model_database: Database,
) -> None:
    teach_actor, grp, st_ids = await setup_teacher_and_class(model_database)

    # Create a foreign student in another group
    foreign_teacher = await actor(model_database, role=Role.TEACHER)
    async with model_database.session() as session:
        sub = Subject(name=f"Fan_{uuid.uuid4().hex[:8]}")
        session.add(sub)
        await session.flush()
        foreign_grp = Group(
            name="Boshqa guruh",
            subject_id=sub.id,
            teacher_id=foreign_teacher.staff_id,
            monthly_price=Decimal("400000.00"),
            max_students=10,
            days_of_week=[1, 3],
            start_time=time(14, 0),
            end_time=time(15, 30),
            room_number="102",
        )
        session.add(foreign_grp)
        await session.flush()
        p = parent(phone="+998909999999")
        session.add(p)
        await session.flush()
        foreign_st = student(foreign_grp.id, p.id, first_name="Begona")
        session.add(foreign_st)
        await session.commit()
        foreign_st_id = foreign_st.id

    async with client_for(teach_actor) as client:
        # Invalid status
        bad_status = {
            "date": "2026-10-05",
            "items": [{"student_id": str(st_ids[0]), "status": "here"}],
        }
        res_bad_status = await client.post(f"{BASE}/{grp.id}/attendance/draft", json=bad_status)
        assert res_bad_status.status_code == 422

        # Note too long (>2000 chars)
        bad_note = {
            "date": "2026-10-05",
            "items": [{"student_id": str(st_ids[0]), "status": "present", "note": "x" * 2001}],
        }
        res_bad_note = await client.post(f"{BASE}/{grp.id}/attendance/draft", json=bad_note)
        assert res_bad_note.status_code == 422

        # Foreign student from another group -> 422
        foreign_payload = {
            "date": "2026-10-05",
            "items": [{"student_id": str(foreign_st_id), "status": "present"}],
        }
        foreign_res = await client.post(f"{BASE}/{grp.id}/attendance/draft", json=foreign_payload)
        assert foreign_res.status_code == 422
        assert "tegishli emas" in foreign_res.json()["detail"]

        # Valid statuses present, absent, late
        for valid_status in ("present", "absent", "late"):
            ok_res = await client.post(
                f"{BASE}/{grp.id}/attendance/draft",
                json={
                    "date": "2026-10-05",
                    "items": [{"student_id": str(st_ids[0]), "status": valid_status}],
                },
            )
            assert ok_res.status_code == 200


async def test_unique_upsert_and_finalized_date_rejection(
    model_database: Database,
) -> None:
    teach_actor, grp, st_ids = await setup_teacher_and_class(model_database)
    d = "2026-10-05"

    async with client_for(teach_actor) as client:
        # 1. First upsert: student 0 present, student 1 absent
        res1 = await client.post(
            f"{BASE}/{grp.id}/attendance/draft",
            json={
                "date": d,
                "items": [
                    {"student_id": str(st_ids[0]), "status": "present", "note": "Darsda"},
                    {"student_id": str(st_ids[1]), "status": "absent", "note": "Kasal"},
                ],
            },
        )
        assert res1.status_code == 200

        # Verify DB records
        async with model_database.session() as session:
            rows = (
                await session.scalars(
                    Attendance.__table__.select().where(
                        Attendance.group_id == grp.id,
                        Attendance.date == date(2026, 10, 5),
                    )
                )
            ).all()
            assert len(rows) == 2

        # 2. Second upsert: update student 0 to late with new note, student 1 to present
        res2 = await client.post(
            f"{BASE}/{grp.id}/attendance/draft",
            json={
                "date": d,
                "items": [
                    {"student_id": str(st_ids[0]), "status": "late", "note": "10 daqiqa kechikdi"},
                    {"student_id": str(st_ids[1]), "status": "present", "note": None},
                ],
            },
        )
        assert res2.status_code == 200
        sheet2 = res2.json()
        item0 = next(i for i in sheet2["items"] if i["student_id"] == str(st_ids[0]))
        assert item0["status"] == "late"
        assert item0["note"] == "10 daqiqa kechikdi"

        # Check total rows in DB remains 2 (upsert, not duplicate insert)
        async with model_database.session() as session:
            rows2 = (
                await session.scalars(
                    Attendance.__table__.select().where(
                        Attendance.group_id == grp.id,
                        Attendance.date == date(2026, 10, 5),
                    )
                )
            ).all()
            assert len(rows2) == 2

        # 3. Simulate finalization for this date
        async with model_database.session() as session:
            batch = AttendanceBatch(
                group_id=grp.id,
                date=date(2026, 10, 5),
                finalized_by=teach_actor.staff_id,
            )
            session.add(batch)
            await session.commit()

        # 4. Attempt to write draft for finalized date -> 409
        finalized_attempt = await client.post(
            f"{BASE}/{grp.id}/attendance/draft",
            json={
                "date": d,
                "items": [{"student_id": str(st_ids[0]), "status": "absent"}],
            },
        )
        assert finalized_attempt.status_code == 409
        assert "allaqachon yakunlangan" in finalized_attempt.json()["detail"]

        # Check attendance sheet shows finalized=True
        get_res = await client.get(f"{BASE}/{grp.id}/attendance", params={"date": d})
        assert get_res.status_code == 200
        assert get_res.json()["finalized"] is True
