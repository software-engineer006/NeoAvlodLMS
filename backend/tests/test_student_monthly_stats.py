import uuid
from datetime import date, time
from decimal import Decimal

import pytest
from factories import group, parent, staff, student
from sqlalchemy.ext.asyncio import AsyncSession
from test_rbac import actor, client_for

from neoavlod.database import Database
from neoavlod.models import (
    Attendance,
    AttendanceBatch,
    AttendanceStatus,
    Group,
    Parent,
    Role,
    Staff,
    Student,
    Subject,
)
from neoavlod.models.common import Status

pytestmark = pytest.mark.anyio


async def _create_test_hierarchy(
    session: AsyncSession,
    teacher_staff: Staff | None = None,
    group_name: str = "Python Core",
    month_price: str = "350000.00",
) -> tuple[Staff, Subject, Group, Parent, Student]:
    if teacher_staff is None:
        teacher_staff = staff(
            role=Role.TEACHER,
            status=Status.ACTIVE,
            first_name="Ustoz",
            last_name="Muallim",
        )
        session.add(teacher_staff)
        await session.flush()

    sub = Subject(name=f"Fan_{uuid.uuid4().hex[:6]}", description="Asosiy fan", is_active=True)
    session.add(sub)
    await session.flush()

    g = group(
        subject_id=sub.id,
        teacher_id=teacher_staff.id,
        name=group_name,
        status=Status.ACTIVE,
        monthly_price=Decimal(month_price),
        days_of_week=[1, 3, 5],
        start_time=time(9, 0),
        end_time=time(10, 30),
        room_number="302",
    )
    session.add(g)
    await session.flush()

    p = parent(first_name="Ota", last_name="Onaxon")
    session.add(p)
    await session.flush()

    s = student(
        group_id=g.id,
        parent_id=p.id,
        first_name="Alisher",
        last_name="Navoiy",
        age=15,
        status=Status.ACTIVE,
    )
    session.add(s)
    await session.flush()

    return teacher_staff, sub, g, p, s


async def _add_finalized_attendance(
    session: AsyncSession,
    group_obj: Group,
    student_obj: Student,
    teacher_staff: Staff,
    target_date: date,
    status_val: AttendanceStatus,
) -> tuple[Attendance, AttendanceBatch]:
    batch = AttendanceBatch(
        group_id=group_obj.id,
        date=target_date,
        finalized_by=teacher_staff.id,
    )
    session.add(batch)
    await session.flush()

    att = Attendance(
        group_id=group_obj.id,
        student_id=student_obj.id,
        date=target_date,
        status=status_val,
        marked_by=teacher_staff.id,
        batch_id=batch.id,
    )
    session.add(att)
    await session.flush()
    return att, batch


async def _add_draft_attendance(
    session: AsyncSession,
    group_obj: Group,
    student_obj: Student,
    teacher_staff: Staff,
    target_date: date,
    status_val: AttendanceStatus,
) -> Attendance:
    att = Attendance(
        group_id=group_obj.id,
        student_id=student_obj.id,
        date=target_date,
        status=status_val,
        marked_by=teacher_staff.id,
        batch_id=None,
    )
    session.add(att)
    await session.flush()
    return att


async def test_mixed_attendance_status_and_totals(model_database: Database) -> None:
    async with model_database.session() as session:
        t_staff, sub, g, p, s = await _create_test_hierarchy(session)
        # Add finalized attendance records in 2026-10:
        # 2 present, 1 late, 1 absent = 4 total, 3 attended
        await _add_finalized_attendance(
            session, g, s, t_staff, date(2026, 10, 2), AttendanceStatus.PRESENT
        )
        await _add_finalized_attendance(
            session, g, s, t_staff, date(2026, 10, 5), AttendanceStatus.PRESENT
        )
        await _add_finalized_attendance(
            session, g, s, t_staff, date(2026, 10, 7), AttendanceStatus.LATE
        )
        await _add_finalized_attendance(
            session, g, s, t_staff, date(2026, 10, 9), AttendanceStatus.ABSENT
        )
        await session.commit()
        student_id = s.id

    superadmin = await actor(model_database, role=Role.SUPERADMIN)
    async with client_for(superadmin) as client:
        res = await client.get(f"/api/v1/admin/students/{student_id}?month=2026-10")
        assert res.status_code == 200
        data = res.json()
        assert data["first_name"] == "Alisher"
        assert data["last_name"] == "Navoiy"
        assert data["group"]["subject_name"] is not None
        assert data["group"]["teacher_name"] == "Ustoz Muallim"
        assert data["group"]["room_number"] == "302"
        assert data["group"]["days_of_week"] == [1, 3, 5]

        stats = data["attendance_stats"]
        assert stats is not None
        assert stats["month"] == "2026-10"
        assert stats["present_count"] == 2
        assert stats["late_count"] == 1
        assert stats["absent_count"] == 1
        assert stats["attended_count"] == 3
        assert stats["total_lessons"] == 4


