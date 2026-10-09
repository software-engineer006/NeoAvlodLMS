from datetime import date

import pytest
from factories import group
from sqlalchemy import func, select
from test_rbac import actor, client_for

from neoavlod.database import Database
from neoavlod.models import NotificationOutbox, Role, Staff, Student, Subject

pytestmark = pytest.mark.anyio


async def test_partial_roster_is_visible_and_finalizes_without_fictional_parent(
    model_database: Database,
) -> None:
    admin = await actor(model_database, role=Role.SUPERADMIN)
    teacher = await actor(model_database, role=Role.TEACHER, phone=None, last_name=None)
    other = await actor(model_database, role=Role.TEACHER)
    async with model_database.session() as session:
        subject = Subject(name="Partial profile subject")
        session.add(subject)
        await session.flush()
        grp = group(
            subject_id=subject.id,
            teacher_id=teacher.staff_id,
            monthly_price=None,
            room_number=None,
            start_time=None,
            end_time=None,
        )
        session.add(grp)
        await session.flush()
        learner = Student(
            first_name="Original Full Name",
            last_name=None,
            phone=None,
            age=None,
            parent_id=None,
            group_id=grp.id,
            school_grade="7-sinf",
            source_key="fixture:1",
            source_data={"notes": ["Source note"]},
        )
        session.add(learner)
        await session.commit()
        gid, sid = str(grp.id), str(learner.id)
    async with client_for(admin) as client:
        res = await client.get("/api/v1/admin/students", params={"q": "Original"})
        assert res.status_code == 200
        assert res.json()["total"] == 1
        item = res.json()["items"][0]
        assert item["parent"] is None and item["age"] is None and item["phone"] is None
        assert item["school_grade"] == "7-sinf"
        detail = (await client.get(f"/api/v1/admin/students/{sid}")).json()
        assert detail["import_notes"] == ["Source note"]
        assert detail["group"]["monthly_price"] is None
        assert (
            await client.post(f"/api/v1/admin/students/{sid}/parent/telegram-link")
        ).status_code == 409
    async with client_for(other) as client:
        assert (await client.get(f"/api/v1/teacher/students/{sid}")).status_code == 404
    async with client_for(teacher) as client:
        assert (await client.get("/api/v1/auth/teacher/me")).json()["phone"] is None
        assert (await client.get(f"/api/v1/teacher/students/{sid}")).json()["parent"] is None
        response = await client.post(
            f"/api/v1/teacher/groups/{gid}/attendance/finalize",
            json={
                "date": date.today().isoformat(),
                "items": [{"student_id": sid, "status": "present"}],
            },
        )
        assert response.status_code == 200, response.text
        history = await client.get(
            f"/api/v1/teacher/groups/{gid}/attendance/history",
            params={"month": date.today().strftime("%Y-%m")},
        )
        assert history.status_code == 200
        assert history.json()["records"][0]["student_name"] == "Original Full Name"
    async with model_database.session() as session:
        assert await session.scalar(select(func.count()).select_from(NotificationOutbox)) == 0
        assert (await session.get(Staff, teacher.staff_id)) is not None


async def test_api_creates_partial_student_and_later_adds_real_parent(
    model_database: Database,
) -> None:
    admin = await actor(model_database, role=Role.SUPERADMIN)
    teacher = await actor(model_database, role=Role.TEACHER)
    async with model_database.session() as session:
        subject = Subject(name="Real profile subject")
        session.add(subject)
        await session.flush()
        grp = group(subject_id=subject.id, teacher_id=teacher.staff_id)
        session.add(grp)
        await session.commit()
        gid = str(grp.id)
    async with client_for(admin) as client:
        created = await client.post(
            "/api/v1/admin/students", json={"first_name": "Source Name", "group_id": gid}
        )
        assert created.status_code == 201, created.text
        sid = created.json()["id"]
        updated = await client.patch(
            f"/api/v1/admin/students/{sid}",
            json={
                "parent": {"first_name": "Actual", "last_name": "Parent", "phone": "+998901111234"}
            },
        )
        assert updated.status_code == 200, updated.text
        assert updated.json()["parent"]["phone"] == "+998901111234"
