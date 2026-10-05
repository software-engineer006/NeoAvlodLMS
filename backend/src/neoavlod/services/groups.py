import uuid
from dataclasses import dataclass
from datetime import time
from decimal import Decimal

from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from neoavlod.errors import DomainError
from neoavlod.models import Attendance, Group, Role, Staff, Student, Subject
from neoavlod.models.common import Status


@dataclass(frozen=True)
class GroupRow:
    group: Group
    current_students: int


@dataclass(frozen=True)
class GroupPage:
    items: list[GroupRow]
    total: int
    page: int
    page_size: int


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


async def get_group(
    session: AsyncSession, group_id: uuid.UUID, *, lock: bool = False
) -> Group:
    query = select(Group).where(Group.id == group_id).execution_options(populate_existing=True)
    if lock:
        query = query.with_for_update()
    group = await session.scalar(query)
    if group is None:
        raise DomainError("Guruh topilmadi", 404)
    return group


async def get_group_row(session: AsyncSession, group_id: uuid.UUID) -> GroupRow:
    active_count = (
        await session.scalar(
            select(func.count())
            .select_from(Student)
            .where(Student.group_id == group_id, Student.status == Status.ACTIVE)
        )
        or 0
    )
    query = (
        select(Group)
        .where(Group.id == group_id)
        .options(joinedload(Group.subject), joinedload(Group.teacher))
    )
    group = await session.scalar(query)
    if group is None:
        raise DomainError("Guruh topilmadi", 404)
    return GroupRow(group=group, current_students=int(active_count))


async def validate_subject(session: AsyncSession, subject_id: uuid.UUID) -> Subject:
    subject = await session.get(Subject, subject_id)
    if subject is None:
        raise DomainError("Fan topilmadi", 404)
    if not subject.is_active:
        raise DomainError("Tanlangan fan faol emas", 409)
    return subject


async def validate_teacher(session: AsyncSession, teacher_id: uuid.UUID) -> Staff:
    teacher = await session.get(Staff, teacher_id)
    if teacher is None:
        raise DomainError("O‘qituvchi topilmadi", 404)
    if teacher.role != Role.TEACHER:
        raise DomainError("Xodim o‘qituvchi roliga ega emas", 422)
    if teacher.status != Status.ACTIVE:
        raise DomainError("O‘qituvchi faol emas", 409)
    return teacher


async def list_groups(
    session: AsyncSession,
    *,
    search: str | None = None,
    subject_id: uuid.UUID | None = None,
    teacher_id: uuid.UUID | None = None,
    status: Status | None = None,
    day_of_week: int | None = None,
    page: int = 1,
    page_size: int = 20,
) -> GroupPage:
    filters: list[ColumnElement[bool]] = []
    if search:
        clean = _escape_like(search.strip())
        filters.append(
            or_(
                Group.name.ilike(f"%{clean}%", escape="\\"),
                Group.room_number.ilike(f"%{clean}%", escape="\\"),
            )
        )
    if subject_id is not None:
        filters.append(Group.subject_id == subject_id)
    if teacher_id is not None:
        filters.append(Group.teacher_id == teacher_id)
    if status is not None:
        filters.append(Group.status == status)
    if day_of_week is not None:
        filters.append(Group.days_of_week.contains([day_of_week]))

    total = await session.scalar(select(func.count()).select_from(Group).where(*filters)) or 0

    active_sub = (
        select(
            Student.group_id,
            func.count().label("active_count"),
        )
        .where(Student.status == Status.ACTIVE)
        .group_by(Student.group_id)
        .subquery()
    )
    count_col = func.coalesce(active_sub.c.active_count, 0)

    stmt = (
        select(Group, count_col)
        .outerjoin(active_sub, Group.id == active_sub.c.group_id)
        .options(joinedload(Group.subject), joinedload(Group.teacher))
        .where(*filters)
        .order_by(func.lower(Group.name), Group.id)
        .limit(page_size)
        .offset((page - 1) * page_size)
    )

    result = await session.execute(stmt)
    rows = [GroupRow(group=item[0], current_students=int(item[1])) for item in result.all()]
    return GroupPage(items=rows, total=total, page=page, page_size=page_size)


