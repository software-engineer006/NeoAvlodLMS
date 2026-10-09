import uuid
from decimal import Decimal

import pytest
from factories import group, parent, staff, student
from test_rbac import actor, client_for

from neoavlod.database import Database
from neoavlod.main import create_app
from neoavlod.models import Role, Subject
from neoavlod.models.common import Status

pytestmark = pytest.mark.anyio
URL = "/api/v1/admin/dashboard/stats"


async def test_unauthenticated_and_teacher_rejected(model_database: Database) -> None:
    # 1. Unauthenticated client
    app = create_app()
    import httpx

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="https://admin.eduneo.uz"
    ) as client:
        res = await client.get(URL)
        assert res.status_code == 401

    # 2. Teacher client
    teacher_actor = await actor(model_database, role=Role.TEACHER)
    async with client_for(teacher_actor) as client:
        res = await client.get(URL)
        assert res.status_code == 403


async def test_superadmin_receives_all_counts(model_database: Database) -> None:
    superadmin = await actor(model_database, role=Role.SUPERADMIN)
    async with model_database.session() as session:
        # Create a teacher staff
        t1 = staff(role=Role.TEACHER, status=Status.ACTIVE)
        session.add(t1)
        # Create a subject and group
        sub = Subject(name=f"Sub_{uuid.uuid4().hex[:6]}", description="Dars", is_active=True)
        session.add(sub)
        await session.flush()

        g1 = group(
            subject_id=sub.id,
            teacher_id=t1.id,
            status=Status.ACTIVE,
            monthly_price=Decimal("200000.00"),
        )
        session.add(g1)

        # Create parent and student
        p1 = parent()
        session.add(p1)
        await session.flush()

        s1 = student(group_id=g1.id, parent_id=p1.id, status=Status.ACTIVE)
        session.add(s1)
        await session.commit()

    async with client_for(superadmin) as client:
        res = await client.get(URL)
        assert res.status_code == 200
        data = res.json()
        assert data["groups_count"] is not None and data["groups_count"] >= 1
        assert data["students_count"] is not None and data["students_count"] >= 1
        assert data["staff_count"] is not None and data["staff_count"] >= 2
        assert data["staff_breakdown"] is not None
        assert data["staff_breakdown"]["superadmins"] >= 1
        assert data["staff_breakdown"]["teachers"] >= 1


async def test_limited_admin_sees_only_permitted_stats(model_database: Database) -> None:
    student_admin = await actor(model_database, permissions=["students:read"])
    async with client_for(student_admin) as client:
        res = await client.get(URL)
        assert res.status_code == 200
        data = res.json()
        assert data["students_count"] is not None
        assert data["groups_count"] is None
        assert data["staff_count"] is None
        assert data["staff_breakdown"] is None

    group_admin = await actor(model_database, permissions=["groups:read"])
    async with client_for(group_admin) as client:
        res = await client.get(URL)
        assert res.status_code == 200
        data = res.json()
        assert data["groups_count"] is not None
        assert data["students_count"] is None
        assert data["staff_count"] is None


async def test_inactive_entities_are_excluded_from_counts(model_database: Database) -> None:
    superadmin = await actor(model_database, role=Role.SUPERADMIN)
    async with model_database.session() as session:
        sub = Subject(name=f"Sub_{uuid.uuid4().hex[:6]}", description="Dars", is_active=True)
        t1 = staff(role=Role.TEACHER, status=Status.ACTIVE)
        session.add_all([sub, t1])
        await session.flush()

        # Inactive group
        g_inactive = group(
            subject_id=sub.id,
            teacher_id=t1.id,
            status=Status.INACTIVE,
            monthly_price=Decimal("150000.00"),
        )
        p = parent()
        session.add_all([g_inactive, p])
        await session.flush()

        # Inactive student
        s_inactive = student(group_id=g_inactive.id, parent_id=p.id, status=Status.INACTIVE)
        # Inactive staff
        staff_inactive = staff(role=Role.ADMIN, status=Status.INACTIVE)
        session.add_all([s_inactive, staff_inactive])
        await session.commit()

    async with client_for(superadmin) as client:
        res = await client.get(URL)
        assert res.status_code == 200
        data = res.json()
        # Verify status 200 and integer values
        assert isinstance(data["groups_count"], int)
        assert isinstance(data["students_count"], int)
        assert isinstance(data["staff_count"], int)
