import uuid
from datetime import time
from decimal import Decimal

import pytest
from factories import parent, student
from test_rbac import Actor, actor, client_for

from neoavlod.database import Database
from neoavlod.models import Group, Role, Subject
from neoavlod.models.common import Status

pytestmark = pytest.mark.anyio
BASE = "/api/v1/teacher"


async def setup_two_teachers_with_classes(
    database: Database,
) -> tuple[Actor, Group, Actor, Group, uuid.UUID, uuid.UUID]:
    t1_actor = await actor(database, role=Role.TEACHER)
    t2_actor = await actor(database, role=Role.TEACHER)

    async with database.session() as session:
        sub = Subject(name=f"Fan_{uuid.uuid4().hex[:8]}")
        session.add(sub)
        await session.flush()

        g1 = Group(
            name="Guruh Ustoz 1",
            subject_id=sub.id,
            teacher_id=t1_actor.staff_id,
            monthly_price=Decimal("400000.00"),
            max_students=15,
            days_of_week=[1, 3, 5],
            start_time=time(9, 0),
            end_time=time(10, 30),
            room_number="101",
            status=Status.ACTIVE,
        )
        g2 = Group(
            name="Guruh Ustoz 2",
            subject_id=sub.id,
            teacher_id=t2_actor.staff_id,
            monthly_price=Decimal("450000.00"),
            max_students=20,
            days_of_week=[2, 4, 6],
            start_time=time(11, 0),
            end_time=time(12, 30),
            room_number="102",
            status=Status.ACTIVE,
        )
        session.add_all([g1, g2])
        await session.flush()

        p1 = parent(first_name="Ota1", last_name="Aliyev", phone="+998901112233")
        p2 = parent(first_name="Ota2", last_name="Valiyev", phone="+998902223344")
        session.add_all([p1, p2])
        await session.flush()

        s1 = student(g1.id, p1.id, first_name="Ali", last_name="Aliyev")
        s2 = student(g2.id, p2.id, first_name="Vali", last_name="Valiyev")
        session.add_all([s1, s2])
        await session.commit()
        return t1_actor, g1, t2_actor, g2, s1.id, s2.id


async def test_teacher_portal_guard_and_permissions(model_database: Database) -> None:
    t1_actor, g1, _, _, s1_id, _ = await setup_two_teachers_with_classes(model_database)
    admin_actor = await actor(model_database, role=Role.ADMIN, permissions=["groups:read"])
    super_actor = await actor(model_database, role=Role.SUPERADMIN)

    # Admin and superadmin get 403 on teacher routes
    async with client_for(admin_actor) as client:
        assert (await client.get(f"{BASE}/groups")).status_code == 403
        assert (await client.get(f"{BASE}/groups/{g1.id}")).status_code == 403
        assert (await client.get(f"{BASE}/groups/{g1.id}/students")).status_code == 403
        assert (await client.get(f"{BASE}/students/{s1_id}")).status_code == 403

    async with client_for(super_actor) as client:
        assert (await client.get(f"{BASE}/groups")).status_code == 403

    # Teacher gets 200
    async with client_for(t1_actor) as client:
        assert (await client.get(f"{BASE}/groups")).status_code == 200


async def test_teacher_group_and_student_ownership_isolation(
    model_database: Database,
) -> None:
    t1_actor, g1, t2_actor, g2, s1_id, s2_id = await setup_two_teachers_with_classes(model_database)

    # Teacher 1 sees only g1
    async with client_for(t1_actor) as client:
        groups_res = (await client.get(f"{BASE}/groups")).json()
        assert len(groups_res) == 1
        assert groups_res[0]["id"] == str(g1.id)
        assert groups_res[0]["name"] == "Guruh Ustoz 1"
        assert groups_res[0]["current_students"] == 1

        # Teacher 1 reads g1 -> 200
        g1_detail = await client.get(f"{BASE}/groups/{g1.id}")
        assert g1_detail.status_code == 200
        assert g1_detail.json()["id"] == str(g1.id)

        # Teacher 1 attempts to read Teacher 2's group -> 404 (ownership check)
        bad_g = await client.get(f"{BASE}/groups/{g2.id}")
        assert bad_g.status_code == 404
        assert "Guruh topilmadi" in bad_g.json()["detail"]

        # Teacher 1 attempts to read students in Teacher 2's group -> 404
        bad_g_students = await client.get(f"{BASE}/groups/{g2.id}/students")
        assert bad_g_students.status_code == 404
        assert "Guruh topilmadi" in bad_g_students.json()["detail"]

        # Teacher 1 reads students in own group g1 -> 200
        g1_students = await client.get(f"{BASE}/groups/{g1.id}/students")
        assert g1_students.status_code == 200
        st_list = g1_students.json()
        assert len(st_list) == 1
        assert st_list[0]["id"] == str(s1_id)
        assert st_list[0]["first_name"] == "Ali"
        assert st_list[0]["parent"]["first_name"] == "Ota1"
        assert st_list[0]["parent"]["phone"] == "+998901112233"
        assert st_list[0]["parent"]["telegram_connected"] is False

        # Teacher 1 reads own student -> 200
        s1_detail = await client.get(f"{BASE}/students/{s1_id}")
        assert s1_detail.status_code == 200
        assert s1_detail.json()["id"] == str(s1_id)
        assert s1_detail.json()["parent"]["phone"] == "+998901112233"

        # Teacher 1 attempts to read Teacher 2's student -> 404
        bad_student = await client.get(f"{BASE}/students/{s2_id}")
        assert bad_student.status_code == 404
        assert "Talaba topilmadi" in bad_student.json()["detail"]

    # Teacher 2 sees only g2
    async with client_for(t2_actor) as client:
        groups_res2 = (await client.get(f"{BASE}/groups")).json()
        assert len(groups_res2) == 1
        assert groups_res2[0]["id"] == str(g2.id)

        # Teacher 2 can read s2 but not s1
        assert (await client.get(f"{BASE}/students/{s2_id}")).status_code == 200
        assert (await client.get(f"{BASE}/students/{s1_id}")).status_code == 404
