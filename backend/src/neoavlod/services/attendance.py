import calendar
import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from neoavlod.database import Database
from neoavlod.errors import DomainError
from neoavlod.models import (
    Attendance,
    AttendanceBatch,
    AttendanceChange,
    AttendanceStatus,
    Group,
    NotificationOutbox,
    OutboxStatus,
    Portal,
    Role,
    Staff,
    Student,
    SystemSettings,
)
from neoavlod.models.common import Status
from neoavlod.security.rbac import (
    Permission,
    ensure_group_owner,
    ensure_permissions,
    ensure_portal_session,
    ensure_superadmin,
    has_permission,
)
from neoavlod.security.sessions import Identity
from neoavlod.services.attendance_payload import message_snapshot
from neoavlod.services.enrollments import in_group
from neoavlod.services.outbox import dispatch_pending_outbox


@dataclass(frozen=True)
class AttendanceEntry:
    student_id: uuid.UUID
    student_first_name: str
    student_last_name: str | None
    status: AttendanceStatus | None
    note: str | None
    marked_at: datetime | None
    source_imported: bool = False


@dataclass(frozen=True)
class AttendanceSheet:
    group_id: uuid.UUID
    date: date
    finalized: bool
    finalized_at: datetime | None
    can_edit: bool
    edit_deadline: datetime | None
    edit_disabled_reason: str | None
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
    source_imported: bool = False


@dataclass(frozen=True)
class AdminAttendancePage:
    items: list[AdminAttendanceRow]
    total: int
    page: int
    page_size: int


@dataclass(frozen=True)
class StudentMonthlyAttendanceStats:
    month: str
    present_count: int
    late_count: int
    absent_count: int
    attended_count: int
    total_lessons: int


@dataclass(frozen=True)
class MonthlyAttendanceRecord:
    attendance_id: uuid.UUID
    student_id: uuid.UUID
    student_name: str
    date: date
    status: AttendanceStatus
    note: str | None
    source_imported: bool = False


@dataclass(frozen=True)
class StudentMonthlyAttendanceSummary:
    student_id: uuid.UUID
    student_name: str
    present_count: int
    late_count: int
    absent_count: int
    attended_count: int
    total_lessons: int


@dataclass(frozen=True)
class GroupMonthlyAttendanceSummary:
    total_lessons: int
    total_records: int
    present_count: int
    late_count: int
    absent_count: int


@dataclass(frozen=True)
class GroupMonthlyAttendanceHistory:
    group_id: uuid.UUID
    group_name: str
    month: str
    dates: list[date]
    records: list[MonthlyAttendanceRecord]
    students_summary: list[StudentMonthlyAttendanceSummary]
    summary: GroupMonthlyAttendanceSummary


TASHKENT = ZoneInfo("Asia/Tashkent")


def attendance_now() -> datetime:
    return datetime.now(TASHKENT)


def edit_window(target_date: date) -> tuple[bool, datetime, str | None]:
    now = attendance_now().astimezone(TASHKENT)
    deadline = datetime.combine(target_date + timedelta(days=2), time.max, TASHKENT)
    if target_date > now.date():
        return False, deadline, "Kelajakdagi sana uchun davomatni o‘zgartirib bo‘lmaydi"
    if now > deadline:
        return False, deadline, "Davomatni tahrirlash uchun 2 kunlik muddat tugagan"
    return True, deadline, None


async def ensure_attendance_access(
    session: AsyncSession, actor: Identity, group_id: uuid.UUID, *, write: bool = False
) -> None:
    if actor.staff.role == Role.TEACHER:
        ensure_portal_session(actor, Portal.TEACHER)
        await ensure_group_owner(session, actor, group_id)
    else:
        ensure_portal_session(actor, Portal.ADMIN)
        required = [Permission.ATTENDANCE_READ]
        if write:
            required.append(Permission.ATTENDANCE_WRITE)
        ensure_permissions(actor, required)
        if await session.get(Group, group_id) is None:
            raise DomainError("Guruh topilmadi", 404)


