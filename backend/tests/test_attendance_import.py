import csv
import json
import uuid
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import func, select

from neoavlod.attendance_import import (
    FILE_MAPPING,
    apply_attendance_import,
    build_attendance_plan,
    compute_plan_hash,
    parse_cell_status_and_note,
)
from neoavlod.database import Database
from neoavlod.models import (
    Attendance,
    AttendanceBatch,
    Group,
    NotificationOutbox,
    Role,
    Staff,
    Student,
    Subject,
)
from neoavlod.services.attendance import get_group_monthly_attendance_history

pytestmark = pytest.mark.anyio


def test_parse_cell_status_and_note() -> None:
    assert parse_cell_status_and_note("") == ("absent", None)
    assert parse_cell_status_and_note("   ") == ("absent", None)
    assert parse_cell_status_and_note("k") == ("present", None)
    assert parse_cell_status_and_note("K") == ("present", None)
    assert parse_cell_status_and_note("kasal bop qopti") == ("absent", "kasal bop qopti")
    assert parse_cell_status_and_note("kelmas ekan") == ("absent", "kelmas ekan")


def test_build_legacy_attendance_plan_without_private_sources(tmp_path: Path) -> None:
    # Legacy spreadsheets use fixed reviewed sections. Keep this regression
    # executable in CI even after the user's original private CSVs are replaced.
    source_dir = tmp_path / "legacy"
    source_dir.mkdir()
    for filename in FILE_MAPPING.values():
        rows = [["", "", "", f"Synthetic Student {i}"] + [""] * 10 for i in range(1, 106)]
        if filename == FILE_MAPPING["it_even"]:
            rows[10][6] = "k"
            rows[11][6] = "Synthetic note"
        with (source_dir / filename).open("w", newline="") as file:
            csv.writer(file).writerows(rows)
    (source_dir / "legacy-attendance-overrides.json").write_text(
        json.dumps({"english_pre_extra": ["Synthetic Extra One", "Synthetic Extra Two"]})
    )

    plan = build_attendance_plan(source_dir)
    summary = plan["summary"]
    assert summary["groups_count"] == 10
    assert summary["total_students"] == 81
    assert summary["total_lessons"] == 29
    assert summary["total_records"] == 302
    assert summary["present_count"] == 1
    assert summary["absent_count"] == 301
    assert summary["with_notes_count"] == 1

    h1 = compute_plan_hash(plan)
    h2 = compute_plan_hash(plan)
    assert h1 == h2
    assert len(h1) == 64


