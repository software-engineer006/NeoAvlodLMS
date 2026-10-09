import uuid
from datetime import date, time
from decimal import Decimal

import pytest
from factories import group, parent, student
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


async def _create_hierarchy(
    session: AsyncSession,
    teacher_staff: Staff,
    group_name: str = "History Test Group",
) -> tuple[Subject, Group, Parent, list[Student]]:
    sub = Subject(name=f"Fan_{uuid.uuid4().hex[:6]}", description="Tarix fani", is_active=True)
    session.add(sub)
    await session.flush()

    grp = group(
        subject_id=sub.id,
        teacher_id=teacher_staff.id,
        name=group_name,
        status=Status.ACTIVE,
        monthly_price=Decimal("400000.00"),
        days_of_week=[1, 3, 5],
        start_time=time(14, 0),
        end_time=time(15, 30),
        room_number="101",
    )
    session.add(grp)
    await session.flush()

    pr = parent(first_name="Rustam", last_name="Olimov")
    session.add(pr)
    await session.flush()

    s1 = student(
        group_id=grp.id,
        parent_id=pr.id,
        first_name="Bobur",
        last_name="Mirzo",
        age=16,
        status=Status.ACTIVE,
    )
    s2 = student(
        group_id=grp.id,
        parent_id=pr.id,
        first_name="Dilshod",
        last_name="Karimov",
        age=15,
        status=Status.ACTIVE,
    )
    session.add_all([s1, s2])
    await session.flush()

    return sub, grp, pr, [s1, s2]


async def _add_finalized_lesson(
    session: AsyncSession,
    grp: Group,
    teacher_staff: Staff,
    lesson_date: date,
    student_statuses: list[tuple[Student, AttendanceStatus, str | None]],
) -> AttendanceBatch:
    batch = AttendanceBatch(
        group_id=grp.id,
        date=lesson_date,
        finalized_by=teacher_staff.id,
    )
    session.add(batch)
    await session.flush()

    for std, st_val, note in student_statuses:
        att = Attendance(
            group_id=grp.id,
            student_id=std.id,
            date=lesson_date,
            status=st_val,
            note=note,
            marked_by=teacher_staff.id,
            batch_id=batch.id,
        )
        session.add(att)
    await session.flush()
    return batch


async def _add_draft_lesson(
    session: AsyncSession,
    grp: Group,
    teacher_staff: Staff,
    lesson_date: date,
    student_statuses: list[tuple[Student, AttendanceStatus, str | None]],
) -> None:
    for std, st_val, note in student_statuses:
        att = Attendance(
            group_id=grp.id,
            student_id=std.id,
            date=lesson_date,
            status=st_val,
            note=note,
            marked_by=teacher_staff.id,
            batch_id=None,
        )
        session.add(att)
    await session.flush()


async def test_attendance_history_28_day_month(model_database: Database) -> None:
    """Non-leap February (28 days): 2026-02-01 and 2026-02-28 included; 2026-03-01 excluded."""
    t_actor = await actor(model_database, role=Role.TEACHER)
    async with model_database.session() as session:
        t_staff = await session.get(Staff, t_actor.staff_id)
        assert t_staff is not None
        _, grp, _, students = await _create_hierarchy(session, teacher_staff=t_staff)
        s1, s2 = students

        await _add_finalized_lesson(
            session,
            grp,
            t_staff,
            date(2026, 2, 1),
            [(s1, AttendanceStatus.PRESENT, "Vaqtida keldi"), (s2, AttendanceStatus.ABSENT, None)],
        )
        await _add_finalized_lesson(
            session,
            grp,
            t_staff,
            date(2026, 2, 28),
            [(s1, AttendanceStatus.LATE, "5 min"), (s2, AttendanceStatus.PRESENT, None)],
        )
        # Out-of-range lesson: 2026-03-01
        await _add_finalized_lesson(
            session,
            grp,
            t_staff,
            date(2026, 3, 1),
            [(s1, AttendanceStatus.PRESENT, None), (s2, AttendanceStatus.PRESENT, None)],
        )
        await session.commit()
        grp_id = grp.id

    async with client_for(t_actor) as client:
        resp = await client.get(f"/api/v1/teacher/groups/{grp_id}/attendance/history?month=2026-02")
        assert resp.status_code == 200
        data = resp.json()
        assert data["month"] == "2026-02"
        assert len(data["dates"]) == 2
        assert "2026-02-01" in data["dates"]
        assert "2026-02-28" in data["dates"]
        assert "2026-03-01" not in data["dates"]
        assert data["summary"]["total_lessons"] == 2
        assert data["summary"]["present_count"] == 2
        assert data["summary"]["late_count"] == 1
        assert data["summary"]["absent_count"] == 1