async def create_group(
    session: AsyncSession,
    *,
    name: str,
    subject_id: uuid.UUID,
    teacher_id: uuid.UUID,
    monthly_price: Decimal,
    max_students: int,
    days_of_week: list[int],
    start_time: time,
    end_time: time,
    room_number: str,
) -> GroupRow:
    await validate_subject(session, subject_id)
    await validate_teacher(session, teacher_id)
    group = Group(
        name=name,
        subject_id=subject_id,
        teacher_id=teacher_id,
        monthly_price=monthly_price,
        max_students=max_students,
        days_of_week=days_of_week,
        start_time=start_time,
        end_time=end_time,
        room_number=room_number,
        status=Status.ACTIVE,
    )
    session.add(group)
    await session.commit()
    return await get_group_row(session, group.id)


async def update_group(
    session: AsyncSession,
    group_id: uuid.UUID,
    *,
    name: str | None = None,
    subject_id: uuid.UUID | None = None,
    teacher_id: uuid.UUID | None = None,
    monthly_price: Decimal | None = None,
    max_students: int | None = None,
    days_of_week: list[int] | None = None,
    start_time: time | None = None,
    end_time: time | None = None,
    room_number: str | None = None,
) -> GroupRow:
    group = await get_group(session, group_id, lock=True)

    if subject_id is not None and subject_id != group.subject_id:
        await validate_subject(session, subject_id)
        group.subject_id = subject_id

    if teacher_id is not None and teacher_id != group.teacher_id:
        await validate_teacher(session, teacher_id)
        group.teacher_id = teacher_id

    if max_students is not None:
        active_count = (
            await session.scalar(
                select(func.count())
                .select_from(Student)
                .where(Student.group_id == group_id, Student.status == Status.ACTIVE)
            )
            or 0
        )
        if max_students < active_count:
            msg = (
                f"Guruhdagi faol talabalar soni ({active_count}) "
                f"yangi sig‘imdan ({max_students}) ko‘p"
            )
            raise DomainError(msg, 409)
        group.max_students = max_students

    if start_time is not None or end_time is not None:
        eff_start = start_time if start_time is not None else group.start_time
        eff_end = end_time if end_time is not None else group.end_time
        if eff_start >= eff_end:
            raise DomainError("Dars boshlanish vaqti tugash vaqtidan oldin bo‘lishi kerak", 422)
        if start_time is not None:
            group.start_time = start_time
        if end_time is not None:
            group.end_time = end_time

    if name is not None:
        group.name = name
    if monthly_price is not None:
        group.monthly_price = monthly_price
    if days_of_week is not None:
        group.days_of_week = days_of_week
    if room_number is not None:
        group.room_number = room_number

    await session.commit()
    return await get_group_row(session, group_id)


async def set_group_active(
    session: AsyncSession, group_id: uuid.UUID, *, active: bool
) -> GroupRow:
    group = await get_group(session, group_id, lock=True)
    if active:
        await validate_subject(session, group.subject_id)
        await validate_teacher(session, group.teacher_id)
        group.status = Status.ACTIVE
    else:
        group.status = Status.INACTIVE
    await session.commit()
    return await get_group_row(session, group_id)


async def delete_group(session: AsyncSession, group_id: uuid.UUID) -> None:
    group = await get_group(session, group_id, lock=True)
    student_count = (
        await session.scalar(
            select(func.count()).select_from(Student).where(Student.group_id == group_id)
        )
        or 0
    )
    if student_count > 0:
        msg = (
            f"Talabalar bog‘langan guruhni o‘chirib bo‘lmaydi "
            f"({student_count} ta talaba mavjud); nofaol qiling"
        )
        raise DomainError(msg, 409)
    attendance_count = (
        await session.scalar(
            select(func.count()).select_from(Attendance).where(Attendance.group_id == group_id)
        )
        or 0
    )
    if attendance_count > 0:
        raise DomainError(
            "Davomat yozuvlari mavjud bo‘lgan guruhni o‘chirib bo‘lmaydi; nofaol qiling",
            409,
        )
    await session.delete(group)
    await session.commit()
