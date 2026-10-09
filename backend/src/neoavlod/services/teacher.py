import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from neoavlod.errors import DomainError
from neoavlod.models import Group, Student
from neoavlod.models.common import Status
from neoavlod.security.rbac import ensure_group_owner, ensure_student_owner
from neoavlod.security.sessions import Identity


@dataclass(frozen=True)
class TeacherGroupRow:
    group: Group
    current_students: int


async def list_teacher_groups(
    session: AsyncSession,
    teacher: Identity,
    *,
    status: Status | None = None,
) -> list[TeacherGroupRow]:
    filters = [Group.teacher_id == teacher.staff.id]
    if status is not None:
        filters.append(Group.status == status)

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
        .options(joinedload(Group.subject))
        .where(*filters)
        .order_by(Group.status, func.lower(Group.name), Group.id)
    )

    result = await session.execute(stmt)
    return [
        TeacherGroupRow(group=item[0], current_students=int(item[1]))
        for item in result.all()
    ]


async def get_teacher_group(
    session: AsyncSession,
    teacher: Identity,
    group_id: uuid.UUID,
) -> TeacherGroupRow:
    await ensure_group_owner(session, teacher, group_id)
    active_count = (
        await session.scalar(
            select(func.count())
            .select_from(Student)
            .where(Student.group_id == group_id, Student.status == Status.ACTIVE)
        )
        or 0
    )
    group = await session.scalar(
        select(Group).where(Group.id == group_id).options(joinedload(Group.subject))
    )
    if group is None:
        raise DomainError("Guruh topilmadi", 404)
    return TeacherGroupRow(group=group, current_students=int(active_count))


async def list_group_students(
    session: AsyncSession,
    teacher: Identity,
    group_id: uuid.UUID,
    *,
    status: Status | None = None,
) -> list[Student]:
    await ensure_group_owner(session, teacher, group_id)
    filters = [Student.group_id == group_id]
    if status is not None:
        filters.append(Student.status == status)

    stmt = (
        select(Student)
        .where(*filters)
        .options(
            joinedload(Student.parent),
            joinedload(Student.group).joinedload(Group.subject),
            joinedload(Student.group).joinedload(Group.teacher),
        )
        .order_by(Student.status, func.lower(Student.first_name), func.lower(Student.last_name))
    )
    return list((await session.scalars(stmt)).all())


async def get_teacher_student(
    session: AsyncSession,
    teacher: Identity,
    student_id: uuid.UUID,
) -> Student:
    await ensure_student_owner(session, teacher, student_id)
    stmt = (
        select(Student)
        .where(Student.id == student_id)
        .options(
            joinedload(Student.parent),
            joinedload(Student.group).joinedload(Group.subject),
            joinedload(Student.group).joinedload(Group.teacher),
        )
    )
    learner = await session.scalar(stmt)
    if learner is None:
        raise DomainError("Talaba topilmadi", 404)
    return learner