async def test_attendance_history_29_day_leap_month(model_database: Database) -> None:
    """Leap February (29 days): 2024-02-29 is included; 2024-03-01 is excluded."""
    t_actor = await actor(model_database, role=Role.TEACHER)
    async with model_database.session() as session:
        t_staff = await session.get(Staff, t_actor.staff_id)
        assert t_staff is not None
        _, grp, _, students = await _create_hierarchy(session, teacher_staff=t_staff)
        s1, s2 = students

        await _add_finalized_lesson(
            session,
            grp,
            t_staff,
            date(2024, 2, 29),
            [(s1, AttendanceStatus.PRESENT, None), (s2, AttendanceStatus.LATE, "Kechikdi")],
        )
        await _add_finalized_lesson(
            session,
            grp,
            t_staff,
            date(2024, 3, 1),
            [(s1, AttendanceStatus.PRESENT, None), (s2, AttendanceStatus.PRESENT, None)],
        )
        await session.commit()
        grp_id = grp.id

    async with client_for(t_actor) as client:
        resp = await client.get(f"/api/v1/teacher/groups/{grp_id}/attendance/history?month=2024-02")
        assert resp.status_code == 200
        data = resp.json()
        assert data["month"] == "2024-02"
        assert data["dates"] == ["2024-02-29"]
        assert data["summary"]["total_lessons"] == 1
        assert data["summary"]["present_count"] == 1
        assert data["summary"]["late_count"] == 1


async def test_attendance_history_30_and_31_day_months(model_database: Database) -> None:
    """30-day month (2026-04) and 31-day month (2026-03) handling."""
    t_actor = await actor(model_database, role=Role.TEACHER)
    async with model_database.session() as session:
        t_staff = await session.get(Staff, t_actor.staff_id)
        assert t_staff is not None
        _, grp, _, students = await _create_hierarchy(session, teacher_staff=t_staff)
        s1, s2 = students

        # 30-day month (April 30)
        await _add_finalized_lesson(
            session,
            grp,
            t_staff,
            date(2026, 4, 30),
            [(s1, AttendanceStatus.PRESENT, None), (s2, AttendanceStatus.PRESENT, None)],
        )
        # 31-day month (March 31)
        await _add_finalized_lesson(
            session,
            grp,
            t_staff,
            date(2026, 3, 31),
            [(s1, AttendanceStatus.PRESENT, None), (s2, AttendanceStatus.ABSENT, None)],
        )
        await session.commit()
        grp_id = grp.id

    async with client_for(t_actor) as client:
        # April (30 days)
        resp_apr = await client.get(
            f"/api/v1/teacher/groups/{grp_id}/attendance/history?month=2026-04"
        )
        assert resp_apr.status_code == 200
        assert resp_apr.json()["dates"] == ["2026-04-30"]

        # March (31 days)
        resp_mar = await client.get(
            f"/api/v1/teacher/groups/{grp_id}/attendance/history?month=2026-03"
        )
        assert resp_mar.status_code == 200
        assert resp_mar.json()["dates"] == ["2026-03-31"]


