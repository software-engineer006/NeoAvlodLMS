import uuid
from datetime import date, time
from decimal import Decimal

import anyio
import pytest
from test_rbac import actor, client_for

from neoavlod.database import Database
from neoavlod.models import (
    Attendance,
    AttendanceStatus,
    Group,
    Parent,
    Role,
    Staff,
    Subject,
    SystemSettings,
)
from neoavlod.models.common import Status

pytestmark = pytest.mark.anyio
BASE = "/api/v1/admin/students"


async def setup_test_group(database: Database, max_students: int = 10) -> Group:
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
        await session.flush()
        grp = Group(
            name=f"Guruh_{uuid.uuid4().hex[:6]}",
            subject_id=sub.id,
            teacher_id=teach.id,
            monthly_price=Decimal("450000.00"),
            max_students=max_students,
            days_of_week=[1, 3, 5],
            start_time=time(9, 0),
            end_time=time(10, 30),
            room_number="101",
            status=Status.ACTIVE,
        )
        # Ensure system settings exist for telegram links
        settings = await session.get(SystemSettings, 1)
        if settings is None:
            settings = SystemSettings(
                id=1,
                bot_username="eduneo_test_bot",
                bot_token_encrypted="dummy_token_str_for_testing_123456",
            )
            session.add(settings)
        else:
            settings.bot_username = "eduneo_test_bot"
            settings.bot_token_encrypted = "dummy_token_str_for_testing_123456"

        session.add(grp)
        await session.commit()
        return grp


async def test_student_permissions_and_role_access(model_database: Database) -> None:
    grp = await setup_test_group(model_database)
    reader = await actor(model_database, permissions=["students:read"])
    creator = await actor(model_database, permissions=["students:create"])
    editor = await actor(model_database, permissions=["students:edit"])
    teacher_actor = await actor(model_database, role=Role.TEACHER)
    super_actor = await actor(model_database, role=Role.SUPERADMIN)

    payload = {
        "first_name": "Ali",
        "last_name": "Valiyev",
        "phone": "+998901234567",
        "age": 14,
        "group_id": str(grp.id),
        "parent": {
            "first_name": "Vali",
            "last_name": "Aliyev",
            "phone": "+998909876543",
        },
    }

    # Teacher gets 403 on admin student routes
    async with client_for(teacher_actor) as client:
        assert (await client.get(BASE)).status_code == 403
        assert (await client.post(BASE, json=payload)).status_code == 403
        assert (await client.get(f"{BASE}/{uuid.uuid4()}")).status_code == 403

    # Reader can list but cannot create or edit
    async with client_for(reader) as client:
        assert (await client.get(BASE)).status_code == 200
        assert (await client.post(BASE, json=payload)).status_code == 403
        assert (await client.patch(f"{BASE}/{uuid.uuid4()}", json={"age": 15})).status_code == 403

    # Creator can create
    async with client_for(creator) as client:
        assert (await client.get(BASE)).status_code == 403
        res = await client.post(BASE, json=payload)
        assert res.status_code == 201
        created_id = res.json()["id"]

    # Editor can edit and delete, but cannot list or create
    async with client_for(editor) as client:
        assert (await client.get(BASE)).status_code == 403
        assert (await client.post(BASE, json=payload)).status_code == 403
        patch_res = await client.patch(f"{BASE}/{created_id}", json={"age": 16})
        assert patch_res.status_code == 200
        assert patch_res.json()["age"] == 16

    # Superadmin has full access
    async with client_for(super_actor) as client:
        assert (await client.get(BASE)).status_code == 200
        assert (await client.get(f"{BASE}/{created_id}")).status_code == 200


