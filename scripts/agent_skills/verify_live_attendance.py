"""Verify live attendance records, monthly history, and student stats in neoavlod_demo."""

import asyncio
import os
from datetime import date
from pydantic import SecretStr
from sqlalchemy import func, select

from neoavlod.database import Database
from neoavlod.models import (
    Attendance,
    AttendanceBatch,
    AttendanceStatus,
    Group,
    NotificationOutbox,
    Staff,
    Student,
)
from neoavlod.services.attendance import (
    get_group_monthly_attendance_history,
    get_student_monthly_attendance_stats,
)
from neoavlod.settings import Settings


async def main() -> None:
    settings = Settings(_env_file=None)
    db = Database(settings)

    async with db.session() as session:
        # 1. Total counts
        groups = (await session.scalars(select(Group))).all()
        students = (await session.scalars(select(Student))).all()
        batches = (await session.scalars(select(AttendanceBatch))).all()
        records = (await session.scalars(select(Attendance))).all()
        outbox_cnt = await session.scalar(select(func.count()).select_from(NotificationOutbox))

        present_cnt = sum(1 for r in records if r.status == AttendanceStatus.PRESENT)
        absent_cnt = sum(1 for r in records if r.status == AttendanceStatus.ABSENT)
        notes_cnt = sum(1 for r in records if r.note)

        print("=== LIVE DATABASE RECONCILIATION ===")
        print(f"Total groups:             {len(groups)} (expected 10)")
        print(f"Total active students:    {len(students)} (expected 81)")
        print(f"Total attendance batches: {len(batches)} (expected 29)")
        print(f"Total attendance records: {len(records)} (expected 302)")
        print(f"Present ('k'):            {present_cnt} (expected 162)")
        print(f"Absent:                   {absent_cnt} (expected 140)")
        print(f"Records with notes:       {notes_cnt} (expected 28)")
        print(f"Notification outbox:      {outbox_cnt} (expected 0 new notifications)")

        assert len(groups) == 10
        assert len(students) == 81
        assert len(batches) == 29
        assert len(records) == 302
        assert present_cnt == 162
        assert absent_cnt == 140
        assert notes_cnt == 28

        # 2. Check each group's monthly history
        print("\n=== MONTHLY ATTENDANCE HISTORY BY GROUP ===")
        for group in sorted(groups, key=lambda g: g.name):
            # Check September 2026
            hist_sep = await get_group_monthly_attendance_history(session, group.id, "2026-09")
            # Check October 2026
            hist_oct = await get_group_monthly_attendance_history(session, group.id, "2026-10")

            total_lessons = hist_sep.summary.total_lessons + hist_oct.summary.total_lessons
            total_present = hist_sep.summary.present_count + hist_oct.summary.present_count
            total_absent = hist_sep.summary.absent_count + hist_oct.summary.absent_count

            print(
                f"• {group.name[:40]:40s} | "
                f"Sep lessons: {hist_sep.summary.total_lessons}, Oct lessons: {hist_oct.summary.total_lessons} | "
                f"Present: {total_present:2d}, Absent: {total_absent:2d}"
            )
            assert total_lessons > 0, f"Group {group.name} has no lessons!"

        # 3. Check sample student profile statistics
        print("\n=== SAMPLE STUDENT PROFILE ATTENDANCE STATS ===")
        sample_students = students[:5]
        for st in sample_students:
            stats_sep = await get_student_monthly_attendance_stats(session, st.id, "2026-09")
            stats_oct = await get_student_monthly_attendance_stats(session, st.id, "2026-10")
            print(
                f"• {st.first_name:25s} | "
                f"Sep (P:{stats_sep.present_count}, A:{stats_sep.absent_count}, Tot:{stats_sep.total_lessons}) | "
                f"Oct (P:{stats_oct.present_count}, A:{stats_oct.absent_count}, Tot:{stats_oct.total_lessons})"
            )

    await db.close()
    print("\nALL LIVE RECONCILIATION AND API QUERIES VERIFIED SUCCESSFULLY!")


if __name__ == "__main__":
    asyncio.run(main())