async def test_attendance_history_year_boundary(model_database: Database) -> None:
    """Year boundary: 2025-12 vs 2026-01."""
    t_actor = await actor(model_database, role=Role.TEACHER)
    async with model_database.session() as session:
        t_staff = await session.get(Staff, t_actor.staff_id)
        assert t_staff is not None
        _, grp, _, students = await _create_hierarchy(session, teacher_staff=t_staff)
        s1, s2 = students

        await _add_finalized_lesson(
            session,
            grp,
            t_staff,
            date(2025, 12, 31),
            [(s1, AttendanceStatus.PRESENT, None), (s2, AttendanceStatus.LATE, None)],
        )
        await _add_finalized_lesson(
            session,
            grp,
            t_staff,
            date(2026, 1, 1),
            [(s1, AttendanceStatus.ABSENT, None), (s2, AttendanceStatus.PRESENT, None)],
        )
        await session.commit()
        grp_id = grp.id

    async with client_for(t_actor) as client:
        # 2025-12
        resp_dec = await client.get(
            f"/api/v1/teacher/groups/{grp_id}/attendance/history?month=2025-12"
        )
        assert resp_dec.status_code == 200
        assert resp_dec.json()["dates"] == ["2025-12-31"]

        # 2026-01
        resp_jan = await client.get(
            f"/api/v1/teacher/groups/{grp_id}/attendance/history?month=2026-01"
        )
        assert resp_jan.status_code == 200
        assert resp_jan.json()["dates"] == ["2026-01-01"]


async def test_attendance_history_draft_exclusion(model_database: Database) -> None:
    """Draft attendances are strictly excluded from history."""
    t_actor = await actor(model_database, role=Role.TEACHER)
    async with model_database.session() as session:
        t_staff = await session.get(Staff, t_actor.staff_id)
        assert t_staff is not None
        _, grp, _, students = await _create_hierarchy(session, teacher_staff=t_staff)
        s1, s2 = students

        # Finalized on 2026-05-10
        await _add_finalized_lesson(
            session,
            grp,
            t_staff,
            date(2026, 5, 10),
            [(s1, AttendanceStatus.PRESENT, None), (s2, AttendanceStatus.PRESENT, None)],
        )
        # Draft on 2026-05-12
        await _add_draft_lesson(
            session,
            grp,
            t_staff,
            date(2026, 5, 12),
            [(s1, AttendanceStatus.ABSENT, "Draft note"), (s2, AttendanceStatus.LATE, None)],
        )
        await session.commit()
        grp_id = grp.id

    async with client_for(t_actor) as client:
        resp = await client.get(f"/api/v1/teacher/groups/{grp_id}/attendance/history?month=2026-05")
        assert resp.status_code == 200
        data = resp.json()
        assert data["dates"] == ["2026-05-10"]
        assert len(data["records"]) == 2
        assert all(r["date"] == "2026-05-10" for r in data["records"])
        assert data["summary"]["total_lessons"] == 1


async def test_attendance_history_multi_records_no_truncation(model_database: Database) -> None:
    """Multiple lessons and students across month: all records and student stats returned."""
    t_actor = await actor(model_database, role=Role.TEACHER)
    async with model_database.session() as session:
        t_staff = await session.get(Staff, t_actor.staff_id)
        assert t_staff is not None
        _, grp, pr, students = await _create_hierarchy(session, teacher_staff=t_staff)
        # Add 2 more students
        s3 = student(
            group_id=grp.id, parent_id=pr.id, first_name="Zayniddin", last_name="Vohidov", age=16
        )
        s4 = student(
            group_id=grp.id, parent_id=pr.id, first_name="Olim", last_name="Shodiyev", age=17
        )
        session.add_all([s3, s4])
        await session.flush()
        all_students = students + [s3, s4]

        # 5 distinct dates
        dates_list = [date(2026, 6, d) for d in [1, 5, 10, 15, 20]]
        for d in dates_list:
            statuses = [
                (all_students[0], AttendanceStatus.PRESENT, None),
                (all_students[1], AttendanceStatus.LATE, "Kech"),
                (all_students[2], AttendanceStatus.ABSENT, "Sababli"),
                (all_students[3], AttendanceStatus.PRESENT, None),
            ]
            await _add_finalized_lesson(session, grp, t_staff, d, statuses)
        await session.commit()
        grp_id = grp.id
        all_std_ids = [s.id for s in all_students]

    async with client_for(t_actor) as client:
        resp = await client.get(f"/api/v1/teacher/groups/{grp_id}/attendance/history?month=2026-06")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["dates"]) == 5
        assert len(data["records"]) == 20  # 4 students * 5 dates
        assert data["summary"]["total_lessons"] == 5
        assert data["summary"]["total_records"] == 20
        assert data["summary"]["present_count"] == 10
        assert data["summary"]["late_count"] == 5
        assert data["summary"]["absent_count"] == 5

        # Check per-student summaries
        assert len(data["students_summary"]) == 4
        s_map = {s["student_id"]: s for s in data["students_summary"]}
        # Student 0 was PRESENT 5 times
        assert s_map[str(all_std_ids[0])]["present_count"] == 5
        assert s_map[str(all_std_ids[0])]["attended_count"] == 5
        assert s_map[str(all_std_ids[0])]["total_lessons"] == 5
        # Student 1 was LATE 5 times
        assert s_map[str(all_std_ids[1])]["late_count"] == 5
        assert s_map[str(all_std_ids[1])]["attended_count"] == 5
        # Student 2 was ABSENT 5 times
        assert s_map[str(all_std_ids[2])]["absent_count"] == 5
        assert s_map[str(all_std_ids[2])]["attended_count"] == 0


