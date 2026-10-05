import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Annotated, Any

import httpx
import pytest
from factories import group, parent, staff, student
from fastapi import APIRouter, Depends, FastAPI
from sqlalchemy import select

from neoavlod.api.deps import (
    SessionDependency,
    SuperadminDependency,
    TeacherDependency,
    require_permission,
)
from neoavlod.database import Database
from neoavlod.errors import DomainError
from neoavlod.main import create_app
from neoavlod.models import Portal, Role, Staff, Subject
from neoavlod.models.common import Status
from neoavlod.security.rbac import (
    PERMISSION_CATALOG,
    Permission,
    ensure_group_owner,
    ensure_student_owner,
    has_permission,
    validate_permissions,
)
from neoavlod.security.sessions import ACCESS_COOKIE, CSRF_COOKIE, Identity, Tokens, issue_session

pytestmark = pytest.mark.anyio
ADMIN_ORIGIN = "https://admin.eduneo.uz"
TEACHER_ORIGIN = "https://teacher.eduneo.uz"

probe = APIRouter(prefix="/probe")


StudentsRead = Annotated[Identity, Depends(require_permission(Permission.STUDENTS_READ))]
StudentsCreate = Annotated[Identity, Depends(require_permission(Permission.STUDENTS_CREATE))]


@probe.get("/students")
async def students_read(_: StudentsRead) -> dict[str, bool]:
    return {"ok": True}


@probe.post("/students")
async def students_create(_: StudentsCreate) -> dict[str, bool]:
    return {"ok": True}


@probe.get("/super")
async def super_only(_: SuperadminDependency) -> dict[str, bool]:
    return {"ok": True}


@probe.get("/teacher/groups/{group_id}")
async def teacher_group(
    group_id: uuid.UUID, identity: TeacherDependency, session: SessionDependency
) -> dict[str, bool]:
    await ensure_group_owner(session, identity, group_id)
    return {"ok": True}


@probe.get("/teacher/students/{student_id}")
async def teacher_student(
    student_id: uuid.UUID, identity: TeacherDependency, session: SessionDependency
) -> dict[str, bool]:
    await ensure_student_owner(session, identity, student_id)
    return {"ok": True}


@dataclass
class Actor:
    staff_id: uuid.UUID
    tokens: Tokens
    portal: Portal

    @property
    def origin(self) -> str:
        return ADMIN_ORIGIN if self.portal == Portal.ADMIN else TEACHER_ORIGIN


async def actor(database: Database, **values: Any) -> Actor:
    role = values.setdefault("role", Role.ADMIN)
    values.setdefault("telegram_id", int(uuid.uuid4().int % 10**9) + 1)
    person = staff(**values)
    portal = Portal.TEACHER if role == Role.TEACHER else Portal.ADMIN
    async with database.session() as session:
        session.add(person)
        await session.flush()
        tokens = await issue_session(session, person, portal)
        await session.commit()
    return Actor(person.id, tokens, portal)


@asynccontextmanager
async def client_for(who: Actor) -> AsyncIterator[httpx.AsyncClient]:
    app: FastAPI = create_app()
    app.include_router(probe)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url=who.origin,
            headers={"Origin": who.origin, "X-CSRF-Token": who.tokens.csrf},
        ) as client,
    ):
        client.cookies.set(ACCESS_COOKIE, who.tokens.access)
        client.cookies.set(CSRF_COOKIE, who.tokens.csrf)
        yield client


def test_catalogue_is_exactly_the_documented_keys() -> None:
    assert PERMISSION_CATALOG == {
        "staff:manage",
        "subjects:manage",
        "groups:read",
        "groups:create",
        "groups:edit",
        "students:read",
        "students:create",
        "students:edit",
        "attendance:read",
    }


def test_permission_matrix_by_role_and_status() -> None:
    active = Status.ACTIVE
    admin = staff(role=Role.ADMIN, status=active, permissions=["students:read"])
    assert has_permission(admin, Permission.STUDENTS_READ)
    assert not has_permission(admin, Permission.STUDENTS_CREATE)
    assert not has_permission(admin, Permission.STAFF_MANAGE)
    boss = staff(role=Role.SUPERADMIN, status=active, permissions=[])
    assert all(has_permission(boss, item) for item in Permission)
    teacher = staff(
        role=Role.TEACHER, status=active, permissions=[item.value for item in Permission]
    )
    assert not any(has_permission(teacher, item) for item in Permission)
    for person in (admin, boss):
        person.status = Status.INACTIVE
        assert not any(has_permission(person, item) for item in Permission)


def test_unknown_permissions_are_rejected_everywhere() -> None:
    assert validate_permissions(["students:read", "groups:read", "students:read"]) == [
        "groups:read",
        "students:read",
    ]
    for bad in ("students:delete", "", "*", "STUDENTS:READ", "bot:manage"):
        with pytest.raises(DomainError) as error:
            validate_permissions(["students:read", bad])
        assert error.value.status_code == 422
    with pytest.raises(ValueError):
        require_permission("unknown:permission")
    with pytest.raises(ValueError):
        require_permission()
    # An unknown key stored on an admin never grants any catalogue permission.
    admin = staff(role=Role.ADMIN, status=Status.ACTIVE, permissions=["unknown:permission"])
    assert not any(has_permission(admin, item) for item in Permission)


