import uuid
from dataclasses import dataclass
from datetime import date, datetime

import httpx
from sqlalchemy import ColumnElement, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from neoavlod.database import Database
from neoavlod.errors import DomainError
from neoavlod.models import (
    Attendance,
    AttendanceBatch,
    AttendanceStatus,
    Group,
    NotificationOutbox,
    OutboxStatus,
    Staff,
    Student,
    SystemSettings,
)
from neoavlod.models.common import Status
from neoavlod.security.rbac import ensure_group_owner
from neoavlod.security.sessions import Identity
from neoavlod.services.outbox import dispatch_pending_outbox


@dataclass(frozen=True)
class AttendanceEntry:
    student_id: uuid.UUID
    student_first_name: str
    student_last_name: str
    status: AttendanceStatus | None
    note: str | None
    marked_at: datetime | None


@dataclass(frozen=True)
class AttendanceSheet:
    group_id: uuid.UUID
    date: date
    finalized: bool
    finalized_at: datetime | None
    items: list[AttendanceEntry]


@dataclass(frozen=True)
class DraftItem:
    student_id: uuid.UUID
    status: AttendanceStatus
    note: str | None = None


@dataclass(frozen=True)
class AdminAttendanceRow:
    attendance_id: uuid.UUID
    date: date
    group_id: uuid.UUID
    group_name: str
    teacher_id: uuid.UUID
    teacher_name: str
    student_id: uuid.UUID
    student_name: str
    status: AttendanceStatus
    note: str | None
    marked_at: datetime
    finalized: bool
    batch_id: uuid.UUID | None


@dataclass(frozen=True)
class AdminAttendancePage:
    items: list[AdminAttendanceRow]
    total: int
    page: int
    page_size: int


async def is_date_finalized(
    session: AsyncSession, group_id: uuid.UUID, target_date: date
) -> tuple[bool, datetime | None]:
    batch = await session.scalar(
        select(AttendanceBatch).where(
            AttendanceBatch.group_id == group_id,
            AttendanceBatch.date == target_date,
        )
    )
    if batch is not None:
        return True, batch.finalized_at
    return False, None


async def get_attendance_sheet(
    session: AsyncSession,
    teacher: Identity,
    group_id: uuid.UUID,
    target_date: date,
) -> AttendanceSheet:
    await ensure_group_owner(session, teacher, group_id)
    finalized, finalized_at = await is_date_finalized(session, group_id, target_date)

    students = list(
        (
            await session.scalars(
                select(Student)
                .where(Student.group_id == group_id, Student.status == Status.ACTIVE)
                .order_by(func.lower(Student.first_name), func.lower(Student.last_name))
            )
        ).all()
    )

    records = list(
        (
            await session.scalars(
                select(Attendance).where(
                    Attendance.group_id == group_id,
                    Attendance.date == target_date,
                )
            )
        ).all()
    )
    by_student = {r.student_id: r for r in records}

    entries = []
    for s in students:
        rec = by_student.get(s.id)
        entries.append(
            AttendanceEntry(
                student_id=s.id,
                student_first_name=s.first_name,
                student_last_name=s.last_name,
                status=rec.status if rec else None,
                note=rec.note if rec else None,
                marked_at=rec.updated_at if rec else None,
            )
        )

    return AttendanceSheet(
        group_id=group_id,
        date=target_date,
        finalized=finalized,
        finalized_at=finalized_at,
        items=entries,
    )


