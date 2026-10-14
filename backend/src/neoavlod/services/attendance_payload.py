"""Immutable message snapshots with truthful feedback attribution from canonical history."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from neoavlod.attendance_messages import FIELDS, render_template
from neoavlod.models import Attendance, AttendanceChange, Group, Student, Subject
from neoavlod.services.attendance_template import current_template

ROLE_LABELS = {"teacher": "O‘qituvchi", "admin": "Administrator", "superadmin": "Superadmin"}
STATUS_LABELS = {"present": "Keldi", "absent": "Kelmadi", "late": "Kech qoldi"}


def clip_units(value: str, limit: int) -> str:
    encoded = value.encode("utf-16-le")
    if len(encoded) <= limit * 2:
        return value
    return encoded[: (limit - 1) * 2].decode("utf-16-le", errors="ignore").rstrip() + "…"


async def message_snapshot(
    session: AsyncSession,
    group: Group,
    pupil: Student,
    record: Attendance,
    *,
    correction: bool = False,
) -> dict[str, object]:
    await session.flush()
    author = ""
    if record.note:
        change = await session.scalar(
            select(AttendanceChange)
            .where(
                AttendanceChange.attendance_id == record.id,
                AttendanceChange.new_note == record.note,
                AttendanceChange.old_note.is_distinct_from(AttendanceChange.new_note),
            )
            .order_by(AttendanceChange.changed_at.desc(), AttendanceChange.id.desc())
            .limit(1)
        )
        author = (
            f"{ROLE_LABELS.get(change.actor_role, 'Xodim')} {change.actor_name}"
            if change
            else "Muallif qayd etilmagan"
        )
    subject = await session.get(Subject, group.subject_id)
    body, version, _ = await current_template(session)
    feedback_author = clip_units(author, 230)
    start = group.start_time.strftime("%H:%M") if group.start_time else "Kiritilmagan"
    end = group.end_time.strftime("%H:%M") if group.end_time else "Kiritilmagan"
    context = {
        "student_name": f"{pupil.first_name} {pupil.last_name or ''}".strip(),
        "subject_name": subject.name if subject else "Fan kiritilmagan",
        "group_name": group.name,
        "date": record.date.strftime("%d.%m.%Y"),
        "lesson_time": f"{start}–{end}",
        "status_label": STATUS_LABELS[record.status.value],
        "feedback_author": feedback_author,
        "feedback": clip_units(f"Izoh ({feedback_author}): {record.note}", 2240)
        if record.note
        else "",
    }
    assert set(context) == FIELDS
    message = render_template(body, context)
    if correction:
        message = "Davomat tuzatildi\n\n" + message
    return {
        "student_name": context["student_name"],
        "group_name": group.name,
        "date": record.date.isoformat(),
        "status": record.status.value,
        "status_label": context["status_label"],
        "note": record.note,
        "correction": correction,
        "template_body": body,
        "template_version": version,
        "message_context": context,
        "message_text": message,
        "feedback_author": author,
    }