async def test_atomic_student_parent_creation_and_deep_links(
    model_database: Database,
) -> None:
    grp = await setup_test_group(model_database)
    super_actor = await actor(model_database, role=Role.SUPERADMIN)

    shared_phone = "+998911112233"
    p1 = {
        "first_name": "Farhod",
        "last_name": "Shokirov",
        "phone": "+998901112233",
        "age": 12,
        "group_id": str(grp.id),
        "parent": {
            "first_name": "Shokir",
            "last_name": "Farhodov",
            "phone": shared_phone,
        },
    }
    p2 = {
        "first_name": "Malika",
        "last_name": "Shokirova",
        "phone": "+998902223344",
        "age": 10,
        "group_id": str(grp.id),
        "parent": {
            "first_name": "Shokir",
            "last_name": "Farhodov",
            "phone": shared_phone,
        },
    }

    async with client_for(super_actor) as client:
        r1 = await client.post(BASE, json=p1)
        assert r1.status_code == 201
        d1 = r1.json()
        assert d1["first_name"] == "Farhod"
        assert d1["parent"]["first_name"] == "Shokir"
        assert d1["parent"]["phone"] == shared_phone
        assert "student_" in d1["telegram_link"]["deep_link"]
        assert "parent_" in d1["parent"]["telegram_link"]["deep_link"]

        # Create second sibling with identical parent phone:
        # DB must NOT silently merge parents, separate Parent row is created
        r2 = await client.post(BASE, json=p2)
        assert r2.status_code == 201
        d2 = r2.json()
        assert d2["parent"]["phone"] == shared_phone
        assert d1["parent"]["id"] != d2["parent"]["id"]

        # Verify in DB that two distinct parent records exist
        async with model_database.session() as session:
            p_parents = (
                await session.scalars(
                    Parent.__table__.select().where(Parent.phone == shared_phone)
                )
            ).all()
            assert len(p_parents) == 2

        # Link rotation tests
        st_link_renew = await client.post(f"{BASE}/{d1['id']}/telegram-link")
        assert st_link_renew.status_code == 200
        assert "student_" in st_link_renew.json()["deep_link"]

        parent_link_renew = await client.post(f"{BASE}/{d1['id']}/parent/telegram-link")
        assert parent_link_renew.status_code == 200
        assert "parent_" in parent_link_renew.json()["deep_link"]


async def test_validation_errors(model_database: Database) -> None:
    grp = await setup_test_group(model_database)
    super_actor = await actor(model_database, role=Role.SUPERADMIN)

    async with client_for(super_actor) as client:
        base = {
            "first_name": "Sardor",
            "last_name": "Karimov",
            "phone": "+998901234567",
            "age": 15,
            "group_id": str(grp.id),
            "parent": {
                "first_name": "Karim",
                "last_name": "Sardorov",
                "phone": "+998907654321",
            },
        }

        # Age invalid (<3 or >100)
        assert (await client.post(BASE, json=dict(base, age=2))).status_code == 422
        assert (await client.post(BASE, json=dict(base, age=101))).status_code == 422

        # Phone format invalid
        assert (
            await client.post(BASE, json=dict(base, phone="invalid_phone"))
        ).status_code == 422
        bad_parent = {
            "first_name": "Karim",
            "last_name": "Sardorov",
            "phone": "12345",
        }
        bad_p = dict(base, parent=bad_parent)
        assert (await client.post(BASE, json=bad_p)).status_code == 422

        # Non-existent group
        bad_g = dict(base, group_id=str(uuid.uuid4()))
        assert (await client.post(BASE, json=bad_g)).status_code == 404

        # Inactive group
        async with model_database.session() as session:
            g = await session.get(Group, grp.id)
            assert g
            g.status = Status.INACTIVE
            await session.commit()

        assert (await client.post(BASE, json=base)).status_code == 409


async def test_capacity_control_and_parallel_requests(model_database: Database) -> None:
    # Setup group with capacity 2
    grp = await setup_test_group(model_database, max_students=2)
    super_actor = await actor(model_database, role=Role.SUPERADMIN)

    async with client_for(super_actor) as client:
        # Create student 1 -> ok
        s1 = await client.post(
            BASE,
            json={
                "first_name": "Talaba1",
                "last_name": "Fam1",
                "phone": "+998901000001",
                "age": 12,
                "group_id": str(grp.id),
                "parent": {"first_name": "Ota1", "last_name": "Fam1", "phone": "+998902000001"},
            },
        )
        assert s1.status_code == 201

        # Create student 2 -> ok
        s2 = await client.post(
            BASE,
            json={
                "first_name": "Talaba2",
                "last_name": "Fam2",
                "phone": "+998901000002",
                "age": 13,
                "group_id": str(grp.id),
                "parent": {"first_name": "Ota2", "last_name": "Fam2", "phone": "+998902000002"},
            },
        )
        assert s2.status_code == 201
        s2_id = s2.json()["id"]

        # Create student 3 -> capacity reached (2 >= 2) -> 409
        s3_blocked = await client.post(
            BASE,
            json={
                "first_name": "Talaba3",
                "last_name": "Fam3",
                "phone": "+998901000003",
                "age": 14,
                "group_id": str(grp.id),
                "parent": {"first_name": "Ota3", "last_name": "Fam3", "phone": "+998902000003"},
            },
        )
        assert s3_blocked.status_code == 409
        assert "bo‘sh joy yo‘q" in s3_blocked.json()["detail"]

        # Deactivate student 2 -> now 1 active student
        deact = await client.post(f"{BASE}/{s2_id}/deactivate")
        assert deact.status_code == 200 and deact.json()["status"] == "inactive"

        # Now student 3 can be created -> 201
        s3_ok = await client.post(
            BASE,
            json={
                "first_name": "Talaba3",
                "last_name": "Fam3",
                "phone": "+998901000003",
                "age": 14,
                "group_id": str(grp.id),
                "parent": {"first_name": "Ota3", "last_name": "Fam3", "phone": "+998902000003"},
            },
        )
        assert s3_ok.status_code == 201

        # Attempt to reactivate student 2 -> group already has 2 active students -> 409
        react_fail = await client.post(f"{BASE}/{s2_id}/activate")
        assert react_fail.status_code == 409
        assert "bo‘sh joy yo‘q" in react_fail.json()["detail"]

    # Parallel requests test: capacity=1, 2 concurrent requests -> exactly 1 succeeds, 1 gets 409
    grp_solo = await setup_test_group(model_database, max_students=1)
    results: list[int] = []

    async def submit_student(idx: int) -> None:
        async with client_for(super_actor) as c:
            r = await c.post(
                BASE,
                json={
                    "first_name": f"Par_{idx}",
                    "last_name": "Test",
                    "phone": f"+99890700000{idx}",
                    "age": 15,
                    "group_id": str(grp_solo.id),
                    "parent": {
                        "first_name": "Par_Ota",
                        "last_name": "Test",
                        "phone": f"+99890800000{idx}",
                    },
                },
            )
            results.append(r.status_code)

    async with anyio.create_task_group() as tg:
        tg.start_soon(submit_student, 1)
        tg.start_soon(submit_student, 2)

    assert sorted(results) == [201, 409]


