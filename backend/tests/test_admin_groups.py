import uuid
from datetime import date

import pytest
from factories import parent, student
from test_rbac import actor, client_for

from neoavlod.database import Database
from neoavlod.models import Attendance, AttendanceStatus, Role, Staff, Subject
from neoavlod.models.common import Status

pytestmark = pytest.mark.anyio
BASE = "/api/v1/admin/groups"


async def setup_subject_and_teacher(database: Database) -> tuple[Subject, Staff]:
    async with database.session() as session:
        sub = Subject(name=f"Fan_{uuid.uuid4().hex[:8]}")
        teach = Staff(
            first_name="Ustoz",
            last_name="Muallim",
            phone=f"+99890{uuid.uuid4().int % 10**7:07d}",
            username=f"teach_{uuid.uuid4().hex[:8]}",
            hashed_password="$argon2id$encoded-test-password",
            role=Role.TEACHER,
            status=Status.ACTIVE,
        )
        session.add_all([sub, teach])
        await session.commit()
        return sub, teach


async def test_group_permissions_and_role_access(model_database: Database) -> None:
    sub, teach = await setup_subject_and_teacher(model_database)
    reader = await actor(model_database, permissions=["groups:read"])
    creator = await actor(model_database, permissions=["groups:create"])
    editor = await actor(model_database, permissions=["groups:edit"])
    teacher_actor = await actor(model_database, role=Role.TEACHER)
    super_actor = await actor(model_database, role=Role.SUPERADMIN)

    group_payload = {
        "name": "Matematika 1",
        "subject_id": str(sub.id),
        "teacher_id": str(teach.id),
        "monthly_price": "500000.00",
        "max_students": 25,
        "days_of_week": [1, 3, 5],
        "start_time": "09:00:00",
        "end_time": "10:30:00",
        "room_number": "101",
    }

    # Teacher gets 403 everywhere on admin group endpoints
    async with client_for(teacher_actor) as client:
        assert (await client.get(BASE)).status_code == 403
        assert (await client.post(BASE, json=group_payload)).status_code == 403
        assert (await client.get(f"{BASE}/{uuid.uuid4()}")).status_code == 403
        assert (await client.patch(f"{BASE}/{uuid.uuid4()}", json={"name": "X"})).status_code == 403

    # Reader can list and get, but cannot create, patch, or delete
    async with client_for(reader) as client:
        assert (await client.get(BASE)).status_code == 200
        assert (await client.post(BASE, json=group_payload)).status_code == 403
        assert (await client.patch(f"{BASE}/{uuid.uuid4()}", json={"name": "X"})).status_code == 403
        assert (await client.delete(f"{BASE}/{uuid.uuid4()}")).status_code == 403

    # Creator can create, but cannot list or edit
    async with client_for(creator) as client:
        assert (await client.get(BASE)).status_code == 403
        create_resp = await client.post(BASE, json=group_payload)
        assert create_resp.status_code == 201
        created_id = create_resp.json()["id"]
        assert (await client.patch(f"{BASE}/{created_id}", json={"name": "X"})).status_code == 403

    # Editor can edit, deactivate, activate, delete, but cannot list or create
    async with client_for(editor) as client:
        assert (await client.get(BASE)).status_code == 403
        assert (await client.post(BASE, json=group_payload)).status_code == 403
        patch_resp = await client.patch(f"{BASE}/{created_id}", json={"name": "Matematika Yangi"})
        assert patch_resp.status_code == 200
        assert patch_resp.json()["name"] == "Matematika Yangi"

    # Superadmin has access to everything
    async with client_for(super_actor) as client:
        assert (await client.get(BASE)).status_code == 200
        assert (await client.get(f"{BASE}/{created_id}")).status_code == 200


