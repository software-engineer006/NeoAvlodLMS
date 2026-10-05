import uuid
from dataclasses import dataclass

from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from neoavlod.errors import DomainError
from neoavlod.models import Attendance, Group, Parent, Student
from neoavlod.models.common import Status


@dataclass(frozen=True)
class StudentPage:
    items: list[Student]
    total: int
    page: int
    page_size: int


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


async def get_student_for_update(session: AsyncSession, student_id: uuid.UUID) -> Student:
    query = (
        select(Student)
        .where(Student.id == student_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    learner = await session.scalar(query)
    if learner is None:
        raise DomainError("Talaba topilmadi", 404)
    return learner


async def get_student(session: AsyncSession, student_id: uuid.UUID) -> Student:
    query = (
        select(Student)
        .where(Student.id == student_id)
        .options(
            joinedload(Student.parent),
            joinedload(Student.group),
        )
        .execution_options(populate_existing=True)
    )
    learner = await session.scalar(query)
    if learner is None:
        raise DomainError("Talaba topilmadi", 404)
    return learner


async def list_students(
    session: AsyncSession,
    *,
    search: str | None = None,
    group_id: uuid.UUID | None = None,
    status: Status | None = None,
    page: int = 1,
    page_size: int = 20,
) -> StudentPage:
    filters: list[ColumnElement[bool]] = []
    if search:
        clean = _escape_like(search.strip())
        filters.append(
            or_(
                Student.first_name.ilike(f"%{clean}%", escape="\\"),
                Student.last_name.ilike(f"%{clean}%", escape="\\"),
                Student.phone.ilike(f"%{clean}%", escape="\\"),
                Parent.phone.ilike(f"%{clean}%", escape="\\"),
            )
        )
    if group_id is not None:
        filters.append(Student.group_id == group_id)
    if status is not None:
        filters.append(Student.status == status)

    total = (
        await session.scalar(
            select(func.count())
            .select_from(Student)
            .join(Parent, Student.parent_id == Parent.id)
            .where(*filters)
        )
        or 0
    )

    stmt = (
        select(Student)
        .join(Parent, Student.parent_id == Parent.id)
        .options(joinedload(Student.parent), joinedload(Student.group))
        .where(*filters)
        .order_by(func.lower(Student.first_name), func.lower(Student.last_name), Student.id)
        .limit(page_size)
        .offset((page - 1) * page_size)
    )
    items = list((await session.scalars(stmt)).all())
    return StudentPage(items=items, total=total, page=page, page_size=page_size)


async def create_student(
    session: AsyncSession,
    *,
    first_name: str,
    last_name: str,
    phone: str,
    age: int,
    group_id: uuid.UUID,
    parent_first_name: str,
    parent_last_name: str,
    parent_phone: str,
) -> Student:
    # Lock group row to serialize concurrent enrollments against capacity
    group_query = (
        select(Group)
        .where(Group.id == group_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    group = await session.scalar(group_query)
    if group is None:
        raise DomainError("Guruh topilmadi", 404)
    if group.status != Status.ACTIVE:
        raise DomainError("Guruh faol emas", 409)

    active_count = (
        await session.scalar(
            select(func.count())
            .select_from(Student)
            .where(Student.group_id == group_id, Student.status == Status.ACTIVE)
        )
        or 0
    )
    if active_count >= group.max_students:
        raise DomainError("Guruhda bo‘sh joy yo‘q", 409)

    guardian = Parent(
        first_name=parent_first_name,
        last_name=parent_last_name,
        phone=parent_phone,
    )
    session.add(guardian)
    await session.flush()

    learner = Student(
        first_name=first_name,
        last_name=last_name,
        phone=phone,
        age=age,
        group_id=group_id,
        parent_id=guardian.id,
        status=Status.ACTIVE,
    )
    session.add(learner)
    await session.commit()
    return await get_student(session, learner.id)


async def update_student(
    session: AsyncSession,
    student_id: uuid.UUID,
    *,
    first_name: str | None = None,
    last_name: str | None = None,
    phone: str | None = None,
    age: int | None = None,
    parent_first_name: str | None = None,
    parent_last_name: str | None = None,
    parent_phone: str | None = None,
) -> Student:
    learner = await get_student_for_update(session, student_id)
    if first_name is not None:
        learner.first_name = first_name
    if last_name is not None:
        learner.last_name = last_name
    if phone is not None:
        learner.phone = phone
    if age is not None:
        learner.age = age

    if any(p is not None for p in (parent_first_name, parent_last_name, parent_phone)):
        guardian = await session.scalar(
            select(Parent)
            .where(Parent.id == learner.parent_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if guardian is not None:
            if parent_first_name is not None:
                guardian.first_name = parent_first_name
            if parent_last_name is not None:
                guardian.last_name = parent_last_name
            if parent_phone is not None:
                guardian.phone = parent_phone

    await session.commit()
    return await get_student(session, student_id)


async def transfer_student(
    session: AsyncSession,
    student_id: uuid.UUID,
    target_group_id: uuid.UUID,
) -> Student:
    learner = await get_student_for_update(session, student_id)
    if learner.group_id == target_group_id:
        return await get_student(session, student_id)

    source_group_id = learner.group_id
    # Deterministic lock ordering to prevent deadlocks
    ordered_ids = sorted([source_group_id, target_group_id])
    groups_by_id: dict[uuid.UUID, Group] = {}
    for gid in ordered_ids:
        group_query = (
            select(Group)
            .where(Group.id == gid)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        found = await session.scalar(group_query)
        if found is None:
            raise DomainError("Guruh topilmadi", 404)
        groups_by_id[gid] = found

    target_group = groups_by_id[target_group_id]
    if target_group.status != Status.ACTIVE:
        raise DomainError("Mo‘ljallangan guruh faol emas", 409)

    if learner.status == Status.ACTIVE:
        active_target_count = (
            await session.scalar(
                select(func.count())
                .select_from(Student)
                .where(Student.group_id == target_group_id, Student.status == Status.ACTIVE)
            )
            or 0
        )
        if active_target_count >= target_group.max_students:
            raise DomainError("Guruhda bo‘sh joy yo‘q", 409)

    learner.group_id = target_group_id
    await session.commit()
    return await get_student(session, student_id)


async def set_student_active(
    session: AsyncSession,
    student_id: uuid.UUID,
    *,
    active: bool,
) -> Student:
    learner = await get_student_for_update(session, student_id)
    if active:
        group_query = (
            select(Group)
            .where(Group.id == learner.group_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        group = await session.scalar(group_query)
        if group is None or group.status != Status.ACTIVE:
            raise DomainError("Bog‘langan guruh faol emas", 409)

        if learner.status != Status.ACTIVE:
            active_count = (
                await session.scalar(
                    select(func.count())
                    .select_from(Student)
                    .where(Student.group_id == learner.group_id, Student.status == Status.ACTIVE)
                )
                or 0
            )
            if active_count >= group.max_students:
                raise DomainError("Guruhda bo‘sh joy yo‘q", 409)
            learner.status = Status.ACTIVE
    else:
        learner.status = Status.INACTIVE

    await session.commit()
    return await get_student(session, student_id)


async def delete_student(session: AsyncSession, student_id: uuid.UUID) -> None:
    learner = await get_student_for_update(session, student_id)
    attendance_count = (
        await session.scalar(
            select(func.count())
            .select_from(Attendance)
            .where(Attendance.student_id == student_id)
        )
        or 0
    )
    if attendance_count > 0:
        msg = (
            "Davomat yozuvlari mavjud bo‘lgan talabani o‘chirib bo‘lmaydi; nofaol qiling"
        )
        raise DomainError(msg, 409)

    await session.delete(learner)
    await session.commit()