async def save_attendance_draft(
    session: AsyncSession,
    teacher: Identity,
    group_id: uuid.UUID,
    target_date: date,
    items: list[DraftItem],
) -> AttendanceSheet:
    await ensure_group_owner(session, teacher, group_id)
    finalized, _ = await is_date_finalized(session, group_id, target_date)
    if finalized:
        raise DomainError("Ushbu sana uchun davomat allaqachon yakunlangan", 409)

    valid_ids = set(
        (
            await session.scalars(
                select(Student.id).where(
                    Student.group_id == group_id,
                    Student.status == Status.ACTIVE,
                )
            )
        ).all()
    )

    for item in items:
        if item.student_id not in valid_ids:
            msg = f"Talaba ({item.student_id}) ushbu guruhga tegishli emas yoki faol emas"
            raise DomainError(msg, 422)

        note_clean = item.note.strip() if item.note else None
        if note_clean == "":
            note_clean = None

        stmt = (
            insert(Attendance)
            .values(
                group_id=group_id,
                student_id=item.student_id,
                date=target_date,
                status=item.status,
                note=note_clean,
                marked_by=teacher.staff.id,
            )
            .on_conflict_do_update(
                constraint="uq_attendance_group_student_date",
                set_={
                    "status": item.status,
                    "note": note_clean,
                    "marked_by": teacher.staff.id,
                    "updated_at": func.now(),
                },
            )
        )
        await session.execute(stmt)

    await session.commit()
    return await get_attendance_sheet(session, teacher, group_id, target_date)


async def finalize_attendance(
    session: AsyncSession,
    teacher: Identity,
    group_id: uuid.UUID,
    target_date: date,
    items: list[DraftItem] | None = None,
) -> AttendanceSheet:
    await ensure_group_owner(session, teacher, group_id)

    # 1. Idempotent check: if already finalized, return current sheet
    finalized, _ = await is_date_finalized(session, group_id, target_date)
    if finalized:
        return await get_attendance_sheet(session, teacher, group_id, target_date)

    # 2. Upsert any items passed in request body
    if items:
        valid_ids = set(
            (
                await session.scalars(
                    select(Student.id).where(
                        Student.group_id == group_id,
                        Student.status == Status.ACTIVE,
                    )
                )
            ).all()
        )
        for item in items:
            if item.student_id not in valid_ids:
                msg = f"Talaba ({item.student_id}) ushbu guruhga tegishli emas yoki faol emas"
                raise DomainError(msg, 422)

            note_clean = item.note.strip() if item.note else None
            if note_clean == "":
                note_clean = None

            stmt = (
                insert(Attendance)
                .values(
                    group_id=group_id,
                    student_id=item.student_id,
                    date=target_date,
                    status=item.status,
                    note=note_clean,
                    marked_by=teacher.staff.id,
                )
                .on_conflict_do_update(
                    constraint="uq_attendance_group_student_date",
                    set_={
                        "status": item.status,
                        "note": note_clean,
                        "marked_by": teacher.staff.id,
                        "updated_at": func.now(),
                    },
                )
            )
            await session.execute(stmt)
        await session.flush()

    # 3. Fetch all active students in this group
    active_students = list(
        (
            await session.scalars(
                select(Student)
                .options(joinedload(Student.parent), joinedload(Student.group))
                .where(Student.group_id == group_id, Student.status == Status.ACTIVE)
            )
        ).all()
    )

    # 4. Fetch all attendance records for (group_id, target_date)
    records = list(
        (
            await session.scalars(
                select(Attendance).where(
                    Attendance.group_id == group_id,
                    Attendance.date == target_date,
                )
            )
        ).all()
    )
    records_by_student = {r.student_id: r for r in records}

    # 5. Check that EVERY active student has attendance marked
    missing = [s for s in active_students if s.id not in records_by_student]
    if missing:
        names = ", ".join(f"{s.first_name} {s.last_name}" for s in missing)
        msg = f"Barcha faol talabalar uchun davomat belgilanishi shart. Belgilanmagan: {names}"
        raise DomainError(msg, 422)

    # 6. Create AttendanceBatch
    batch = AttendanceBatch(
        group_id=group_id,
        date=target_date,
        finalized_by=teacher.staff.id,
    )
    session.add(batch)
    await session.flush()

    # 7. Atomically attach batch_id and create NotificationOutbox records
    for s in active_students:
        att = records_by_student[s.id]
        att.batch_id = batch.id

        idem_key = f"att_{att.id}"
        existing_outbox = await session.scalar(
            select(NotificationOutbox.id).where(NotificationOutbox.idempotency_key == idem_key)
        )
        if not existing_outbox:
            status_labels = {
                AttendanceStatus.PRESENT: "Bor",
                AttendanceStatus.ABSENT: "Yo‘q",
                AttendanceStatus.LATE: "Kechikdi",
            }
            payload = {
                "student_name": f"{s.first_name} {s.last_name}",
                "group_name": s.group.name,
                "date": target_date.isoformat(),
                "status": att.status.value,
                "status_label": status_labels.get(att.status, att.status.value),
                "note": att.note,
            }
            outbox_item = NotificationOutbox(
                idempotency_key=idem_key,
                attendance_id=att.id,
                parent_id=s.parent_id,
                telegram_id=s.parent.telegram_id,
                payload=payload,
                status=OutboxStatus.PENDING if s.parent.telegram_id else OutboxStatus.SKIPPED,
            )
            session.add(outbox_item)

    await session.commit()
    return await get_attendance_sheet(session, teacher, group_id, target_date)