async def test_attendance_history_transfer_and_deactivation_preservation(
    model_database: Database,
) -> None:
    """Historical attendance is preserved even if student is transferred or deactivated."""
    t_actor = await actor(model_database, role=Role.TEACHER)
    async with model_database.session() as session:
        t_staff = await session.get(Staff, t_actor.staff_id)
        assert t_staff is not None
        sub, grp1, pr, students = await _create_hierarchy(
            session, teacher_staff=t_staff, group_name="Guruh 1"
        )
        s1, s2 = students

        # Finalized lesson on 2026-07-05 in grp1
        await _add_finalized_lesson(
            session,
            grp1,
            t_staff,
            date(2026, 7, 5),
            [(s1, AttendanceStatus.PRESENT, None), (s2, AttendanceStatus.LATE, None)],
        )

        # Create grp2
        grp2 = group(
            subject_id=sub.id,
            teacher_id=t_staff.id,
            name="Guruh 2",
            status=Status.ACTIVE,
        )
        session.add(grp2)
        await session.flush()

        # Transfer s1 to grp2
        s1.group_id = grp2.id
        # Deactivate s2
        s2.status = Status.INACTIVE

        # Add s3 to grp1
        s3 = student(
            group_id=grp1.id,
            parent_id=pr.id,
            first_name="Madina",
            last_name="Saidova",
            status=Status.ACTIVE,
        )
        session.add(s3)
        await session.commit()
        grp1_id = grp1.id
        s1_id = s1.id
        s2_id = s2.id
        s3_id = s3.id

    async with client_for(t_actor) as client:
        resp = await client.get(
            f"/api/v1/teacher/groups/{grp1_id}/attendance/history?month=2026-07"
        )
        assert resp.status_code == 200
        data = resp.json()
        # s1 and s2 records on 2026-07-05 must still be in grp1 history!
        rec_student_ids = {r["student_id"] for r in data["records"]}
        assert str(s1_id) in rec_student_ids
        assert str(s2_id) in rec_student_ids

        # s3 is in students_summary because currently active in grp1, but has 0 absent/present
        s_summary_map = {s["student_id"]: s for s in data["students_summary"]}
        assert str(s3_id) in s_summary_map
        assert s_summary_map[str(s3_id)]["absent_count"] == 0
        assert s_summary_map[str(s3_id)]["present_count"] == 0
        assert s_summary_map[str(s3_id)]["total_lessons"] == 0


