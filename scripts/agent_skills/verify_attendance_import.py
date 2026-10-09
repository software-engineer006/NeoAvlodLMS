"""Test synthetic fixture dry-run, idempotent rerun, and rollback for attendance_import."""

import asyncio
import os
import uuid

from neoavlod.attendance_import import (
    apply_attendance_import,
    compute_plan_hash,
)
from neoavlod.database import Base, Database
from neoavlod.models import (
    Attendance,
    AttendanceBatch,
    Group,
    Role,
    Staff,
    Student,
    Subject,
)
from neoavlod.settings import Settings
from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.engine import make_url


async def main() -> None:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        raise RuntimeError("TEST_DATABASE_URL required")
    parsed = make_url(url)
    if parsed.host != "test-database" or parsed.database != "neoavlod_test":
        raise RuntimeError("Disposable Docker test-database required")

    settings = Settings(database_url=SecretStr(url), environment="test", _env_file=None)
    db = Database(settings)

    # Recreate tables in disposable test-database
    async with db.engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    print("1. Setting up synthetic fixture...")
    async with db.session() as session, session.begin():
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

        s1 = Student(first_name="Synthetic Student One", group_id=group.id)
        s2 = Student(first_name="Synthetic Student Two", group_id=group.id)
        s3 = Student(first_name="Synthetic Student Three", group_id=group.id)
        session.add_all([s1, s2, s3])

    synthetic_plan = {
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
                        "note": "A'lo",
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

    print("2. Testing first apply...")
    async with db.session() as session, session.begin():
        res1 = await apply_attendance_import(session, synthetic_plan)
        assert res1["batches_upserted"] == 2
        assert res1["records_upserted"] == 6
        assert res1["new_records_created"] == 6

    async with db.session() as session:
        batch_cnt = await session.scalar(
            select(func.count()).select_from(AttendanceBatch)
        )
        att_cnt = await session.scalar(select(func.count()).select_from(Attendance))
        assert batch_cnt == 2
        assert att_cnt == 6

        # Check batch linkage
        atts = (await session.scalars(select(Attendance))).all()
        for att in atts:
            assert att.batch_id is not None
            assert att.marked_by == teacher.id

    print("3. Testing idempotent rerun (0 new records created)...")
    async with db.session() as session, session.begin():
        res2 = await apply_attendance_import(session, synthetic_plan)
        assert res2["batches_upserted"] == 2
        assert res2["records_upserted"] == 6
        assert res2["new_records_created"] == 0

    async with db.session() as session:
        batch_cnt = await session.scalar(
            select(func.count()).select_from(AttendanceBatch)
        )
        att_cnt = await session.scalar(select(func.count()).select_from(Attendance))
        assert batch_cnt == 2
        assert att_cnt == 6

    print("4. Testing rollback on error...")
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
                        "student_name": "Unknown Person",
                        "date": "2026-10-03",
                        "status": "present",
                        "note": None,
                    }
                ],
            }
        ]
    }
    rolled_back = False
    try:
        async with db.session() as session, session.begin():
            await apply_attendance_import(session, bad_plan)
    except ValueError as e:
        assert "not found in group" in str(e)
        rolled_back = True

    assert rolled_back
    async with db.session() as session:
        # Counts must still be exactly 2 batches and 6 attendances (no partial batch from 2026-10-03)
        batch_cnt = await session.scalar(
            select(func.count()).select_from(AttendanceBatch)
        )
        att_cnt = await session.scalar(select(func.count()).select_from(Attendance))
        assert batch_cnt == 2
        assert att_cnt == 6

    print("5. Testing deterministic plan hash without private sources...")
    h = compute_plan_hash(synthetic_plan)
    assert len(h) == 64 and h == compute_plan_hash(synthetic_plan)

    await db.close()
    print("ALL SYNTHETIC FIXTURE, IDEMPOTENT RERUN, ROLLBACK AND AUDIT TESTS PASSED!")


if __name__ == "__main__":
    asyncio.run(main())