async def list_admin_attendance(
    session: AsyncSession,
    *,
    target_date: date | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    group_id: uuid.UUID | None = None,
    teacher_id: uuid.UUID | None = None,
    student_id: uuid.UUID | None = None,
    status: AttendanceStatus | None = None,
    page: int = 1,
    page_size: int = 20,
) -> AdminAttendancePage:
    filters: list[ColumnElement[bool]] = []
    if target_date is not None:
        filters.append(Attendance.date == target_date)
    if from_date is not None:
        filters.append(Attendance.date >= from_date)
    if to_date is not None:
        filters.append(Attendance.date <= to_date)
    if group_id is not None:
        filters.append(Attendance.group_id == group_id)
    if teacher_id is not None:
        filters.append(Group.teacher_id == teacher_id)
    if student_id is not None:
        filters.append(Attendance.student_id == student_id)
    if status is not None:
        filters.append(Attendance.status == status)

    total = (
        await session.scalar(
            select(func.count())
            .select_from(Attendance)
            .join(Group, Attendance.group_id == Group.id)
            .where(*filters)
        )
        or 0
    )

    stmt = (
        select(
            Attendance,
            Group.name,
            Staff.first_name,
            Staff.last_name,
            Student.first_name,
            Student.last_name,
        )
        .join(Group, Attendance.group_id == Group.id)
        .join(Staff, Group.teacher_id == Staff.id)
        .join(Student, Attendance.student_id == Student.id)
        .where(*filters)
        .order_by(Attendance.date.desc(), Group.name, Student.first_name)
        .limit(page_size)
        .offset((page - 1) * page_size)
    )

    rows = []
    for att, g_name, t_fn, t_ln, s_fn, s_ln in (await session.execute(stmt)).all():
        rows.append(
            AdminAttendanceRow(
                attendance_id=att.id,
                date=att.date,
                group_id=att.group_id,
                group_name=g_name,
                teacher_id=att.marked_by,
                teacher_name=f"{t_fn} {t_ln}",
                student_id=att.student_id,
                student_name=f"{s_fn} {s_ln}",
                status=att.status,
                note=att.note,
                marked_at=att.updated_at,
                finalized=att.batch_id is not None,
                batch_id=att.batch_id,
            )
        )

    return AdminAttendancePage(items=rows, total=total, page=page, page_size=page_size)


async def dispatch_pending_outbox_stub(
    database: Database,
    transport: httpx.AsyncBaseTransport | None = None,
) -> int:
    try:
        async with database.session() as session:
            sys_settings = await session.get(SystemSettings, 1)
            if sys_settings is None or not sys_settings.bot_token_encrypted:
                return 0
        return await dispatch_pending_outbox(database, transport=transport)
    except Exception:
        return 0