async def test_attendance_history_rbac(model_database: Database) -> None:
    """RBAC validation: Superadmin, Admin with/without attendance:read, Teacher ownership."""
    t_actor1 = await actor(model_database, role=Role.TEACHER)
    t_actor2 = await actor(model_database, role=Role.TEACHER)
    s_admin_act = await actor(model_database, role=Role.SUPERADMIN)
    adm_with_att_act = await actor(
        model_database,
        role=Role.ADMIN,
        permissions=["attendance:read", "groups:read"],
    )
    adm_no_att_act = await actor(
        model_database,
        role=Role.ADMIN,
        permissions=["groups:read"],
    )

    async with model_database.session() as session:
        t_staff1 = await session.get(Staff, t_actor1.staff_id)
        assert t_staff1 is not None
        _, grp1, _, students = await _create_hierarchy(
            session, teacher_staff=t_staff1, group_name="Ustoz 1 guruhi"
        )
        s1, s2 = students
        await _add_finalized_lesson(
            session,
            grp1,
            t_staff1,
            date(2026, 8, 10),
            [(s1, AttendanceStatus.PRESENT, None), (s2, AttendanceStatus.PRESENT, None)],
        )
        await session.commit()
        grp1_id = grp1.id

    # 1. Superadmin -> OK on admin endpoints
    async with client_for(s_admin_act) as client:
        resp = await client.get(
            f"/api/v1/admin/attendance/history?group_id={grp1_id}&month=2026-08"
        )
        assert resp.status_code == 200
        resp2 = await client.get(f"/api/v1/admin/groups/{grp1_id}/attendance/history?month=2026-08")
        assert resp2.status_code == 200

    # 2. Admin with attendance:read -> OK
    async with client_for(adm_with_att_act) as client:
        resp = await client.get(
            f"/api/v1/admin/attendance/history?group_id={grp1_id}&month=2026-08"
        )
        assert resp.status_code == 200
        resp2 = await client.get(f"/api/v1/admin/groups/{grp1_id}/attendance/history?month=2026-08")
        assert resp2.status_code == 200

    # 3. Admin WITHOUT attendance:read -> 403 Forbidden
    async with client_for(adm_no_att_act) as client:
        resp = await client.get(
            f"/api/v1/admin/attendance/history?group_id={grp1_id}&month=2026-08"
        )
        assert resp.status_code == 403
        resp2 = await client.get(f"/api/v1/admin/groups/{grp1_id}/attendance/history?month=2026-08")
        assert resp2.status_code == 403

    # 4. Teacher 1 (owner) -> OK on teacher endpoint
    async with client_for(t_actor1) as client:
        resp = await client.get(
            f"/api/v1/teacher/groups/{grp1_id}/attendance/history?month=2026-08"
        )
        assert resp.status_code == 200
        # But 403 on admin endpoint
        resp_admin = await client.get(
            f"/api/v1/admin/attendance/history?group_id={grp1_id}&month=2026-08"
        )
        assert resp_admin.status_code == 403

    # 5. Teacher 2 (foreign teacher) -> 404 Not Found on teacher endpoint
    async with client_for(t_actor2) as client:
        resp = await client.get(
            f"/api/v1/teacher/groups/{grp1_id}/attendance/history?month=2026-08"
        )
        assert resp.status_code == 404

    # 6. Admin accessing teacher endpoint -> 403 Forbidden
    async with client_for(adm_with_att_act) as client:
        resp = await client.get(
            f"/api/v1/teacher/groups/{grp1_id}/attendance/history?month=2026-08"
        )
        assert resp.status_code == 403


async def test_attendance_history_invalid_month(model_database: Database) -> None:
    """Invalid month string formats return 422."""
    t_actor = await actor(model_database, role=Role.TEACHER)
    async with model_database.session() as session:
        t_staff = await session.get(Staff, t_actor.staff_id)
        assert t_staff is not None
        _, grp, _, _ = await _create_hierarchy(session, teacher_staff=t_staff)
        await session.commit()
        grp_id = grp.id

    async with client_for(t_actor) as client:
        for bad_month in ["invalid", "2026-13", "2026-00", "2026", "26-05"]:
            resp = await client.get(
                f"/api/v1/teacher/groups/{grp_id}/attendance/history?month={bad_month}"
            )
            assert resp.status_code == 422, (
                f"Expected 422 for month '{bad_month}', got {resp.status_code}"
            )


async def test_attendance_history_nonexistent_group(model_database: Database) -> None:
    """Non-existent group ID returns 404 on both admin and teacher routes."""
    s_admin_act = await actor(model_database, role=Role.SUPERADMIN)
    t_actor = await actor(model_database, role=Role.TEACHER)
    fake_id = uuid.uuid4()

    async with client_for(s_admin_act) as client:
        resp = await client.get(
            f"/api/v1/admin/attendance/history?group_id={fake_id}&month=2026-08"
        )
        assert resp.status_code == 404
        resp2 = await client.get(f"/api/v1/admin/groups/{fake_id}/attendance/history?month=2026-08")
        assert resp2.status_code == 404

    async with client_for(t_actor) as client:
        resp = await client.get(
            f"/api/v1/teacher/groups/{fake_id}/attendance/history?month=2026-08"
        )
        assert resp.status_code == 404