async def test_admin_permissions_and_superadmin_over_http(model_database: Database) -> None:
    reader = await actor(model_database, permissions=["students:read"])
    async with client_for(reader) as client:
        assert (await client.get("/probe/students")).status_code == 200
        denied = await client.post("/probe/students")
        assert denied.status_code == 403
        assert (await client.get("/probe/super")).status_code == 403
    boss = await actor(model_database, role=Role.SUPERADMIN)
    async with client_for(boss) as client:
        assert (await client.get("/probe/students")).status_code == 200
        assert (await client.post("/probe/students")).status_code == 200
        assert (await client.get("/probe/super")).status_code == 200


async def test_unsafe_requests_need_origin_and_csrf(model_database: Database) -> None:
    writer = await actor(model_database, permissions=["students:create"])
    async with client_for(writer) as client:
        assert (
            await client.post("/probe/students", headers={"X-CSRF-Token": "x"})
        ).status_code == 403
        assert (
            await client.post("/probe/students", headers={"Origin": "https://evil.test"})
        ).status_code == 403
        assert (await client.post("/probe/students")).status_code == 200


async def test_teacher_is_forbidden_from_admin_routes_and_admin_from_teacher_routes(
    model_database: Database,
) -> None:
    teacher = await actor(model_database, role=Role.TEACHER)
    async with client_for(teacher) as client:
        for path in ("/probe/students", "/probe/super"):
            assert (await client.get(path)).status_code == 403
    admin = await actor(model_database, permissions=[item.value for item in Permission])
    async with client_for(admin) as client:
        assert (await client.get(f"/probe/teacher/groups/{uuid.uuid4()}")).status_code == 403
    boss = await actor(model_database, role=Role.SUPERADMIN)
    async with client_for(boss) as client:
        assert (await client.get(f"/probe/teacher/groups/{uuid.uuid4()}")).status_code == 403


async def test_unauthenticated_inactive_demoted_and_revoked_users_lose_access(
    model_database: Database,
) -> None:
    admin = await actor(model_database, permissions=["students:read"])
    async with client_for(admin) as client:
        client.cookies.clear()
        assert (await client.get("/probe/students")).status_code == 401
        client.cookies.set(ACCESS_COOKIE, admin.tokens.access)
        assert (await client.get("/probe/students")).status_code == 200
        async with model_database.session() as session:
            person = await session.scalar(select(Staff).where(Staff.id == admin.staff_id))
            assert person
            person.permissions = []
            await session.commit()
        assert (await client.get("/probe/students")).status_code == 403
        async with model_database.session() as session:
            person = await session.scalar(select(Staff).where(Staff.id == admin.staff_id))
            assert person
            person.permissions = ["students:read"]
            person.status = Status.INACTIVE
            await session.commit()
        assert (await client.get("/probe/students")).status_code == 401
        async with model_database.session() as session:
            person = await session.scalar(select(Staff).where(Staff.id == admin.staff_id))
            assert person
            person.status = Status.ACTIVE
            person.role = Role.TEACHER
            await session.commit()
        assert (await client.get("/probe/students")).status_code == 403


async def test_teacher_ownership_is_checked_in_sql(model_database: Database) -> None:
    mine = await actor(model_database, role=Role.TEACHER)
    other = await actor(model_database, role=Role.TEACHER)
    async with model_database.session() as session:
        subject = Subject(name="Matematika")
        session.add(subject)
        await session.flush()
        own_group = group(subject.id, mine.staff_id)
        foreign_group = group(subject.id, other.staff_id, name="Fizika A")
        guardian = parent()
        session.add_all([own_group, foreign_group, guardian])
        await session.flush()
        own_student = student(own_group.id, guardian.id)
        foreign_student = student(foreign_group.id, guardian.id, phone="+998907654321")
        session.add_all([own_student, foreign_student])
        await session.commit()
        ids = (own_group.id, foreign_group.id, own_student.id, foreign_student.id)
    own_group_id, foreign_group_id, own_student_id, foreign_student_id = ids
    async with client_for(mine) as client:
        assert (await client.get(f"/probe/teacher/groups/{own_group_id}")).status_code == 200
        assert (await client.get(f"/probe/teacher/students/{own_student_id}")).status_code == 200
        for path in (
            f"/probe/teacher/groups/{foreign_group_id}",
            f"/probe/teacher/students/{foreign_student_id}",
            f"/probe/teacher/groups/{uuid.uuid4()}",
            f"/probe/teacher/students/{uuid.uuid4()}",
        ):
            assert (await client.get(path)).status_code == 404
