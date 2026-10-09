import re
import uuid
from datetime import UTC, datetime

from pydantic import BaseModel, SecretStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from neoavlod.errors import DomainError
from neoavlod.models import Parent, Role, Staff, Student, SystemSettings
from neoavlod.models.common import Status, link_expiry
from neoavlod.security.secrets import decrypt_token
from neoavlod.settings import Settings

LinkEntity = Staff | Parent | Student
_models: dict[str, type[Staff] | type[Parent] | type[Student]] = {
    "staff": Staff,
    "parent": Parent,
    "student": Student,
}


class LinkState(BaseModel):
    connected: bool
    expired: bool
    is_expired: bool = False
    deep_link: str | None
    expires_at: datetime | None

    def model_post_init(self, context: object) -> None:
        object.__setattr__(self, "is_expired", self.expired)


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
    if settings is None or not settings.bot_username:
        raise DomainError(
            "Telegram bot username sozlanmagan; Bot sozlamalarida username kiriting", 503
        )
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
        raise DomainError(
            "Havola allaqachon ishlatilgan. Parolingizni unutgan bo‘lsangiz, login sahifasidagi "
            "«Parolni unutdingizmi?» havolasidan foydalaning.",
            409,
        )
    if isinstance(entity, (Staff, Student)) and entity.status != Status.ACTIVE:
        raise DomainError("Hisob faol emas", 403)
    return entity


async def link_telegram_account(
    session: AsyncSession,
    payload: str,
    telegram_id: int,
    settings: Settings | None = None,
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
    display_name = f"{entity.first_name} {entity.last_name or ''}".strip()
    if kind == "staff":
        assert isinstance(entity, Staff)
        if entity.role == Role.TEACHER:
            portal_url = settings.teacher_origin if settings else "https://teacher.eduneo.uz"
            portal_name = "O‘qituvchi portali"
        else:
            portal_url = settings.admin_origin if settings else "https://admin.eduneo.uz"
            portal_name = "Admin portali"

        temp_pw: str | None = None
        if (
            entity.temporary_password_encrypted is not None
            and (
                entity.temporary_password_expires_at is None
                or entity.temporary_password_expires_at > datetime.now(UTC)
            )
        ):
            try:
                if settings is not None:
                    temp_pw = decrypt_token(entity.temporary_password_encrypted, settings)
                else:
                    test_settings = Settings(
                        database_url=SecretStr("postgresql+asyncpg://user:pass@localhost/db"),
                        environment="test",
                    )
                    temp_pw = decrypt_token(entity.temporary_password_encrypted, test_settings)
            except Exception:
                temp_pw = None

        if temp_pw:
            msg = (
                f"Assalomu alaykum, {display_name}!\n"
                f"Hisobingiz muvaffaqiyatli bog‘landi.\n\n"
                f"{portal_name}: {portal_url}\n"
                f"Login: {entity.username}\n"
                f"Vaqtinchalik parol: {temp_pw}\n\n"
                "Parolingizni yangilab qo‘ying! Tizimga kirgach parolingizni darhol yangilang."
            )
        else:
            msg = (
                f"Hisobingiz muvaffaqiyatli bog‘landi, {display_name}!\n"
                f"{portal_name}: {portal_url}\n"
                f"Login: {entity.username}\n\n"
                f"Endi tizimga kirishda Telegram orqali bir martalik tasdiqlash kodini olasiz."
            )
    elif kind == "parent":
        msg = (
            f"Hisobingiz muvaffaqiyatli bog‘landi, {display_name}!\n"
            "Farzandingiz davomati haqidagi bildirishnomalar shu yerga yuboriladi."
        )
    else:
        msg = f"Hisobingiz muvaffaqiyatli bog‘landi, {display_name}!"

    return entity, msg
