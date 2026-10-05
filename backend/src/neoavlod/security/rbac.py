"""Role/permission rules shared by every protected endpoint.

Superadmin implicitly holds every catalogue permission, admin holds only the
catalogue keys stored on the account, and teacher holds none: teacher access is
granted through ownership of groups/students, checked with SQL.
"""

import uuid
from collections.abc import Iterable
from enum import StrEnum

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from neoavlod.errors import DomainError
from neoavlod.models import Group, Portal, Role, Staff, Student
from neoavlod.models.common import Status
from neoavlod.security.sessions import Identity


class Permission(StrEnum):
    STAFF_MANAGE = "staff:manage"
    SUBJECTS_MANAGE = "subjects:manage"
    GROUPS_READ = "groups:read"
    GROUPS_CREATE = "groups:create"
    GROUPS_EDIT = "groups:edit"
    STUDENTS_READ = "students:read"
    STUDENTS_CREATE = "students:create"
    STUDENTS_EDIT = "students:edit"
    ATTENDANCE_READ = "attendance:read"


PERMISSION_CATALOG: frozenset[str] = frozenset(item.value for item in Permission)
FORBIDDEN = "Bu amal uchun ruxsat yo‘q"


def parse_permission(value: str | Permission) -> Permission:
    try:
        return Permission(value)
    except ValueError:
        raise DomainError("Noma’lum permission", 422) from None


def validate_permissions(values: Iterable[str]) -> list[str]:
    """Return a sorted, de-duplicated list or reject any unknown key."""
    return sorted({parse_permission(value).value for value in values})


def has_permission(person: Staff, permission: Permission) -> bool:
    if person.status != Status.ACTIVE:
        return False
    if person.role == Role.SUPERADMIN:
        return True
    if person.role == Role.ADMIN:
        return permission.value in person.permissions
    return False


def ensure_portal_session(identity: Identity, portal: Portal) -> None:
    if identity.session.portal != portal:
        raise DomainError("Ushbu panelga kirish taqiqlangan", 403)


def ensure_permissions(identity: Identity, required: Iterable[str | Permission]) -> None:
    for item in required:
        if not has_permission(identity.staff, parse_permission(item)):
            raise DomainError(FORBIDDEN, 403)


def ensure_superadmin(identity: Identity) -> None:
    if identity.staff.role != Role.SUPERADMIN or identity.staff.status != Status.ACTIVE:
        raise DomainError(FORBIDDEN, 403)


def ensure_teacher(identity: Identity) -> None:
    if identity.staff.role != Role.TEACHER or identity.staff.status != Status.ACTIVE:
        raise DomainError(FORBIDDEN, 403)


async def ensure_group_owner(
    session: AsyncSession, identity: Identity, group_id: uuid.UUID
) -> None:
    """Teacher must own the group; absent and foreign groups look identical."""
    ensure_teacher(identity)
    owned = await session.scalar(
        select(exists().where(Group.id == group_id, Group.teacher_id == identity.staff.id))
    )
    if not owned:
        raise DomainError("Guruh topilmadi", 404)


async def ensure_student_owner(
    session: AsyncSession, identity: Identity, student_id: uuid.UUID
) -> None:
    """Teacher must own the student's group; absent and foreign students look identical."""
    ensure_teacher(identity)
    owned = await session.scalar(
        select(
            exists().where(
                Student.id == student_id,
                Student.group_id == Group.id,
                Group.teacher_id == identity.staff.id,
            )
        )
    )
    if not owned:
        raise DomainError("Talaba topilmadi", 404)