def actor_edit_window(
    actor: Identity, target_date: date
) -> tuple[bool, datetime | None, str | None]:
    if actor.staff.role == Role.TEACHER:
        return edit_window(target_date)
    if target_date > attendance_now().astimezone(TASHKENT).date():
        return False, None, "Kelajakdagi sana uchun davomatni o‘zgartirib bo‘lmaydi"
    if not has_permission(actor.staff, Permission.ATTENDANCE_WRITE):
        return False, None, "Davomatni belgilash uchun ruxsat yo‘q"
    return True, None, None


async def _lock_editable_group(
    session: AsyncSession, teacher: Identity, group_id: uuid.UUID, target_date: date
) -> Group:
    await ensure_attendance_access(session, teacher, group_id, write=True)
    query = select(Group).where(Group.id == group_id)
    if teacher.staff.role == Role.TEACHER:
        query = query.where(Group.teacher_id == teacher.staff.id)
    owned = await session.scalar(query.with_for_update())
    if owned is None:
        raise DomainError("Guruh topilmadi", 404)
    editable, _, reason = actor_edit_window(teacher, target_date)
    if not editable:
        raise DomainError(reason or "Davomatni tahrirlash mumkin emas", 409)
    return owned


def _audit(
    session: AsyncSession,
    actor: Identity,
    record: Attendance,
    action: str,
    old_status: str | None,
    old_note: str | None,
    reason: str | None,
) -> None:
    session.add(
        AttendanceChange(
            attendance_id=record.id,
            actor_id=actor.staff.id,
            actor_name=f"{actor.staff.first_name} {actor.staff.last_name or ''}".strip(),
            actor_role=actor.staff.role.value,
            action=action,
            old_status=old_status,
            new_status=record.status.value,
            old_note=old_note,
            new_note=record.note,
            reason=reason,
        )
    )


def _require_reason(actor: Identity, reason: str | None) -> None:
    if not (reason and reason.strip()):
        raise DomainError("Davomat tuzatish sababini kiritish shart", 422)


async def _upsert_items(
    session: AsyncSession,
    actor: Identity,
    group_id: uuid.UUID,
    target_date: date,
    items: list[DraftItem],
    reason: str | None,
) -> None:
    for item in items:
        note = item.note.strip() or None if item.note else None
        record = await session.scalar(
            select(Attendance)
            .where(
                Attendance.group_id == group_id,
                Attendance.student_id == item.student_id,
                Attendance.date == target_date,
            )
            .execution_options(populate_existing=True)
        )
        if record and record.status == item.status and record.note == note:
            continue
        old_status, old_note = (record.status.value, record.note) if record else (None, None)
        if record:
            _require_reason(actor, reason)
            record.status, record.note = item.status, note
            record.marked_by, record.updated_at = actor.staff.id, attendance_now()
        else:
            record = Attendance(
                group_id=group_id,
                student_id=item.student_id,
                date=target_date,
                status=item.status,
                note=note,
                marked_by=actor.staff.id,
            )
            session.add(record)
        await session.flush()
        _audit(session, actor, record, "draft", old_status, old_note, reason)