async def test_teacher_and_subject_compatibility(model_database: Database) -> None:
    sub, teach = await setup_subject_and_teacher(model_database)
    super_actor = await actor(model_database, role=Role.SUPERADMIN)

    # Inactive subject and inactive teacher
    async with model_database.session() as session:
        inactive_sub = Subject(name="Inaktiv fan", is_active=False)
        inactive_teach = Staff(
            first_name="Nofaol",
            last_name="Ustoz",
            phone="+998901239999",
            username="nofaol_ustoz",
            hashed_password="$argon2id$encoded-test-password",
            role=Role.TEACHER,
            status=Status.INACTIVE,
        )
        admin_staff = Staff(
            first_name="Admin",
            last_name="Xodim",
            phone="+998901238888",
            username="admin_xodim",
            hashed_password="$argon2id$encoded-test-password",
            role=Role.ADMIN,
            status=Status.ACTIVE,
        )
        session.add_all([inactive_sub, inactive_teach, admin_staff])
        await session.commit()
        inactive_sub_id = inactive_sub.id
        inactive_teach_id = inactive_teach.id
        admin_staff_id = admin_staff.id

    valid_payload = {
        "name": "Fizika A",
        "subject_id": str(sub.id),
        "teacher_id": str(teach.id),
        "monthly_price": "400000.00",
        "max_students": 20,
        "days_of_week": [2, 4, 6],
        "start_time": "14:00:00",
        "end_time": "15:30:00",
        "room_number": "202",
    }

    async with client_for(super_actor) as client:
        # Non-existent subject -> 404
        bad_sub = dict(valid_payload, subject_id=str(uuid.uuid4()))
        res = await client.post(BASE, json=bad_sub)
        assert res.status_code == 404 and "Fan topilmadi" in res.json()["detail"]

        # Inactive subject -> 409
        bad_sub_inactive = dict(valid_payload, subject_id=str(inactive_sub_id))
        res = await client.post(BASE, json=bad_sub_inactive)
        assert res.status_code == 409 and "faol emas" in res.json()["detail"]

        # Non-existent teacher -> 404
        bad_teach = dict(valid_payload, teacher_id=str(uuid.uuid4()))
        res = await client.post(BASE, json=bad_teach)
        assert res.status_code == 404 and "O‘qituvchi topilmadi" in res.json()["detail"]

        # Staff with non-teacher role -> 422
        bad_teach_role = dict(valid_payload, teacher_id=str(admin_staff_id))
        res = await client.post(BASE, json=bad_teach_role)
        assert res.status_code == 422 and "o‘qituvchi roliga ega emas" in res.json()["detail"]

        # Inactive teacher -> 409
        bad_teach_inactive = dict(valid_payload, teacher_id=str(inactive_teach_id))
        res = await client.post(BASE, json=bad_teach_inactive)
        assert res.status_code == 409 and "faol emas" in res.json()["detail"]

        # Successfully create group
        created = (await client.post(BASE, json=valid_payload)).json()
        group_id = created["id"]

        # Update checks
        # Change to inactive subject -> 409
        assert (
            await client.patch(f"{BASE}/{group_id}", json={"subject_id": str(inactive_sub_id)})
        ).status_code == 409

        # Change to non-teacher staff -> 422
        assert (
            await client.patch(f"{BASE}/{group_id}", json={"teacher_id": str(admin_staff_id)})
        ).status_code == 422

        # Change to inactive teacher -> 409
        assert (
            await client.patch(f"{BASE}/{group_id}", json={"teacher_id": str(inactive_teach_id)})
        ).status_code == 409

        # Deactivate group
        deact = await client.post(f"{BASE}/{group_id}/deactivate")
        assert deact.status_code == 200 and deact.json()["status"] == "inactive"

        # Now deactivate the teacher in DB
        async with model_database.session() as session:
            t = await session.get(Staff, teach.id)
            assert t
            t.status = Status.INACTIVE
            await session.commit()

        # Activating group should now fail because teacher is inactive -> 409
        act_blocked = await client.post(f"{BASE}/{group_id}/activate")
        assert act_blocked.status_code == 409
        assert "O‘qituvchi faol emas" in act_blocked.json()["detail"]