async def test_empty_month_returns_zeros(model_database: Database) -> None:
    async with model_database.session() as session:
        t_staff, sub, g, p, s = await _create_test_hierarchy(session)
        await _add_finalized_attendance(
            session, g, s, t_staff, date(2026, 10, 2), AttendanceStatus.PRESENT
        )
        await session.commit()
        student_id = s.id

    superadmin = await actor(model_database, role=Role.SUPERADMIN)
    async with client_for(superadmin) as client:
        # Request month 2026-11 where no attendance exists
        res = await client.get(f"/api/v1/admin/students/{student_id}?month=2026-11")
        assert res.status_code == 200
        data = res.json()
        stats = data["attendance_stats"]
        assert stats is not None
        assert stats["month"] == "2026-11"
        assert stats["present_count"] == 0
        assert stats["late_count"] == 0
        assert stats["absent_count"] == 0
        assert stats["attended_count"] == 0
        assert stats["total_lessons"] == 0


async def test_month_year_boundary_isolation(model_database: Database) -> None:
    async with model_database.session() as session:
        t_staff, sub, g, p, s = await _create_test_hierarchy(session)
        # Lesson on last day of December 2026
        await _add_finalized_attendance(
            session, g, s, t_staff, date(2026, 12, 31), AttendanceStatus.PRESENT
        )
        # Lesson on first day of January 2027
        await _add_finalized_attendance(
            session, g, s, t_staff, date(2027, 1, 1), AttendanceStatus.LATE
        )
        await session.commit()
        student_id = s.id

    superadmin = await actor(model_database, role=Role.SUPERADMIN)
    async with client_for(superadmin) as client:
        # December 2026
        res_dec = await client.get(f"/api/v1/admin/students/{student_id}?month=2026-12")
        assert res_dec.status_code == 200
        stats_dec = res_dec.json()["attendance_stats"]
        assert stats_dec["month"] == "2026-12"
        assert stats_dec["present_count"] == 1
        assert stats_dec["late_count"] == 0
        assert stats_dec["total_lessons"] == 1

        # January 2027
        res_jan = await client.get(f"/api/v1/admin/students/{student_id}?month=2027-01")
        assert res_jan.status_code == 200
        stats_jan = res_jan.json()["attendance_stats"]
        assert stats_jan["month"] == "2027-01"
        assert stats_jan["present_count"] == 0
        assert stats_jan["late_count"] == 1
        assert stats_jan["total_lessons"] == 1


async def test_draft_attendance_excluded_from_stats(model_database: Database) -> None:
    async with model_database.session() as session:
        t_staff, sub, g, p, s = await _create_test_hierarchy(session)
        # 1 finalized present
        await _add_finalized_attendance(
            session, g, s, t_staff, date(2026, 10, 2), AttendanceStatus.PRESENT
        )
        # 1 draft present (NOT finalized)
        await _add_draft_attendance(
            session, g, s, t_staff, date(2026, 10, 5), AttendanceStatus.PRESENT
        )
        await session.commit()
        student_id = s.id

    superadmin = await actor(model_database, role=Role.SUPERADMIN)
    async with client_for(superadmin) as client:
        res = await client.get(f"/api/v1/admin/students/{student_id}?month=2026-10")
        assert res.status_code == 200
        stats = res.json()["attendance_stats"]
        # Only the finalized record should be counted
        assert stats["present_count"] == 1
        assert stats["total_lessons"] == 1


async def test_transferred_student_aggregates_across_groups(model_database: Database) -> None:
    async with model_database.session() as session:
        t_staff, sub1, g1, p, s = await _create_test_hierarchy(session, group_name="Guruh 1")
        # Lesson in Group 1
        await _add_finalized_attendance(
            session, g1, s, t_staff, date(2026, 10, 2), AttendanceStatus.PRESENT
        )

        # Create Group 2 and transfer student
        g2 = group(
            subject_id=sub1.id,
            teacher_id=t_staff.id,
            name="Guruh 2",
            status=Status.ACTIVE,
        )
        session.add(g2)
        await session.flush()

        s.group_id = g2.id
        await session.flush()

        # Lesson in Group 2
        await _add_finalized_attendance(
            session, g2, s, t_staff, date(2026, 10, 15), AttendanceStatus.LATE
        )
        await session.commit()
        student_id = s.id

    superadmin = await actor(model_database, role=Role.SUPERADMIN)
    async with client_for(superadmin) as client:
        res = await client.get(f"/api/v1/admin/students/{student_id}?month=2026-10")
        assert res.status_code == 200
        stats = res.json()["attendance_stats"]
        assert stats["present_count"] == 1
        assert stats["late_count"] == 1
        assert stats["attended_count"] == 2
        assert stats["total_lessons"] == 2