def _validate_items(items: list[DraftItem], valid_ids: set[uuid.UUID]) -> None:
    if len({item.student_id for item in items}) != len(items):
        raise DomainError("Bir o‘quvchi davomatda bir marta ko‘rsatilishi kerak", 422)
    if any(item.student_id not in valid_ids for item in items):
        raise DomainError("O‘quvchi ushbu guruhga tegishli emas yoki faol emas", 422)


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
    await ensure_attendance_access(session, teacher, group_id)
    finalized, finalized_at = await is_date_finalized(session, group_id, target_date)
    can_edit, edit_deadline, edit_disabled_reason = actor_edit_window(teacher, target_date)

    students = list(
        (
            await session.scalars(
                select(Student)
                .where(in_group(group_id), Student.status == Status.ACTIVE)
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
                source_imported=rec.source_imported if rec else False,
            )
        )

    return AttendanceSheet(
        group_id=group_id,
        date=target_date,
        finalized=finalized,
        finalized_at=finalized_at,
        can_edit=can_edit,
        edit_deadline=edit_deadline,
        edit_disabled_reason=edit_disabled_reason,
        items=entries,
    )


async def save_attendance_draft(
    session: AsyncSession,
    teacher: Identity,
    group_id: uuid.UUID,
    target_date: date,
    items: list[DraftItem],
    reason: str | None = None,
) -> AttendanceSheet:
    await _lock_editable_group(session, teacher, group_id, target_date)
    finalized, _ = await is_date_finalized(session, group_id, target_date)
    if finalized:
        raise DomainError("Ushbu sana uchun davomat allaqachon yakunlangan", 409)

    valid_ids = set(
        (
            await session.scalars(
                select(Student.id).where(
                    in_group(group_id),
                    Student.status == Status.ACTIVE,
                )
            )
        ).all()
    )

    _validate_items(items, valid_ids)

    await _upsert_items(session, teacher, group_id, target_date, items, reason)

    await session.commit()
    return await get_attendance_sheet(session, teacher, group_id, target_date)


async def finalize_attendance(
    session: AsyncSession,
    teacher: Identity,
    group_id: uuid.UUID,
    target_date: date,
    items: list[DraftItem] | None = None,
    reason: str | None = None,
) -> AttendanceSheet:
    group = await _lock_editable_group(session, teacher, group_id, target_date)

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
                        in_group(group_id),
                        Student.status == Status.ACTIVE,
                    )
                )
            ).all()
        )
        _validate_items(items, valid_ids)
        await _upsert_items(session, teacher, group_id, target_date, items, reason)
        await session.flush()

    # 3. Fetch all active students in this group
    active_students = list(
        (
            await session.scalars(
                select(Student)
                .options(joinedload(Student.parent), joinedload(Student.group))
                .where(in_group(group_id), Student.status == Status.ACTIVE)
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
        names = ", ".join(f"{s.first_name} {s.last_name or ''}".strip() for s in missing)
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
        _audit(session, teacher, att, "finalize", att.status.value, att.note, reason)

        idem_key = f"att_{att.id}"
        existing_outbox = await session.scalar(
            select(NotificationOutbox.id).where(NotificationOutbox.idempotency_key == idem_key)
        )
        if not existing_outbox and s.parent is not None:
            payload = await message_snapshot(session, group, s, att)
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


async def correct_attendance(
    session: AsyncSession,
    teacher: Identity,
    group_id: uuid.UUID,
    target_date: date,
    items: list[DraftItem],
    reason: str | None = None,
) -> AttendanceSheet:
    group = await _lock_editable_group(session, teacher, group_id, target_date)
    batch = await session.scalar(
        select(AttendanceBatch).where(
            AttendanceBatch.group_id == group_id, AttendanceBatch.date == target_date
        )
    )
    if batch is None:
        raise DomainError("Avval davomatni yakunlang yoki qoralama sifatida saqlang", 409)
    students = list(
        (
            await session.scalars(
                select(Student)
                .options(joinedload(Student.parent), joinedload(Student.group))
                .where(in_group(group_id), Student.status == Status.ACTIVE)
            )
        ).all()
    )
    by_student = {s.id: s for s in students}
    _validate_items(items, set(by_student))
    records = list(
        (
            await session.scalars(
                select(Attendance)
                .where(Attendance.group_id == group_id, Attendance.date == target_date)
                .execution_options(populate_existing=True)
            )
        ).all()
    )
    by_record = {r.student_id: r for r in records}
    for item in items:
        note = item.note.strip() or None if item.note else None
        record = by_record.get(item.student_id)
        if record is not None and record.status == item.status and record.note == note:
            continue
        _require_reason(teacher, reason)
        old_status, old_note = (record.status.value, record.note) if record else (None, None)
        if record is None:
            record = Attendance(
                group_id=group_id,
                student_id=item.student_id,
                date=target_date,
                status=item.status,
                note=note,
                marked_by=teacher.staff.id,
                batch_id=batch.id,
            )
            session.add(record)
        else:
            record.status = item.status
            record.note = note
            record.marked_by = teacher.staff.id
            record.batch_id = batch.id
            record.updated_at = attendance_now()
        await session.flush()
        _audit(session, teacher, record, "correct", old_status, old_note, reason)
        learner = by_student[item.student_id]
        if teacher.staff.role != Role.TEACHER:
            queued = (
                await session.scalars(
                    select(NotificationOutbox)
                    .where(
                        NotificationOutbox.attendance_id == record.id,
                        NotificationOutbox.status.in_(
                            (OutboxStatus.PENDING, OutboxStatus.PROCESSING, OutboxStatus.FAILED)
                        ),
                    )
                    .with_for_update()
                )
            ).all()
            for pending in queued:
                pending.status = OutboxStatus.SKIPPED
                pending.locked_by = None
                pending.locked_until = None
                pending.last_error = "Administrator davomatni tuzatdi; xabar yuborilmaydi"
            continue
        if learner.parent is None:
            continue
        payload = await message_snapshot(session, group, learner, record, correction=True)
        latest = await session.scalar(
            select(NotificationOutbox)
            .where(NotificationOutbox.attendance_id == record.id)
            .order_by(NotificationOutbox.created_at.desc(), NotificationOutbox.id.desc())
            .limit(1)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if latest is not None and latest.status in (
            OutboxStatus.PENDING,
            OutboxStatus.SKIPPED,
            OutboxStatus.FAILED,
            OutboxStatus.PROCESSING,
        ):
            latest.payload = payload
            latest.telegram_id = learner.parent.telegram_id
            latest.parent_id = learner.parent.id
            latest.status = OutboxStatus.PENDING if latest.telegram_id else OutboxStatus.SKIPPED
            latest.attempts = 0
            latest.locked_by = None
            latest.locked_until = None
            latest.available_at = attendance_now()
            latest.last_error = None
        else:
            session.add(
                NotificationOutbox(
                    idempotency_key=f"att_{record.id}_correction_{uuid.uuid4()}",
                    attendance_id=record.id,
                    parent_id=learner.parent.id,
                    telegram_id=learner.parent.telegram_id,
                    payload=payload,
                    status=OutboxStatus.PENDING
                    if learner.parent.telegram_id
                    else OutboxStatus.SKIPPED,
                )
            )
    await session.commit()
    return await get_attendance_sheet(session, teacher, group_id, target_date)


async def attendance_groups(
    session: AsyncSession, pending_date: date | None = None
) -> list[dict[str, object]]:
    query = select(Group, Staff).join(Staff, Staff.id == Group.teacher_id)
    if pending_date is not None:
        query = query.where(
            Group.status == Status.ACTIVE,
            Group.days_of_week.contains([pending_date.isoweekday()]),
            ~select(AttendanceBatch.id)
            .where(AttendanceBatch.group_id == Group.id, AttendanceBatch.date == pending_date)
            .exists(),
        )
    rows = (await session.execute(query.order_by(func.lower(Group.name)))).all()
    return [
        {
            "id": g.id,
            "name": g.name,
            "teacher_id": t.id,
            "teacher_name": f"{t.first_name} {t.last_name or ''}".strip(),
            "days_of_week": list(g.days_of_week),
        }
        for g, t in rows
    ]


async def list_attendance_changes(
    session: AsyncSession,
    actor: Identity,
    group_id: uuid.UUID,
    target_date: date,
    *,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, object]:
    ensure_superadmin(actor)
    await ensure_attendance_access(session, actor, group_id)
    query = (
        select(AttendanceChange, Student)
        .join(Attendance, Attendance.id == AttendanceChange.attendance_id)
        .join(Student, Student.id == Attendance.student_id)
        .where(Attendance.group_id == group_id, Attendance.date == target_date)
    )
    total = await session.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = (
        await session.execute(
            query.order_by(AttendanceChange.changed_at.desc(), AttendanceChange.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    items = [
        {
            **{
                key: getattr(change, key)
                for key in (
                    "id",
                    "attendance_id",
                    "actor_id",
                    "actor_name",
                    "actor_role",
                    "action",
                    "old_status",
                    "new_status",
                    "old_note",
                    "new_note",
                    "reason",
                    "changed_at",
                )
            },
            "student_name": f"{student.first_name} {student.last_name or ''}".strip(),
        }
        for change, student in rows
    ]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


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
            Group.teacher_id,
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
    for att, g_name, g_teacher_id, t_fn, t_ln, s_fn, s_ln in (await session.execute(stmt)).all():
        rows.append(
            AdminAttendanceRow(
                attendance_id=att.id,
                date=att.date,
                group_id=att.group_id,
                group_name=g_name,
                teacher_id=g_teacher_id,
                teacher_name=f"{t_fn} {t_ln or ''}".strip(),
                student_id=att.student_id,
                student_name=f"{s_fn} {s_ln or ''}".strip(),
                status=att.status,
                note=att.note,
                marked_at=att.updated_at,
                finalized=att.batch_id is not None,
                batch_id=att.batch_id,
                source_imported=att.source_imported,
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


def parse_month_string(month_str: str) -> tuple[date, date]:
    parts = month_str.split("-")
    if len(parts) != 2 or len(parts[0]) != 4 or len(parts[1]) != 2:
        raise DomainError("Noto‘g‘ri oy formati (YYYY-MM talab qilinadi)", 422)
    try:
        year = int(parts[0])
        month_num = int(parts[1])
        if month_num < 1 or month_num > 12:
            raise ValueError
        _, last_day = calendar.monthrange(year, month_num)
        return date(year, month_num, 1), date(year, month_num, last_day)
    except (ValueError, OverflowError):
        raise DomainError("Noto‘g‘ri oy formati (YYYY-MM talab qilinadi)", 422) from None


async def get_student_monthly_attendance_stats(
    session: AsyncSession,
    student_id: uuid.UUID,
    month_str: str,
    group_id: uuid.UUID | None = None,
) -> StudentMonthlyAttendanceStats:
    start_date, end_date = parse_month_string(month_str)

    stmt = (
        select(
            Attendance.status,
            func.count(Attendance.id).label("count"),
        )
        .where(or_(Attendance.batch_id.is_not(None), Attendance.source_imported.is_(True)))
        .where(
            Attendance.student_id == student_id,
            Attendance.date >= start_date,
            Attendance.date <= end_date,
        )
        .group_by(Attendance.status)
    )
    if group_id is not None:
        stmt = stmt.where(Attendance.group_id == group_id)
    result = await session.execute(stmt)
    status_counts = {row[0]: int(row[1]) for row in result.all()}

    present_count = status_counts.get(AttendanceStatus.PRESENT, 0)
    late_count = status_counts.get(AttendanceStatus.LATE, 0)
    absent_count = status_counts.get(AttendanceStatus.ABSENT, 0)
    attended_count = present_count + late_count
    total_lessons = present_count + late_count + absent_count

    return StudentMonthlyAttendanceStats(
        month=month_str,
        present_count=present_count,
        late_count=late_count,
        absent_count=absent_count,
        attended_count=attended_count,
        total_lessons=total_lessons,
    )


async def get_group_monthly_attendance_history(
    session: AsyncSession,
    group_id: uuid.UUID,
    month_str: str,
    teacher: Identity | None = None,
) -> GroupMonthlyAttendanceHistory:
    if teacher is not None:
        await ensure_group_owner(session, teacher, group_id)

    group = await session.get(Group, group_id)
    if group is None:
        raise DomainError("Guruh topilmadi", 404)

    start_date, end_date = parse_month_string(month_str)

    batches_stmt = (
        select(AttendanceBatch.date)
        .where(
            AttendanceBatch.group_id == group_id,
            AttendanceBatch.date >= start_date,
            AttendanceBatch.date <= end_date,
        )
        .order_by(AttendanceBatch.date.asc())
    )
    source_dates = await session.scalars(
        select(Attendance.date)
        .where(
            Attendance.group_id == group_id,
            Attendance.source_imported.is_(True),
            Attendance.date >= start_date,
            Attendance.date <= end_date,
        )
        .distinct()
    )
    batch_dates = sorted(set((await session.scalars(batches_stmt)).all()) | set(source_dates.all()))

    records_stmt = (
        select(
            Attendance,
            Student.first_name,
            Student.last_name,
        )
        .where(or_(Attendance.batch_id.is_not(None), Attendance.source_imported.is_(True)))
        .join(Student, Attendance.student_id == Student.id)
        .where(
            Attendance.group_id == group_id,
            Attendance.date >= start_date,
            Attendance.date <= end_date,
        )
        .order_by(Attendance.date.asc(), Student.first_name.asc(), Student.last_name.asc())
    )
    att_rows = (await session.execute(records_stmt)).all()

    active_students_stmt = (
        select(Student)
        .where(
            in_group(group_id),
            Student.status == Status.ACTIVE,
        )
        .order_by(Student.first_name.asc(), Student.last_name.asc())
    )
    active_students = list((await session.scalars(active_students_stmt)).all())

    records: list[MonthlyAttendanceRecord] = []
    students_map: dict[uuid.UUID, dict[str, Any]] = {}

    for att, s_fn, s_ln in att_rows:
        student_name = f"{s_fn} {s_ln or ''}".strip()
        records.append(
            MonthlyAttendanceRecord(
                attendance_id=att.id,
                student_id=att.student_id,
                student_name=student_name,
                date=att.date,
                status=att.status,
                note=att.note,
                source_imported=att.source_imported,
            )
        )
        s_id = att.student_id
        if s_id not in students_map:
            students_map[s_id] = {
                "name": student_name,
                "present": 0,
                "late": 0,
                "absent": 0,
            }
        if att.status == AttendanceStatus.PRESENT:
            students_map[s_id]["present"] += 1
        elif att.status == AttendanceStatus.LATE:
            students_map[s_id]["late"] += 1
        elif att.status == AttendanceStatus.ABSENT:
            students_map[s_id]["absent"] += 1

    for st in active_students:
        if st.id not in students_map:
            students_map[st.id] = {
                "name": f"{st.first_name} {st.last_name or ''}".strip(),
                "present": 0,
                "late": 0,
                "absent": 0,
            }

    students_summary: list[StudentMonthlyAttendanceSummary] = []
    for s_id, s_data in sorted(students_map.items(), key=lambda item: item[1]["name"].lower()):
        pres_cnt = s_data["present"]
        late_cnt = s_data["late"]
        abs_cnt = s_data["absent"]
        students_summary.append(
            StudentMonthlyAttendanceSummary(
                student_id=s_id,
                student_name=s_data["name"],
                present_count=pres_cnt,
                late_count=late_cnt,
                absent_count=abs_cnt,
                attended_count=pres_cnt + late_cnt,
                total_lessons=pres_cnt + late_cnt + abs_cnt,
            )
        )

    present_total = sum(1 for r in records if r.status == AttendanceStatus.PRESENT)
    late_total = sum(1 for r in records if r.status == AttendanceStatus.LATE)
    absent_total = sum(1 for r in records if r.status == AttendanceStatus.ABSENT)

    group_summary = GroupMonthlyAttendanceSummary(
        total_lessons=len(batch_dates),
        total_records=len(records),
        present_count=present_total,
        late_count=late_total,
        absent_count=absent_total,
    )

    return GroupMonthlyAttendanceHistory(
        group_id=group.id,
        group_name=group.name,
        month=month_str,
        dates=batch_dates,
        records=records,
        students_summary=students_summary,
        summary=group_summary,
    )
