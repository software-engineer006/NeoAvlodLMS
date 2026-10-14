import uuid

import pytest
from factories import group, staff
from sqlalchemy import select
from test_rbac import actor, client_for

from neoavlod.database import Database
from neoavlod.models import Role, Staff, Subject
from neoavlod.models.common import Status
from neoavlod.security.rbac import Permission, validate_permissions

pytestmark = pytest.mark.anyio

ROUTES = {
    "/api/v1/admin/staff": {"staff:manage"},
    "/api/v1/admin/subjects": {"subjects:manage"},
    "/api/v1/admin/rooms": {"rooms:manage"},
    "/api/v1/admin/lookups/rooms": {"groups:create", "groups:edit", "rooms:manage"},
    "/api/v1/admin/groups": {"groups:read", "groups:create", "groups:edit"},
    "/api/v1/admin/students": {"students:read", "students:create", "students:edit"},
    "/api/v1/admin/attendance/groups": {"attendance:read", "attendance:write"},
    "/api/v1/admin/attendance/message-template": {"attendance:write"},
    "/api/v1/admin/messages": {"messages:send"},
    "/api/v1/admin/lookups/group-options": {"groups:read", "groups:create", "groups:edit"},
    "/api/v1/admin/lookups/student-groups": {"students:read", "students:create", "students:edit"},
    "/api/v1/admin/lookups/parents": {"students:create", "students:edit"},
}


@pytest.mark.parametrize(
    "grant", [None, *[item.value for item in Permission], "full", "*", "unknown:permission"]
)
async def test_every_admin_grant_against_real_route_matrix(
    model_database: Database, grant: str | None
) -> None:
    permissions = (
        [item.value for item in Permission] if grant == "full" else [grant] if grant else []
    )
    who = await actor(model_database, permissions=permissions)
    async with client_for(who) as client:
        for path, allowed in ROUTES.items():
            response = await client.get(path)
            assert response.status_code == (200 if set(permissions) & allowed else 403), (
                grant,
                path,
                response.text,
            )
        # Even a full grant list is not the superadmin role.
        assert (await client.get("/api/v1/admin/settings/bot")).status_code == 403


@pytest.mark.parametrize("role", [Role.SUPERADMIN, Role.TEACHER])
async def test_role_boundaries_on_real_routes(model_database: Database, role: Role) -> None:
    who = await actor(model_database, role=role, permissions=[item.value for item in Permission])
    async with client_for(who) as client:
        for path in [*ROUTES, "/api/v1/admin/settings/bot"]:
            assert (await client.get(path)).status_code == (200 if role == Role.SUPERADMIN else 403)


async def test_limited_creator_options_enable_creation_without_staff_or_subject_management(
    model_database: Database,
) -> None:
    who = await actor(model_database, permissions=["groups:create"])
    async with model_database.session() as session:
        subject = Subject(name="English A")
        inactive_subject = Subject(name="Closed subject", is_active=False)
        teacher = staff(role=Role.TEACHER)
        inactive_teacher = staff(role=Role.TEACHER, status=Status.INACTIVE)
        session.add_all([subject, inactive_subject, teacher, inactive_teacher])
        await session.commit()
    async with client_for(who) as client:
        result = await client.get(
            "/api/v1/admin/lookups/group-options", params={"active_only": True}
        )
        assert result.status_code == 200
        assert result.json()["subjects"] == [
            {"id": str(subject.id), "name": subject.name, "is_active": True}
        ]
        assert len(result.json()["teachers"]) == 1
        assert set(result.json()["teachers"][0]) == {"id", "first_name", "last_name", "status"}
        assert (await client.get("/api/v1/admin/staff")).status_code == 403
        assert (await client.get("/api/v1/admin/subjects")).status_code == 403
        created = await client.post(
            "/api/v1/admin/groups",
            json={
                "name": "English A",
                "subject_id": str(subject.id),
                "teacher_id": str(teacher.id),
                "max_students": 15,
                "days_of_week": [1, 3, 5],
            },
        )
        assert created.status_code == 201, created.text
        assert (await client.get("/api/v1/admin/groups")).status_code == 200
        assert (
            await client.patch(
                f"/api/v1/admin/groups/{created.json()['id']}", json={"name": "Denied"}
            )
        ).status_code == 403


async def test_student_editor_capacity_lookup_and_immediate_revocation(
    model_database: Database,
) -> None:
    who = await actor(model_database, permissions=["students:edit"])
    async with model_database.session() as session:
        subject = Subject(name="English")
        teacher = staff(role=Role.TEACHER)
        session.add_all([subject, teacher])
        await session.flush()
        active = group(subject.id, teacher.id)
        inactive = group(subject.id, teacher.id, name="Closed", status=Status.INACTIVE)
        session.add_all([active, inactive])
        await session.commit()
    async with client_for(who) as client:
        result = await client.get("/api/v1/admin/lookups/student-groups")
        assert result.status_code == 200 and len(result.json()["items"]) == 1
        assert set(result.json()["items"][0]) == {"id", "name", "max_students", "current_students"}
        assert result.json()["items"][0]["current_students"] == 0
        assert (await client.get("/api/v1/admin/groups")).status_code == 403
        async with model_database.session() as session:
            person = await session.scalar(select(Staff).where(Staff.id == who.staff_id))
            assert person
            person.permissions = []
            await session.commit()
        assert (await client.get("/api/v1/admin/lookups/student-groups")).status_code == 403
        assert (
            await client.patch(
                f"/api/v1/admin/students/{uuid.uuid4()}", json={"first_name": "Denied"}
            )
        ).status_code == 403


async def test_inactive_account_rejected_on_every_route(model_database: Database) -> None:
    who = await actor(model_database, role=Role.SUPERADMIN)
    async with model_database.session() as session:
        person = await session.get(Staff, who.staff_id)
        assert person
        person.status = Status.INACTIVE
        await session.commit()
    async with client_for(who) as client:
        for path in ROUTES:
            assert (await client.get(path)).status_code == 401


def test_write_grants_normalize_read_dependencies_without_escalating_other_modules() -> None:
    assert validate_permissions(["groups:create"]) == ["groups:create", "groups:read"]
    assert validate_permissions(["groups:edit"]) == ["groups:edit", "groups:read"]
    assert validate_permissions(["students:create"]) == ["students:create", "students:read"]
    assert validate_permissions(["students:edit"]) == ["students:edit", "students:read"]
