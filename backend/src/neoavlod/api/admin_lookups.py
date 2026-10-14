"""Minimal selector data scoped to the action requiring it, without management grants."""

from typing import Any

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from neoavlod.api.deps import AdminDependency, SessionDependency
from neoavlod.errors import DomainError
from neoavlod.models import (
    Group,
    Parent,
    Role,
    Room,
    Staff,
    Student,
    StudentGroupEnrollment,
    Subject,
)
from neoavlod.models.common import Status
from neoavlod.security.rbac import FORBIDDEN, Permission, has_permission

router = APIRouter(prefix="/api/v1/admin/lookups", tags=["admin-lookups"])


@router.get("/parents")
async def parent_options(
    identity: AdminDependency,
    session: SessionDependency,
    q: str | None = Query(default=None, max_length=100),
) -> dict[str, Any]:
    require_any(identity, Permission.STUDENTS_CREATE, Permission.STUDENTS_EDIT)
    children = (
        select(Student.parent_id, func.count().label("child_count"))
        .group_by(Student.parent_id)
        .subquery()
    )
    query = select(
        Parent.id,
        Parent.first_name,
        Parent.last_name,
        Parent.phone,
        (Parent.telegram_id.is_not(None) & Parent.telegram_reconnect_required.is_(False)).label(
            "telegram_connected"
        ),
        func.coalesce(children.c.child_count, 0).label("child_count"),
    ).outerjoin(children, Parent.id == children.c.parent_id)
    if q:
        value = q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        query = query.where(
            (Parent.first_name + " " + Parent.last_name).ilike(f"%{value}%", escape="\\")
            | Parent.phone.ilike(f"%{value}%", escape="\\")
        )
    rows = (
        (
            await session.execute(
                query.order_by(Parent.first_name, Parent.last_name, Parent.id).limit(50)
            )
        )
        .mappings()
        .all()
    )
    return {"items": [dict(row) for row in rows]}


@router.get("/rooms")
async def room_options(identity: AdminDependency, session: SessionDependency) -> dict[str, Any]:
    require_any(identity, Permission.GROUPS_CREATE, Permission.GROUPS_EDIT, Permission.ROOMS_MANAGE)
    rows = (
        (
            await session.execute(
                select(Room.id, Room.name, Room.is_active)
                .where(Room.is_active.is_(True))
                .order_by(Room.name)
                .limit(1000)
            )
        )
        .mappings()
        .all()
    )
    return {"items": [dict(row) for row in rows]}


def require_any(identity: AdminDependency, *permissions: Permission) -> None:
    if not any(has_permission(identity.staff, value) for value in permissions):
        raise DomainError(FORBIDDEN, 403)


@router.get("/group-options")
async def group_options(
    identity: AdminDependency,
    session: SessionDependency,
    active_only: bool = False,
) -> dict[str, Any]:
    require_any(identity, Permission.GROUPS_READ, Permission.GROUPS_CREATE, Permission.GROUPS_EDIT)
    subjects_query = select(Subject.id, Subject.name, Subject.is_active).order_by(Subject.name)
    teachers_query = (
        select(Staff.id, Staff.first_name, Staff.last_name, Staff.status)
        .where(Staff.role == Role.TEACHER)
        .order_by(Staff.first_name, Staff.last_name)
    )
    rooms_query = select(Room.id, Room.name, Room.is_active).order_by(Room.name).limit(1000)
    if active_only:
        subjects_query = subjects_query.where(Subject.is_active.is_(True))
        teachers_query = teachers_query.where(Staff.status == Status.ACTIVE)
        rooms_query = rooms_query.where(Room.is_active.is_(True))
    subjects = (await session.execute(subjects_query)).mappings().all()
    teachers = (await session.execute(teachers_query)).mappings().all()
    rooms = (await session.execute(rooms_query)).mappings().all()
    return {
        "subjects": [dict(row) for row in subjects],
        "teachers": [dict(row) for row in teachers],
        "rooms": [dict(row) for row in rooms],
    }


@router.get("/student-groups")
async def student_groups(identity: AdminDependency, session: SessionDependency) -> dict[str, Any]:
    require_any(
        identity, Permission.STUDENTS_READ, Permission.STUDENTS_CREATE, Permission.STUDENTS_EDIT
    )
    query = (
        select(
            Group.id,
            Group.name,
            Group.max_students,
            func.count(Student.id).label("current_students"),
        )
        .outerjoin(
            StudentGroupEnrollment,
            (StudentGroupEnrollment.group_id == Group.id)
            & StudentGroupEnrollment.is_active.is_(True),
        )
        .outerjoin(
            Student,
            (Student.id == StudentGroupEnrollment.student_id) & (Student.status == Status.ACTIVE),
        )
        .where(Group.status == Status.ACTIVE)
        .group_by(Group.id)
        .order_by(Group.name)
    )
    return {"items": [dict(row) for row in (await session.execute(query)).mappings().all()]}