async def test_schedule_days_time_price_capacity_validation(model_database: Database) -> None:
    sub, teach = await setup_subject_and_teacher(model_database)
    super_actor = await actor(model_database, role=Role.SUPERADMIN)

    base_payload = {
        "name": "Ingliz tili B1",
        "subject_id": str(sub.id),
        "teacher_id": str(teach.id),
        "monthly_price": "600000.00",
        "max_students": 15,
        "days_of_week": [1, 3, 5],
        "start_time": "10:00:00",
        "end_time": "11:30:00",
        "room_number": "301",
    }

    async with client_for(super_actor) as client:
        # Invalid days_of_week
        for bad_days in ([], [0], [8], [1, 1, 3], [1, 2, 3, 4, 5, 6, 7, 1]):
            assert (
                await client.post(BASE, json=dict(base_payload, days_of_week=bad_days))
            ).status_code == 422

        # Invalid time order (start >= end)
        assert (
            await client.post(
                BASE,
                json=dict(base_payload, start_time="11:30:00", end_time="10:00:00"),
            )
        ).status_code == 422
        assert (
            await client.post(
                BASE,
                json=dict(base_payload, start_time="10:00:00", end_time="10:00:00"),
            )
        ).status_code == 422

        # Invalid price
        assert (
            await client.post(BASE, json=dict(base_payload, monthly_price="-100.00"))
        ).status_code == 422

        # Invalid capacity
        for bad_cap in (0, -5, 1001):
            assert (
                await client.post(BASE, json=dict(base_payload, max_students=bad_cap))
            ).status_code == 422

        # Invalid name / room
        for bad_str in ("", "   "):
            assert (
                await client.post(BASE, json=dict(base_payload, name=bad_str))
            ).status_code == 422
            assert (
                await client.post(BASE, json=dict(base_payload, room_number=bad_str))
            ).status_code == 422

        # Successful create
        created = await client.post(BASE, json=base_payload)
        assert created.status_code == 201
        data = created.json()
        assert data["name"] == "Ingliz tili B1"
        assert data["days_of_week"] == [1, 3, 5]
        assert data["monthly_price"] == "600000.00"
        assert data["current_students"] == 0
        group_id = data["id"]

        # Updating start_time to after existing end_time (11:30)
        assert (
            await client.patch(f"{BASE}/{group_id}", json={"start_time": "12:00:00"})
        ).status_code == 422

        # Updating end_time to before existing start_time (10:00)
        assert (
            await client.patch(f"{BASE}/{group_id}", json={"end_time": "09:00:00"})
        ).status_code == 422

        # Valid time update
        time_update = await client.patch(
            f"{BASE}/{group_id}",
            json={"start_time": "11:00:00", "end_time": "12:30:00"},
        )
        assert time_update.status_code == 200
        assert "11:00" in time_update.json()["start_time"]
        assert "12:30" in time_update.json()["end_time"]


async def test_capacity_reduction_below_active_students_is_rejected(
    model_database: Database,
) -> None:
    sub, teach = await setup_subject_and_teacher(model_database)
    super_actor = await actor(model_database, role=Role.SUPERADMIN)

    async with client_for(super_actor) as client:
        created = (
            await client.post(
                BASE,
                json={
                    "name": "Robototexnika",
                    "subject_id": str(sub.id),
                    "teacher_id": str(teach.id),
                    "monthly_price": "700000.00",
                    "max_students": 10,
                    "days_of_week": [1, 3],
                    "start_time": "15:00:00",
                    "end_time": "17:00:00",
                    "room_number": "104",
                },
            )
        ).json()
        group_id = uuid.UUID(created["id"])

        # Enroll 3 students into this group (2 active, 1 inactive)
        async with model_database.session() as session:
            p1 = parent(phone="+998901111111")
            p2 = parent(phone="+998902222222")
            p3 = parent(phone="+998903333333")
            session.add_all([p1, p2, p3])
            await session.flush()
            s1 = student(group_id, p1.id, status=Status.ACTIVE)
            s2 = student(group_id, p2.id, status=Status.ACTIVE)
            s3 = student(group_id, p3.id, status=Status.INACTIVE)
            session.add_all([s1, s2, s3])
            await session.commit()

        # Check detail returns 2 current active students
        detail = (await client.get(f"{BASE}/{group_id}")).json()
        assert detail["current_students"] == 2
        assert detail["max_students"] == 10

        # Attempt to reduce capacity below active students (1 < 2) -> 409
        bad_reduce = await client.patch(f"{BASE}/{group_id}", json={"max_students": 1})
        assert bad_reduce.status_code == 409
        assert "2" in bad_reduce.json()["detail"] and "1" in bad_reduce.json()["detail"]

        # Reduce capacity exactly to active students (2 >= 2) -> 200
        ok_reduce = await client.patch(f"{BASE}/{group_id}", json={"max_students": 2})
        assert ok_reduce.status_code == 200
        assert ok_reduce.json()["max_students"] == 2


