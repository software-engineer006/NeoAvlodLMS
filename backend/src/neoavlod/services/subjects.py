import uuid
from dataclasses import dataclass

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from neoavlod.errors import DomainError
from neoavlod.models import Group, Subject
from neoavlod.models.common import Status

DUPLICATE = "Bunday nomli fan allaqachon mavjud"
NAME_LOCK = 0x4E454F03


@dataclass(frozen=True)
class SubjectRow:
    subject: Subject
    active_groups: int
    total_groups: int


@dataclass(frozen=True)
class SubjectPage:
    items: list[SubjectRow]
    total: int
    page: int
    page_size: int


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


async def _counts(session: AsyncSession, subject_id: uuid.UUID) -> tuple[int, int]:
    row = (
        await session.execute(
            select(
                func.count().filter(Group.status == Status.ACTIVE),
                func.count(),
            ).where(Group.subject_id == subject_id)
        )
    ).one()
    return int(row[0]), int(row[1])


async def _row(session: AsyncSession, subject: Subject) -> SubjectRow:
    active, total = await _counts(session, subject.id)
    return SubjectRow(subject, active, total)


async def _ensure_name_free(
    session: AsyncSession, name: str, *, exclude: uuid.UUID | None = None
) -> None:
    await session.execute(select(func.pg_advisory_xact_lock(NAME_LOCK)))
    query = select(Subject.id).where(func.lower(Subject.name) == name.lower())
    if exclude is not None:
        query = query.where(Subject.id != exclude)
    if await session.scalar(query) is not None:
        raise DomainError(DUPLICATE, 409)


async def list_subjects(
    session: AsyncSession,
    *,
    search: str | None,
    is_active: bool | None,
    page: int,
    page_size: int,
) -> SubjectPage:
    filters: list[ColumnElement[bool]] = []
    if search:
        filters.append(Subject.name.ilike(f"%{_escape_like(search.strip())}%", escape="\\"))
    if is_active is not None:
        filters.append(Subject.is_active == is_active)
    total = await session.scalar(select(func.count()).select_from(Subject).where(*filters)) or 0
    subjects = await session.scalars(
        select(Subject)
        .where(*filters)
        .order_by(func.lower(Subject.name), Subject.id)
        .limit(page_size)
        .offset((page - 1) * page_size)
    )
    return SubjectPage([await _row(session, item) for item in subjects], total, page, page_size)


async def get_subject(
    session: AsyncSession, subject_id: uuid.UUID, *, lock: bool = False
) -> Subject:
    query = (
        select(Subject).where(Subject.id == subject_id).execution_options(populate_existing=True)
    )
    subject = await session.scalar(query.with_for_update() if lock else query)
    if subject is None:
        raise DomainError("Fan topilmadi", 404)
    return subject


async def read_subject(session: AsyncSession, subject_id: uuid.UUID) -> SubjectRow:
    return await _row(session, await get_subject(session, subject_id))


async def create_subject(
    session: AsyncSession, *, name: str, description: str | None
) -> SubjectRow:
    await _ensure_name_free(session, name)
    subject = Subject(name=name, description=description, is_active=True)
    session.add(subject)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise DomainError(DUPLICATE, 409) from None
    return SubjectRow(subject, 0, 0)


async def update_subject(
    session: AsyncSession,
    subject_id: uuid.UUID,
    *,
    name: str | None,
    description: str | None,
    description_given: bool,
) -> SubjectRow:
    subject = await get_subject(session, subject_id, lock=True)
    if name is not None and name != subject.name:
        await _ensure_name_free(session, name, exclude=subject.id)
        subject.name = name
    if description_given:
        subject.description = description
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise DomainError(DUPLICATE, 409) from None
    return await _row(session, subject)


async def set_subject_active(
    session: AsyncSession, subject_id: uuid.UUID, *, active: bool
) -> SubjectRow:
    # The row lock serializes this check with group creation (which locks the subject too).
    subject = await get_subject(session, subject_id, lock=True)
    if not active:
        in_use, _ = await _counts(session, subject.id)
        if in_use:
            raise DomainError(
                f"Fan {in_use} ta faol guruhda ishlatilmoqda; avval guruhlarni o‘zgartiring", 409
            )
    subject.is_active = active
    await session.commit()
    return await _row(session, subject)


async def delete_subject(session: AsyncSession, subject_id: uuid.UUID) -> None:
    subject = await get_subject(session, subject_id, lock=True)
    _, total = await _counts(session, subject.id)
    if total:
        raise DomainError("Guruhlarga bog‘langan fanni o‘chirib bo‘lmaydi; nofaol qiling", 409)
    await session.delete(subject)
    await session.commit()
