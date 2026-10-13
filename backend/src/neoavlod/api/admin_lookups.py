"""Minimal selector data scoped to the action requiring it, without management grants."""

from typing import Any

from fastapi import APIRouter
from sqlalchemy import func, select

from neoavlod.api.deps import AdminDependency, SessionDependency
from neoavlod.errors import DomainError
from neoavlod.models import Group, Role, Staff, Student, Subject
from neoavlod.models.common import Status
from neoavlod.security.rbac import FORBIDDEN, Permission, has_permission

router = APIRouter(prefix="/api/v1/admin/lookups", tags=["admin-lookups"])


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
    if active_only:
        subjects_query = subjects_query.where(Subject.is_active.is_(True))
        teachers_query = teachers_query.where(Staff.status == Status.ACTIVE)
    subjects = (await session.execute(subjects_query)).mappings().all()
    teachers = (await session.execute(teachers_query)).mappings().all()
    return {
        "subjects": [dict(row) for row in subjects],
        "teachers": [dict(row) for row in teachers],
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
        .outerjoin(Student, (Student.group_id == Group.id) & (Student.status == Status.ACTIVE))
        .where(Group.status == Status.ACTIVE)
        .group_by(Group.id)
        .order_by(Group.name)
    )
    return {"items": [dict(row) for row in (await session.execute(query)).mappings().all()]}