async def test_group_deletion_and_filtering(model_database: Database) -> None:
    sub, teach = await setup_subject_and_teacher(model_database)
    super_actor = await actor(model_database, role=Role.SUPERADMIN)

    async with client_for(super_actor) as client:
        # Create 2 groups
        g1 = (
            await client.post(
                BASE,
                json={
                    "name": "Guruh A",
                    "subject_id": str(sub.id),
                    "teacher_id": str(teach.id),
                    "monthly_price": "300000.00",
                    "max_students": 10,
                    "days_of_week": [1, 3],
                    "start_time": "08:00:00",
                    "end_time": "09:30:00",
                    "room_number": "R1",
                },
            )
        ).json()
        g2 = (
            await client.post(
                BASE,
                json={
                    "name": "Guruh B",
                    "subject_id": str(sub.id),
                    "teacher_id": str(teach.id),
                    "monthly_price": "350000.00",
                    "max_students": 12,
                    "days_of_week": [2, 4],
                    "start_time": "10:00:00",
                    "end_time": "11:30:00",
                    "room_number": "R2",
                },
            )
        ).json()

        # Add a student to g1
        async with model_database.session() as session:
            p = parent(phone="+998909876543")
            session.add(p)
            await session.flush()
            s = student(uuid.UUID(g1["id"]), p.id)
            session.add(s)
            await session.commit()

        # Trying to delete g1 (has students) -> 409
        del_g1 = await client.delete(f"{BASE}/{g1['id']}")
        assert del_g1.status_code == 409
        assert "Talabalar bog‘langan" in del_g1.json()["detail"]

        # Deleting g2 (empty) -> 204
        del_g2 = await client.delete(f"{BASE}/{g2['id']}")
        assert del_g2.status_code == 204
        assert (await client.get(f"{BASE}/{g2['id']}")).status_code == 404

        # Test attendance blocking deletion
        g3 = (
            await client.post(
                BASE,
                json={
                    "name": "Guruh C",
                    "subject_id": str(sub.id),
                    "teacher_id": str(teach.id),
                    "monthly_price": "350000.00",
                    "max_students": 12,
                    "days_of_week": [5],
                    "start_time": "14:00:00",
                    "end_time": "15:30:00",
                    "room_number": "R3",
                },
            )
        ).json()
        g3_id = uuid.UUID(g3["id"])

        async with model_database.session() as session:
            att = Attendance(
                group_id=g3_id,
                student_id=s.id,
                date=date(2026, 10, 5),
                status=AttendanceStatus.PRESENT,
                marked_by=teach.id,
            )
            session.add(att)
            await session.commit()

        del_g3 = await client.delete(f"{BASE}/{g3_id}")
        assert del_g3.status_code == 409
        assert "Davomat" in del_g3.json()["detail"]

        # Filter tests
        list_all = (await client.get(BASE)).json()
        assert list_all["total"] >= 2

        # Filter by search
        q_res = (await client.get(BASE, params={"q": "Guruh A"})).json()
        assert q_res["total"] == 1
        assert q_res["items"][0]["name"] == "Guruh A"

        # Filter by day_of_week
        day_res = (await client.get(BASE, params={"day_of_week": 1})).json()
        for item in day_res["items"]:
            assert 1 in item["days_of_week"]

        # Filter by status
        await client.post(f"{BASE}/{g1['id']}/deactivate")
        inactive_res = (await client.get(BASE, params={"status": "inactive"})).json()
        assert any(i["id"] == g1["id"] for i in inactive_res["items"])
