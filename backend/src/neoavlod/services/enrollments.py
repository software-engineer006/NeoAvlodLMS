"""Shared membership predicates, counts and transactional course assignment."""

import uuid

from sqlalchemy import ColumnElement, exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.selectable import Subquery

from neoavlod.errors import DomainError
from neoavlod.models import Group, Student, StudentGroupEnrollment
from neoavlod.models.common import Status
from neoavlod.services.family_lock import family_lock


def in_group(group_id: uuid.UUID, *, active: bool = True) -> ColumnElement[bool]:
    query = exists().where(
        StudentGroupEnrollment.student_id == Student.id,
        StudentGroupEnrollment.group_id == group_id,
        StudentGroupEnrollment.archived_at.is_(None),
    )
    if active:
        query = query.where(StudentGroupEnrollment.is_active.is_(True))
    return query.correlate(Student)


def active_counts() -> Subquery:
    return (
        select(StudentGroupEnrollment.group_id, func.count().label("active_count"))
        .join(Student, Student.id == StudentGroupEnrollment.student_id)
        .where(StudentGroupEnrollment.is_active.is_(True), Student.status == Status.ACTIVE)
        .group_by(StudentGroupEnrollment.group_id)
        .subquery()
    )


async def active_count(session: AsyncSession, group_id: uuid.UUID) -> int:
    return (
        await session.scalar(
            select(func.count())
            .select_from(Student)
            .where(in_group(group_id), Student.status == Status.ACTIVE)
        )
        or 0
    )


async def assign_group(
    session: AsyncSession,
    student_id: uuid.UUID,
    group_id: uuid.UUID,
    *,
    active: bool = True,
) -> None:
    await family_lock(session, student_id)
    learner = await session.scalar(
        select(Student).where(Student.id == student_id).with_for_update()
    )
    if learner is None:
        raise DomainError("Talaba topilmadi", 404)
    group = await session.scalar(select(Group).where(Group.id == group_id).with_for_update())
    if group is None:
        raise DomainError("Guruh topilmadi", 404)
    membership = await session.scalar(
        select(StudentGroupEnrollment)
        .where(
            StudentGroupEnrollment.student_id == student_id,
            StudentGroupEnrollment.group_id == group_id,
        )
        .with_for_update()
    )
    if active and (membership is None or not membership.is_active):
        if group.status != Status.ACTIVE:
            raise DomainError("Guruh faol emas", 409)
        if (
            learner.status == Status.ACTIVE
            and await active_count(session, group_id) >= group.max_students
        ):
            raise DomainError("Guruhda bo‘sh joy yo‘q", 409)
    if membership is None:
        if not active:
            raise DomainError("Guruhga biriktirish topilmadi", 404)
        session.add(StudentGroupEnrollment(student_id=student_id, group_id=group_id))
    else:
        membership.is_active = active
    await session.commit()


async def update_metadata(
    session: AsyncSession,
    student_id: uuid.UUID,
    group_id: uuid.UUID,
    fields: dict[str, str | None],
) -> None:
    await family_lock(session, student_id)
    learner = await session.scalar(
        select(Student.id).where(Student.id == student_id).with_for_update()
    )
    if learner is None:
        raise DomainError("Talaba topilmadi", 404)
    membership = await session.scalar(
        select(StudentGroupEnrollment)
        .where(
            StudentGroupEnrollment.student_id == student_id,
            StudentGroupEnrollment.group_id == group_id,
        )
        .with_for_update()
    )
    if membership is None:
        raise DomainError("Guruhga biriktirish topilmadi", 404)
    for key, value in fields.items():
        if key not in {"level", "mygov_status", "notes"}:
            raise DomainError("Kurs maydoni yaroqsiz", 422)
        setattr(membership, key, value)
    await session.commit()