async def test_apply_attendance_import_lifecycle_and_idempotency(
    model_database: Database,
) -> None:
    # 1. Setup test teacher, subject, group, students
    teacher_id = uuid.uuid4()
    group_id = uuid.uuid4()
    async with model_database.session() as session, session.begin():
        teacher = Staff(
            id=teacher_id,
            first_name="Dilmurod",
            last_name="Amonov",
            username="teacher_dilmurod",
            hashed_password="hash",
            role=Role.TEACHER,
        )
        session.add(teacher)
        subject = Subject(name="Python&vibecoding")
        session.add(subject)
        await session.flush()

        group = Group(
            id=group_id,
            name="Python&vibecoding — Juft kunlar",
            subject_id=subject.id,
            teacher_id=teacher.id,
            days_of_week=[2, 4, 6],
            max_students=30,
        )
        session.add(group)
        await session.flush()

        s1 = Student(first_name="Synthetic Student One", group_id=group.id)
        s2 = Student(first_name="Synthetic Student Two", group_id=group.id)
        s3 = Student(first_name="Synthetic Student Three", group_id=group.id)
        session.add_all([s1, s2, s3])

    plan = {
        "groups": [
            {
                "group_name": "Python&vibecoding — Juft kunlar",
                "subject_name": "Python&vibecoding",
                "teacher_username": "teacher_dilmurod",
                "dates": ["2026-09-26", "2026-09-29"],
                "records": [
                    {
                        "group_name": "Python&vibecoding — Juft kunlar",
                        "student_name": "Synthetic Student One",
                        "date": "2026-09-26",
                        "status": "present",
                        "note": None,
                    },
                    {
                        "group_name": "Python&vibecoding — Juft kunlar",
                        "student_name": "Synthetic Student Two",
                        "date": "2026-09-26",
                        "status": "absent",
                        "note": None,
                    },
                    {
                        "group_name": "Python&vibecoding — Juft kunlar",
                        "student_name": "Synthetic Student Three",
                        "date": "2026-09-26",
                        "status": "present",
                        "note": "Top student",
                    },
                    {
                        "group_name": "Python&vibecoding — Juft kunlar",
                        "student_name": "Synthetic Student One",
                        "date": "2026-09-29",
                        "status": "present",
                        "note": None,
                    },
                    {
                        "group_name": "Python&vibecoding — Juft kunlar",
                        "student_name": "Synthetic Student Two",
                        "date": "2026-09-29",
                        "status": "present",
                        "note": None,
                    },
                    {
                        "group_name": "Python&vibecoding — Juft kunlar",
                        "student_name": "Synthetic Student Three",
                        "date": "2026-09-29",
                        "status": "absent",
                        "note": "Kasal",
                    },
                ],
            }
        ]
    }

    # 2. Initial import
    async with model_database.session() as session, session.begin():
        res1 = await apply_attendance_import(session, plan)
        assert res1["batches_upserted"] == 2
        assert res1["records_upserted"] == 6
        assert res1["new_records_created"] == 6

    # Verify batches and records in database
    async with model_database.session() as session:
        batch_cnt = await session.scalar(select(func.count()).select_from(AttendanceBatch))
        att_cnt = await session.scalar(select(func.count()).select_from(Attendance))
        outbox_cnt = await session.scalar(select(func.count()).select_from(NotificationOutbox))
        assert batch_cnt == 2
        assert att_cnt == 6
        assert outbox_cnt == 0  # No spam notifications for historical imports

        # Check batch_id linkage and marked_by
        batches = (await session.scalars(select(AttendanceBatch))).all()
        batch_map = {b.date: b for b in batches}
        atts = (await session.scalars(select(Attendance))).all()
        for att in atts:
            assert att.batch_id == batch_map[att.date].id
            assert att.marked_by == teacher_id

    # 3. Idempotent rerun
    async with model_database.session() as session, session.begin():
        res2 = await apply_attendance_import(session, plan)
        assert res2["batches_upserted"] == 2
        assert res2["records_upserted"] == 6
        assert res2["new_records_created"] == 0

    async with model_database.session() as session:
        batch_cnt2 = await session.scalar(select(func.count()).select_from(AttendanceBatch))
        att_cnt2 = await session.scalar(select(func.count()).select_from(Attendance))
        assert batch_cnt2 == 2
        assert att_cnt2 == 6

        # 4. Monthly history service integration check
        history = await get_group_monthly_attendance_history(session, group_id, "2026-09")
        assert history.group_id == group_id
        assert history.month == "2026-09"
        assert len(history.dates) == 2
        assert date(2026, 9, 26) in history.dates
        assert date(2026, 9, 29) in history.dates
        assert history.summary.total_lessons == 2
        assert history.summary.total_records == 6
        assert history.summary.present_count == 4
        assert history.summary.absent_count == 2
        assert len(history.students_summary) == 3


async def test_apply_attendance_import_rollback(model_database: Database) -> None:
    async with model_database.session() as session, session.begin():
        teacher = Staff(
            id=uuid.uuid4(),
            first_name="Dilmurod",
            last_name="Amonov",
            username="teacher_dilmurod",
            hashed_password="hash",
            role=Role.TEACHER,
        )
        session.add(teacher)
        subject = Subject(name="Python&vibecoding")
        session.add(subject)
        await session.flush()

        group = Group(
            id=uuid.uuid4(),
            name="Python&vibecoding — Juft kunlar",
            subject_id=subject.id,
            teacher_id=teacher.id,
            days_of_week=[2, 4, 6],
            max_students=30,
        )
        session.add(group)
        await session.flush()

    bad_plan = {
        "groups": [
            {
                "group_name": "Python&vibecoding — Juft kunlar",
                "subject_name": "Python&vibecoding",
                "teacher_username": "teacher_dilmurod",
                "dates": ["2026-10-03"],
                "records": [
                    {
                        "group_name": "Python&vibecoding — Juft kunlar",
                        "student_name": "Nonexistent Student",
                        "date": "2026-10-03",
                        "status": "present",
                        "note": None,
                    }
                ],
            }
        ]
    }

    with pytest.raises(ValueError, match="not found in group"):
        async with model_database.session() as session, session.begin():
            await apply_attendance_import(session, bad_plan)

    async with model_database.session() as session:
        batch_cnt = await session.scalar(select(func.count()).select_from(AttendanceBatch))
        att_cnt = await session.scalar(select(func.count()).select_from(Attendance))
        assert batch_cnt == 0
        assert att_cnt == 0