async def test_transfer_and_deletion(model_database: Database) -> None:
    grp1 = await setup_test_group(model_database, max_students=5)
    grp2 = await setup_test_group(model_database, max_students=1)
    super_actor = await actor(model_database, role=Role.SUPERADMIN)

    async with client_for(super_actor) as client:
        # Create student in grp1
        s1 = (
            await client.post(
                BASE,
                json={
                    "first_name": "Bobur",
                    "last_name": "Mirzo",
                    "phone": "+998903334455",
                    "age": 16,
                    "group_id": str(grp1.id),
                    "parent": {
                        "first_name": "Umar",
                        "last_name": "Mirzo",
                        "phone": "+998905556677",
                    },
                },
            )
        ).json()
        s1_id = s1["id"]

        # Create another student in grp2 (filling its capacity of 1)
        await client.post(
            BASE,
            json={
                "first_name": "Temur",
                "last_name": "Bek",
                "phone": "+998904445566",
                "age": 17,
                "group_id": str(grp2.id),
                "parent": {"first_name": "Taragay", "last_name": "Bek", "phone": "+998906667788"},
            },
        )

        # Attempt to transfer Bobur to full grp2 -> 409
        bad_transfer = await client.post(
            f"{BASE}/{s1_id}/transfer", json={"target_group_id": str(grp2.id)}
        )
        assert bad_transfer.status_code == 409
        assert "bo‘sh joy yo‘q" in bad_transfer.json()["detail"]

        # Create empty grp3
        grp3 = await setup_test_group(model_database, max_students=3)

        # Transfer Bobur to grp3 -> 200
        ok_transfer = await client.post(
            f"{BASE}/{s1_id}/transfer", json={"target_group_id": str(grp3.id)}
        )
        assert ok_transfer.status_code == 200
        assert ok_transfer.json()["group_id"] == str(grp3.id)

        # Attendance blocks deletion
        async with model_database.session() as session:
            teach = await session.get(Staff, grp3.teacher_id)
            assert teach
            att = Attendance(
                group_id=grp3.id,
                student_id=uuid.UUID(s1_id),
                date=date(2026, 10, 5),
                status=AttendanceStatus.PRESENT,
                marked_by=teach.id,
            )
            session.add(att)
            await session.commit()

        # Delete should be blocked -> 409
        del_fail = await client.delete(f"{BASE}/{s1_id}")
        assert del_fail.status_code == 409
        assert "Davomat yozuvlari" in del_fail.json()["detail"]

        # Delete attendance in DB
        async with model_database.session() as session:
            saved_att = await session.get(Attendance, att.id)
            assert saved_att
            await session.delete(saved_att)
            await session.commit()

        # Delete student now succeeds -> 204
        del_ok = await client.delete(f"{BASE}/{s1_id}")
        assert del_ok.status_code == 204
        assert (await client.get(f"{BASE}/{s1_id}")).status_code == 404
