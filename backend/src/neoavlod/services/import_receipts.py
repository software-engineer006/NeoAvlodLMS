"""One-time deployment import or verified adoption; later manual edits stay authoritative."""

from collections.abc import Awaitable, Callable
from datetime import date
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from neoavlod.models import Attendance, AttendanceBatch, Group, ImportReceipt, Student
from neoavlod.roster_import import ImportPlan


async def deployment_import(
    session: AsyncSession,
    *,
    key: str,
    digest: str,
    roster: ImportPlan,
    attendance: list[dict[str, Any]],
    apply: Callable[[], Awaitable[dict[str, int]]],
    lessons: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    """Caller owns transaction. A changed reviewed digest always needs explicit reconciliation."""
    await session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": 0x4E454F099})
    receipt = await session.get(ImportReceipt, key)
    if receipt:
        if receipt.plan_digest != digest:
            raise ValueError("Deployment import digest changed; explicit review required")
        return {"deployment_status": "already_applied", "created": 0}
    groups = {
        row.source_key: row
        for row in (
            await session.scalars(
                select(Group).where(Group.source_key.in_([g.key for g in roster.groups]))
            )
        ).all()
    }
    students = {
        row.source_key: row
        for row in (
            await session.scalars(
                select(Student).where(Student.source_key.in_([s.key for s in roster.students]))
            )
        ).all()
    }
    if not groups and not students:
        result: dict[str, Any] = {"deployment_status": "applied", **await apply()}
        method = "applied"
    else:
        if len(groups) != len(roster.groups) or len(students) != len(roster.students):
            raise ValueError("Partial existing deployment import; explicit review required")
        if any(groups[g.key].source_data != g.source for g in roster.groups) or any(
            students[s.key].source_data != s.source for s in roster.students
        ):
            raise ValueError("Existing import provenance differs; explicit review required")
        # Verify every original record exists, without replacing later admin status,
        # notes, actor, group schedule, enrollment, profile, password or bot link.
        for item in attendance:
            existing = await session.scalar(
                select(Attendance.id).where(
                    Attendance.group_id == groups[item["group_key"]].id,
                    Attendance.student_id == students[item["student_key"]].id,
                    Attendance.date == date.fromisoformat(item["date"]),
                )
            )
            if existing is None:
                raise ValueError("Existing import history incomplete; explicit review required")
        for group_key, dates in (lessons or {}).items():
            for day in dates:
                if (
                    await session.scalar(
                        select(AttendanceBatch.id).where(
                            AttendanceBatch.group_id == groups[group_key].id,
                            AttendanceBatch.date == date.fromisoformat(day),
                        )
                    )
                    is None
                ):
                    raise ValueError("Existing import batches incomplete; explicit review required")
        result = {"deployment_status": "adopted", "created": 0}
        method = "adopted"
    session.add(ImportReceipt(key=key, plan_digest=digest, method=method))
    await session.flush()
    return result
