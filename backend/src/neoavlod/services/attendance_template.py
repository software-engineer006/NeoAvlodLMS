import uuid

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from neoavlod.attendance_messages import DEFAULT_TEMPLATE, validate_template
from neoavlod.errors import DomainError
from neoavlod.models import AttendanceMessageTemplate


async def current_template(
    session: AsyncSession,
) -> tuple[str, int, AttendanceMessageTemplate | None]:
    current = await session.get(AttendanceMessageTemplate, 1)
    return (current.body, current.version, current) if current else (DEFAULT_TEMPLATE, 0, None)


async def save_template(
    session: AsyncSession, actor_id: uuid.UUID, body: str, expected_version: int
) -> AttendanceMessageTemplate | None:
    body = validate_template(body)
    await session.execute(text("SELECT pg_advisory_xact_lock(1313165110)"))
    current = await session.scalar(
        select(AttendanceMessageTemplate)
        .where(AttendanceMessageTemplate.id == 1)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if (current.version if current else 0) != expected_version:
        raise DomainError(
            "Shablon boshqa xodim tomonidan yangilangan. Qayta yuklab tahrirlang.", 409
        )
    if body == (current.body if current else DEFAULT_TEMPLATE):
        return current
    if current is None:
        current = AttendanceMessageTemplate(id=1, body=body, version=1, changed_by=actor_id)
        session.add(current)
    else:
        current.body = body
        current.version += 1
        current.changed_by = actor_id
    await session.commit()
    await session.refresh(current)
    return current
