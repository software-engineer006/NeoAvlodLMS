import uuid
from dataclasses import dataclass

import anyio
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from neoavlod.errors import DomainError
from neoavlod.models import Role, Staff
from neoavlod.models.common import Status
from neoavlod.security.passwords import hash_password, validate_password
from neoavlod.security.rbac import validate_permissions
from neoavlod.security.sessions import Identity
from neoavlod.services.passwords import revoke_account

FORBIDDEN = "Bu amal uchun ruxsat yo‘q"
DUPLICATE = "Username yoki telefon boshqa xodimga tegishli"
CREATABLE_ROLES = frozenset({Role.ADMIN, Role.TEACHER})
SUPERADMIN_LOCK = 0x4E454F02


@dataclass(frozen=True)
class StaffPage:
    items: list[Staff]
    total: int
    page: int
    page_size: int


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def ensure_can_manage(actor: Identity, target_role: Role) -> None:
    """staff:manage admins manage teachers only; admin/superadmin accounts need a superadmin."""
    if target_role != Role.TEACHER and actor.staff.role != Role.SUPERADMIN:
        raise DomainError(FORBIDDEN, 403)


def _permissions_for(role: Role, permissions: list[str] | None, actor: Identity) -> list[str]:
    if not permissions:
        return []
    if actor.staff.role != Role.SUPERADMIN:
        raise DomainError(FORBIDDEN, 403)
    if role != Role.ADMIN:
        raise DomainError("Permission faqat admin rolidagi xodimga biriktiriladi", 422)
    return validate_permissions(permissions)


async def list_staff(
    session: AsyncSession,
    *,
    search: str | None,
    role: Role | None,
    status: Status | None,
    page: int,
    page_size: int,
) -> StaffPage:
    filters = []
    if search:
        pattern = f"%{_escape_like(search.strip())}%"
        filters.append(
            or_(
                Staff.first_name.ilike(pattern, escape="\\"),
                Staff.last_name.ilike(pattern, escape="\\"),
                Staff.username.ilike(pattern, escape="\\"),
                Staff.phone.ilike(pattern, escape="\\"),
            )
        )
    if role is not None:
        filters.append(Staff.role == role)
    if status is not None:
        filters.append(Staff.status == status)
    total = await session.scalar(select(func.count()).select_from(Staff).where(*filters)) or 0
    rows = await session.scalars(
        select(Staff)
        .where(*filters)
        .order_by(Staff.created_at.desc(), Staff.id)
        .limit(page_size)
        .offset((page - 1) * page_size)
    )
    return StaffPage(list(rows), total, page, page_size)


async def get_staff(session: AsyncSession, staff_id: uuid.UUID, *, lock: bool = False) -> Staff:
    query = select(Staff).where(Staff.id == staff_id).execution_options(populate_existing=True)
    person = await session.scalar(query.with_for_update() if lock else query)
    if person is None:
        raise DomainError("Xodim topilmadi", 404)
    return person


async def create_staff(
    session: AsyncSession,
    actor: Identity,
    *,
    first_name: str,
    last_name: str,
    phone: str,
    username: str,
    password: str,
    role: Role,
    permissions: list[str] | None,
) -> Staff:
    if role not in CREATABLE_ROLES:
        raise DomainError("Bu rolda xodim yaratib bo‘lmaydi", 422)
    ensure_can_manage(actor, role)
    granted = _permissions_for(role, permissions, actor)
    try:
        validate_password(password)
    except ValueError as error:
        raise DomainError(str(error), 422) from None
    encoded = await anyio.to_thread.run_sync(hash_password, password)
    person = Staff(
        first_name=first_name,
        last_name=last_name,
        phone=phone,
        username=username,
        hashed_password=encoded,
        role=role,
        permissions=granted,
    )
    session.add(person)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise DomainError(DUPLICATE, 409) from None
    return person


async def update_staff(
    session: AsyncSession,
    actor: Identity,
    staff_id: uuid.UUID,
    *,
    first_name: str | None,
    last_name: str | None,
    phone: str | None,
    permissions: list[str] | None,
) -> Staff:
    person = await get_staff(session, staff_id, lock=True)
    ensure_can_manage(actor, person.role)
    if permissions is not None:
        if actor.staff.role != Role.SUPERADMIN:
            raise DomainError(FORBIDDEN, 403)
        if person.role != Role.ADMIN and permissions:
            raise DomainError("Permission faqat admin rolidagi xodimga biriktiriladi", 422)
        person.permissions = validate_permissions(permissions) if person.role == Role.ADMIN else []
    if first_name is not None:
        person.first_name = first_name
    if last_name is not None:
        person.last_name = last_name
    if phone is not None:
        person.phone = phone
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise DomainError(DUPLICATE, 409) from None
    return person


async def set_active(
    session: AsyncSession, actor: Identity, staff_id: uuid.UUID, *, active: bool
) -> Staff:
    # Serialize concurrent deactivations so the last active superadmin survives.
    await session.execute(select(func.pg_advisory_xact_lock(SUPERADMIN_LOCK)))
    person = await get_staff(session, staff_id, lock=True)
    if not active and person.id == actor.staff.id:
        raise DomainError("O‘zingizni o‘chirib bo‘lmaydi", 409)
    ensure_can_manage(actor, person.role)
    if active:
        person.status = Status.ACTIVE
        await session.commit()
        return person
    if person.role == Role.SUPERADMIN and person.status == Status.ACTIVE:
        remaining = await session.scalar(
            select(func.count())
            .select_from(Staff)
            .where(
                Staff.role == Role.SUPERADMIN,
                Staff.status == Status.ACTIVE,
                Staff.id != person.id,
            )
        )
        if not remaining:
            raise DomainError("Oxirgi faol superadminni o‘chirib bo‘lmaydi", 409)
    person.status = Status.INACTIVE
    await revoke_account(session, person.id)
    await session.commit()
    return person
