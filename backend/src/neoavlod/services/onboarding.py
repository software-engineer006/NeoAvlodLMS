import re
import uuid
from datetime import UTC, datetime

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from neoavlod.errors import DomainError
from neoavlod.models import Parent, Staff, Student, SystemSettings
from neoavlod.models.common import Status, link_expiry

LinkEntity = Staff | Parent | Student
_models: dict[str, type[Staff] | type[Parent] | type[Student]] = {
    "staff": Staff,
    "parent": Parent,
    "student": Student,
}


class LinkState(BaseModel):
    connected: bool
    expired: bool
    deep_link: str | None
    expires_at: datetime | None


def entity_kind(entity: LinkEntity) -> str:
    if isinstance(entity, Staff):
        return "staff"
    return "parent" if isinstance(entity, Parent) else "student"


async def link_state(session: AsyncSession, entity: LinkEntity) -> LinkState:
    await session.flush()
    if entity.telegram_id is not None:
        return LinkState(connected=True, expired=False, deep_link=None, expires_at=None)
    expired = entity.auth_used_at is not None or entity.auth_expires_at <= datetime.now(UTC)
    if expired:
        return LinkState(
            connected=False, expired=True, deep_link=None, expires_at=entity.auth_expires_at
        )
    settings = await session.get(SystemSettings, 1)
    if settings is None or not settings.bot_username or not settings.bot_token_encrypted:
        raise DomainError("Telegram bot avval sozlanishi kerak", 503)
    if re.fullmatch(r"[A-Za-z0-9_]{5,32}", settings.bot_username) is None:
        raise DomainError("Telegram bot username noto‘g‘ri sozlangan", 503)
    payload = f"{entity_kind(entity)}_{entity.auth_uuid}"
    return LinkState(
        connected=False,
        expired=False,
        deep_link=f"https://t.me/{settings.bot_username}?start={payload}",
        expires_at=entity.auth_expires_at,
    )


async def rotate_staff_link(session: AsyncSession, staff_id: uuid.UUID) -> LinkState:
    person = await session.scalar(
        select(Staff)
        .where(Staff.id == staff_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if person is None:
        raise DomainError("Xodim topilmadi", 404)
    if person.status != Status.ACTIVE:
        raise DomainError("Faol bo‘lmagan xodimga havola berilmaydi", 409)
    if person.telegram_id is not None:
        raise DomainError("Xodim Telegramga allaqachon ulangan", 409)
    person.auth_uuid = uuid.uuid4()
    person.auth_expires_at = link_expiry()
    person.auth_used_at = None
    return await link_state(session, person)


async def rotate_student_link(session: AsyncSession, student_id: uuid.UUID) -> LinkState:
    learner = await session.scalar(
        select(Student)
        .where(Student.id == student_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if learner is None:
        raise DomainError("Talaba topilmadi", 404)
    if learner.status != Status.ACTIVE:
        raise DomainError("Faol bo‘lmagan talabaga havola berilmaydi", 409)
    if learner.telegram_id is not None:
        raise DomainError("Talaba Telegramga allaqachon ulangan", 409)
    learner.auth_uuid = uuid.uuid4()
    learner.auth_expires_at = link_expiry()
    learner.auth_used_at = None
    return await link_state(session, learner)


async def rotate_parent_link(session: AsyncSession, parent_id: uuid.UUID) -> LinkState:
    guardian = await session.scalar(
        select(Parent)
        .where(Parent.id == parent_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if guardian is None:
        raise DomainError("Ota-ona topilmadi", 404)
    if guardian.telegram_id is not None:
        raise DomainError("Ota-ona Telegramga allaqachon ulangan", 409)
    guardian.auth_uuid = uuid.uuid4()
    guardian.auth_expires_at = link_expiry()
    guardian.auth_used_at = None
    return await link_state(session, guardian)


async def resolve_link(session: AsyncSession, payload: str) -> LinkEntity:
    kind, separator, raw_uuid = payload.partition("_")
    if not separator or kind not in _models or len(payload) > 64:
        raise DomainError("Havola yaroqsiz", 400)
    try:
        token = uuid.UUID(raw_uuid)
    except ValueError:
        raise DomainError("Havola yaroqsiz", 400) from None
    model = _models[kind]
    entity: LinkEntity | None = await session.scalar(
        select(model)
        .where(model.auth_uuid == token)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if entity is None or entity.auth_expires_at <= datetime.now(UTC):
        raise DomainError("Havola yaroqsiz yoki muddati tugagan", 400)
    if entity.telegram_id is not None or entity.auth_used_at is not None:
        raise DomainError("Havola allaqachon ishlatilgan", 409)
    if isinstance(entity, (Staff, Student)) and entity.status != Status.ACTIVE:
        raise DomainError("Hisob faol emas", 403)
    return entity


async def link_telegram_account(
    session: AsyncSession, payload: str, telegram_id: int
) -> tuple[LinkEntity, str]:
    if telegram_id <= 0:
        raise DomainError("Telegram ID yaroqsiz", 400)

    entity = await resolve_link(session, payload)

    staff_match = await session.scalar(
        select(Staff.id).where(Staff.telegram_id == telegram_id)
    )
    parent_match = await session.scalar(
        select(Parent.id).where(Parent.telegram_id == telegram_id)
    )
    student_match = await session.scalar(
        select(Student.id).where(Student.telegram_id == telegram_id)
    )
    if (
        (staff_match is not None and staff_match != entity.id)
        or (parent_match is not None and parent_match != entity.id)
        or (student_match is not None and student_match != entity.id)
    ):
        raise DomainError(
            "Ushbu Telegram hisobi allaqachon boshqa foydalanuvchiga biriktirilgan", 409
        )

    entity.telegram_id = telegram_id
    entity.auth_used_at = datetime.now(UTC)
    await session.flush()

    kind = entity_kind(entity)
    if kind == "staff":
        msg = (
            f"Hisobingiz muvaffaqiyatli bog‘landi, {entity.first_name} {entity.last_name}! "
            "Endi tizimga kirishda Telegram orqali bir martalik tasdiqlash kodini olasiz."
        )
    elif kind == "parent":
        msg = (
            f"Hisobingiz muvaffaqiyatli bog‘landi, {entity.first_name} {entity.last_name}! "
            "Farzandingiz davomati haqidagi bildirishnomalar shu yerga yuboriladi."
        )
    else:
        msg = f"Hisobingiz muvaffaqiyatli bog‘landi, {entity.first_name} {entity.last_name}!"

    return entity, msg