async def test_admin_rbac_permission_filtering(model_database: Database) -> None:
    async with model_database.session() as session:
        t_staff, sub, g, p, s = await _create_test_hierarchy(session)
        await _add_finalized_attendance(
            session, g, s, t_staff, date(2026, 10, 2), AttendanceStatus.PRESENT
        )
        await session.commit()
        student_id = s.id

    # 1. Admin with students:read AND attendance:read -> sees stats
    admin_with_both = await actor(model_database, permissions=["students:read", "attendance:read"])
    async with client_for(admin_with_both) as client:
        res = await client.get(f"/api/v1/admin/students/{student_id}?month=2026-10")
        assert res.status_code == 200
        data = res.json()
        assert data["attendance_stats"] is not None
        assert data["attendance_stats"]["present_count"] == 1

    # 2. Admin with ONLY students:read (no attendance:read)
    # sees profile, but attendance_stats is null
    admin_only_students = await actor(model_database, permissions=["students:read"])
    async with client_for(admin_only_students) as client:
        res = await client.get(f"/api/v1/admin/students/{student_id}?month=2026-10")
        assert res.status_code == 200
        data = res.json()
        assert data["first_name"] == "Alisher"
        assert data["attendance_stats"] is None

    # 3. Admin without students:read -> 403 Forbidden
    admin_no_students = await actor(model_database, permissions=["attendance:read"])
    async with client_for(admin_no_students) as client:
        res = await client.get(f"/api/v1/admin/students/{student_id}?month=2026-10")
        assert res.status_code == 403


async def test_teacher_portal_detail_and_ownership(model_database: Database) -> None:
    owning_teacher_actor = await actor(model_database, role=Role.TEACHER)
    foreign_teacher_actor = await actor(model_database, role=Role.TEACHER)

    async with model_database.session() as session:
        t_staff = await session.get(Staff, owning_teacher_actor.staff_id)
        assert t_staff is not None
        _, sub, g, p, s = await _create_test_hierarchy(session, teacher_staff=t_staff)
        await _add_finalized_attendance(
            session, g, s, t_staff, date(2026, 10, 2), AttendanceStatus.PRESENT
        )
        await session.commit()
        student_id = s.id

    # 1. Owning teacher sees student detail and monthly stats
    async with client_for(owning_teacher_actor) as client:
        res = await client.get(f"/api/v1/teacher/students/{student_id}?month=2026-10")
        assert res.status_code == 200
        data = res.json()
        assert data["first_name"] == "Alisher"
        assert data["group_name"] == "Python Core"
        assert data["attendance_stats"] is not None
        assert data["attendance_stats"]["present_count"] == 1
        assert data["attendance_stats"]["total_lessons"] == 1

    # 2. Foreign teacher trying to get student -> 404 Not Found (ownership isolation)
    async with client_for(foreign_teacher_actor) as client:
        res = await client.get(f"/api/v1/teacher/students/{student_id}?month=2026-10")
        assert res.status_code == 404

    # 3. Teacher trying to access admin endpoint -> 403
    async with client_for(owning_teacher_actor) as client:
        res = await client.get(f"/api/v1/admin/students/{student_id}")
        assert res.status_code == 403

    # 4. Superadmin trying to access teacher endpoint -> 403
    superadmin = await actor(model_database, role=Role.SUPERADMIN)
    async with client_for(superadmin) as client:
        res = await client.get(f"/api/v1/teacher/students/{student_id}")
        assert res.status_code == 403


async def test_invalid_month_format_rejected(model_database: Database) -> None:
    async with model_database.session() as session:
        t_staff, sub, g, p, s = await _create_test_hierarchy(session)
        await session.commit()
        student_id = s.id

    superadmin = await actor(model_database, role=Role.SUPERADMIN)
    async with client_for(superadmin) as client:
        # Invalid month: month 13
        res = await client.get(f"/api/v1/admin/students/{student_id}?month=2026-13")
        assert res.status_code == 422

        # Invalid month: letters
        res = await client.get(f"/api/v1/admin/students/{student_id}?month=october")
        assert res.status_code == 422

        # Invalid month: missing month
        res = await client.get(f"/api/v1/admin/students/{student_id}?month=2026")
        assert res.status_code == 422
