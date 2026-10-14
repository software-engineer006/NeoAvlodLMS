import uuid
from dataclasses import dataclass

from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy.sql.base import ExecutableOption

from neoavlod.audit_context import emit
from neoavlod.errors import DomainError
from neoavlod.models import Attendance, Group, Parent, Student, StudentGroupEnrollment
from neoavlod.models.common import Status
from neoavlod.services.enrollments import in_group
from neoavlod.services.family_lock import family_lock


def enrollment_loads() -> tuple[ExecutableOption, ExecutableOption]:
    return (
        selectinload(Student.enrollments)
        .joinedload(StudentGroupEnrollment.group)
        .joinedload(Group.subject),
        selectinload(Student.enrollments)
        .joinedload(StudentGroupEnrollment.group)
        .joinedload(Group.teacher),
    )


@dataclass(frozen=True)
class StudentPage:
    items: list[Student]
    total: int
    page: int
    page_size: int


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


async def get_student_for_update(session: AsyncSession, student_id: uuid.UUID) -> Student:
    await family_lock(session, student_id)
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
            *enrollment_loads(),
            joinedload(Student.parent),
            joinedload(Student.group).joinedload(Group.subject),
            joinedload(Student.group).joinedload(Group.teacher),
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
        filters.append(in_group(group_id))
    if status is not None:
        filters.append(Student.status == status)

    total = (
        await session.scalar(
            select(func.count())
            .select_from(Student)
            .outerjoin(Parent, Student.parent_id == Parent.id)
            .where(*filters)
        )
        or 0
    )

    stmt = (
        select(Student)
        .outerjoin(Parent, Student.parent_id == Parent.id)
        .options(
            *enrollment_loads(),
            joinedload(Student.parent),
            joinedload(Student.group).joinedload(Group.subject),
            joinedload(Student.group).joinedload(Group.teacher),
        )
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
    last_name: str | None,
    phone: str | None,
    age: int | None,
    group_id: uuid.UUID,
    parent_first_name: str | None,
    parent_last_name: str | None,
    parent_phone: str | None,
    school_grade: str | None = None,
    school_name: str | None = None,
    existing_parent_id: uuid.UUID | None = None,
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
            .where(in_group(group_id), Student.status == Status.ACTIVE)
        )
        or 0
    )
    if active_count >= group.max_students:
        raise DomainError("Guruhda bo‘sh joy yo‘q", 409)

    guardian = None
    if existing_parent_id is not None:
        if any(p is not None for p in (parent_first_name, parent_last_name, parent_phone)):
            raise DomainError("Mavjud ota-ona yoki yangi ma’lumotdan bittasini tanlang", 422)
        guardian = await session.scalar(
            select(Parent).where(Parent.id == existing_parent_id).with_for_update()
        )
        if guardian is None:
            raise DomainError("Ota-ona topilmadi", 404)
    if any(p is not None for p in (parent_first_name, parent_last_name, parent_phone)):
        if not all((parent_first_name, parent_last_name, parent_phone)):
            raise DomainError("Ota-ona ism, familiya va telefonini to‘liq kiriting", 422)
        guardian = Parent(
            first_name=parent_first_name, last_name=parent_last_name, phone=parent_phone
        )
        session.add(guardian)
        await session.flush()

    learner = Student(
        first_name=first_name,
        last_name=last_name,
        phone=phone,
        age=age,
        group_id=group_id,
        parent_id=guardian.id if guardian else None,
        school_grade=school_grade,
        school_name=school_name,
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
    school_fields: dict[str, str | None] | None = None,
    parent_assignment_specified: bool = False,
    parent_id: uuid.UUID | None = None,
) -> Student:
    if parent_assignment_specified or any(
        p is not None for p in (parent_first_name, parent_last_name, parent_phone)
    ):
        await family_lock(session, student_id)
    learner = await get_student_for_update(session, student_id)
    if parent_assignment_specified:
        if any(p is not None for p in (parent_first_name, parent_last_name, parent_phone)):
            raise DomainError("Ota-onani biriktirish va tahrirlashni alohida bajaring", 422)
        if parent_id is not None:
            found = await session.scalar(
                select(Parent.id).where(Parent.id == parent_id).with_for_update()
            )
            if found is None:
                raise DomainError("Ota-ona topilmadi", 404)
        learner.parent_id = parent_id
    for key, value in (school_fields or {}).items():
        if key not in {"school_grade", "school_name"}:
            raise DomainError("Maktab maydoni yaroqsiz", 422)
        setattr(learner, key, value)
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
        if guardian is None:
            if not all((parent_first_name, parent_last_name, parent_phone)):
                raise DomainError("Yangi ota-ona ism, familiya va telefonini to‘liq kiriting", 422)
            guardian = Parent(
                first_name=parent_first_name, last_name=parent_last_name, phone=parent_phone
            )
            session.add(guardian)
            await session.flush()
            learner.parent_id = guardian.id
        else:
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
    *,
    source_group_id: uuid.UUID | None = None,
    reason: str | None = None,
) -> Student:
    await family_lock(session, student_id)
    primary = await session.scalar(select(Student.group_id).where(Student.id == student_id))
    if primary is None:
        raise DomainError("Talaba topilmadi", 404)
    source = source_group_id or primary
    groups_by_id: dict[uuid.UUID, Group] = {}
    for gid in sorted({source, target_group_id}):
        found = await session.scalar(
            select(Group)
            .where(Group.id == gid)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if found is None:
            raise DomainError("Guruh topilmadi", 404)
        groups_by_id[gid] = found
    learner = await get_student_for_update(session, student_id)
    if source_group_id is None and learner.group_id != primary:
        raise DomainError("O‘quvchining guruhi o‘zgardi; qayta yuklang", 409)
    source_row = await session.scalar(
        select(StudentGroupEnrollment)
        .where(
            StudentGroupEnrollment.student_id == student_id,
            StudentGroupEnrollment.group_id == source,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    target_row = await session.scalar(
        select(StudentGroupEnrollment)
        .where(
            StudentGroupEnrollment.student_id == student_id,
            StudentGroupEnrollment.group_id == target_group_id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if source_row is None:
        raise DomainError("Manba guruhga biriktirish topilmadi", 404)
    if source == target_group_id:
        return await get_student(session, student_id)
    if not source_row.is_active:
        if target_row is not None and target_row.is_active:
            return await get_student(session, student_id)
        raise DomainError("Manba guruh biriktirishi faol emas", 409)
    target = groups_by_id[target_group_id]
    if target.status != Status.ACTIVE:
        raise DomainError("Mo‘ljallangan guruh faol emas", 409)
    if learner.status == Status.ACTIVE and (target_row is None or not target_row.is_active):
        count = (
            await session.scalar(
                select(func.count())
                .select_from(Student)
                .where(in_group(target_group_id), Student.status == Status.ACTIVE)
            )
            or 0
        )
        if count >= target.max_students:
            raise DomainError("Guruhda bo‘sh joy yo‘q", 409)
    new_target = target_row is None
    source_row.is_active = False
    if learner.group_id == source:
        if (learner.source_data or {}).get("notes") and "notes_group_id" not in (
            learner.source_data or {}
        ):
            learner.source_data = {**(learner.source_data or {}), "notes_group_id": str(source)}
        learner.group_id = target_group_id
        await session.flush()
        target_row = await session.scalar(
            select(StudentGroupEnrollment).where(
                StudentGroupEnrollment.student_id == student_id,
                StudentGroupEnrollment.group_id == target_group_id,
            )
        )
    if target_row is None:
        target_row = StudentGroupEnrollment(student_id=student_id, group_id=target_group_id)
        session.add(target_row)
    target_row.is_active = True
    if new_target and groups_by_id[source].subject_id == target.subject_id:
        target_row.level, target_row.mygov_status = source_row.level, source_row.mygov_status
        target_row.notes = source_row.notes
    await session.flush()
    if reason:
        await emit(
            session,
            "student.transferred",
            entity_type="student",
            entity_id=student_id,
            name=f"{learner.first_name} {learner.last_name or ''}".strip(),
            details={
                "reason": reason,
                "source_group": {"id": str(source), "name": groups_by_id[source].name},
                "target_group": {"id": str(target.id), "name": target.name},
                "parent_id": str(learner.parent_id) if learner.parent_id else None,
            },
        )
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
            .join(StudentGroupEnrollment, StudentGroupEnrollment.group_id == Group.id)
            .where(
                StudentGroupEnrollment.student_id == student_id,
                StudentGroupEnrollment.is_active.is_(True),
            )
            .order_by(Group.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        groups = list((await session.scalars(group_query)).all())
        if not groups or any(group.status != Status.ACTIVE for group in groups):
            raise DomainError("Bog‘langan guruh faol emas", 409)

        if learner.status != Status.ACTIVE:
            for group in groups:
                active_count = (
                    await session.scalar(
                        select(func.count())
                        .select_from(Student)
                        .where(in_group(group.id), Student.status == Status.ACTIVE)
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
            select(func.count()).select_from(Attendance).where(Attendance.student_id == student_id)
        )
        or 0
    )
    if attendance_count > 0:
        msg = "Davomat yozuvlari mavjud bo‘lgan talabani o‘chirib bo‘lmaydi; nofaol qiling"
        raise DomainError(msg, 409)

    await session.delete(learner)
    await session.commit()
