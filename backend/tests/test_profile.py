import uuid

import pytest
from test_rbac import actor, client_for

from neoavlod.database import Database
from neoavlod.models import Role, Staff
from neoavlod.models.common import Status

pytestmark = pytest.mark.anyio


async def test_all_three_roles_update_their_own_profile(model_database: Database) -> None:
    # 1. Superadmin updates their profile on admin portal
    superadmin = await actor(
        model_database, role=Role.SUPERADMIN, username="super_orig", phone="+998901111111"
    )
    async with client_for(superadmin) as client:
        res = await client.patch(
            "/api/v1/auth/admin/me",
            json={
                "first_name": "Yangi Ism",
                "last_name": "Yangi Familiya",
                "phone": "+998902222222",
                "username": "super_updated",
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["first_name"] == "Yangi Ism"
        assert data["last_name"] == "Yangi Familiya"
        assert data["phone"] == "+998902222222"
        assert data["username"] == "super_updated"
        assert data["role"] == "superadmin"

        # Verify subsequent GET /me returns the updated profile
        me = await client.get("/api/v1/auth/admin/me")
        assert me.status_code == 200
        assert me.json()["username"] == "super_updated"

    # 2. Admin updates their profile on admin portal
    admin_user = await actor(
        model_database, role=Role.ADMIN, username="admin_orig", phone="+998903333333"
    )
    async with client_for(admin_user) as client:
        res = await client.patch(
            "/api/v1/auth/admin/me",
            json={"first_name": "Admin Yaxshi", "username": "admin_new"},
        )
        assert res.status_code == 200
        assert res.json()["first_name"] == "Admin Yaxshi"
        assert res.json()["username"] == "admin_new"
        assert res.json()["phone"] == "+998903333333"

    # 3. Teacher updates their profile on teacher portal
    teacher_user = await actor(
        model_database, role=Role.TEACHER, username="teacher_orig", phone="+998904444444"
    )
    async with client_for(teacher_user) as client:
        res = await client.patch(
            "/api/v1/auth/teacher/me",
            json={"last_name": "Umarov", "phone": "+998905555555"},
        )
        assert res.status_code == 200
        assert res.json()["last_name"] == "Umarov"
        assert res.json()["phone"] == "+998905555555"
        assert res.json()["role"] == "teacher"


async def test_protected_fields_and_extra_attributes_rejected(model_database: Database) -> None:
    teacher_user = await actor(model_database, role=Role.TEACHER)
    async with client_for(teacher_user) as client:
        # Cannot promote oneself to superadmin or admin
        r1 = await client.patch("/api/v1/auth/teacher/me", json={"role": "superadmin"})
        assert r1.status_code == 422

        # Cannot modify permissions
        r2 = await client.patch("/api/v1/auth/teacher/me", json={"permissions": ["staff:manage"]})
        assert r2.status_code == 422

        # Cannot modify status
        r3 = await client.patch("/api/v1/auth/teacher/me", json={"status": "inactive"})
        assert r3.status_code == 422

        # Cannot modify telegram_id
        r4 = await client.patch("/api/v1/auth/teacher/me", json={"telegram_id": 12345})
        assert r4.status_code == 422

        # Cannot modify id
        r5 = await client.patch("/api/v1/auth/teacher/me", json={"id": str(uuid.uuid4())})
        assert r5.status_code == 422


async def test_username_and_phone_uniqueness_enforced(model_database: Database) -> None:
    first = await actor(model_database, username="user_one", phone="+998901110001")
    second = await actor(model_database, username="user_two", phone="+998901110002")
    assert first.staff_id != second.staff_id

    async with client_for(second) as client:
        # Username clash
        clash_u = await client.patch("/api/v1/auth/admin/me", json={"username": "user_one"})
        assert clash_u.status_code == 409
        assert "Username yoki telefon" in clash_u.json()["detail"]

        # Phone clash
        clash_p = await client.patch("/api/v1/auth/admin/me", json={"phone": "+998901110001"})
        assert clash_p.status_code == 409
        assert "Username yoki telefon" in clash_p.json()["detail"]


async def test_validation_errors(model_database: Database) -> None:
    teacher = await actor(model_database, role=Role.TEACHER)
    async with client_for(teacher) as client:
        # Empty first_name
        r1 = await client.patch("/api/v1/auth/teacher/me", json={"first_name": "  "})
        assert r1.status_code == 422

        # Invalid phone
        r2 = await client.patch("/api/v1/auth/teacher/me", json={"phone": "not-a-phone"})
        assert r2.status_code == 422

        # Invalid username (too short or invalid chars)
        r3 = await client.patch("/api/v1/auth/teacher/me", json={"username": "ab"})
        assert r3.status_code == 422
        r4 = await client.patch("/api/v1/auth/teacher/me", json={"username": "user name"})
        assert r4.status_code == 422


async def test_cross_portal_and_inactive_protection(model_database: Database) -> None:
    teacher = await actor(model_database, role=Role.TEACHER)
    admin_user = await actor(model_database, role=Role.ADMIN)

    # Cross portal requests rejected
    async with client_for(teacher) as client:
        r1 = await client.patch("/api/v1/auth/admin/me", json={"first_name": "Test"})
        assert r1.status_code == 403

    async with client_for(admin_user) as client:
        r2 = await client.patch("/api/v1/auth/teacher/me", json={"first_name": "Test"})
        assert r2.status_code == 403

    # Inactive staff rejected
    async with model_database.session() as session:
        person = await session.get(Staff, teacher.staff_id)
        assert person is not None
        person.status = Status.INACTIVE
        await session.commit()

    async with client_for(teacher) as client:
        res = await client.patch("/api/v1/auth/teacher/me", json={"first_name": "Yangi"})
        assert res.status_code in (401, 403)
