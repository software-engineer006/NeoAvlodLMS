"""Exercise the private real CSV plan only in the disposable Docker database."""

import asyncio
import copy
import hashlib
import json
import os
from pathlib import Path

from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.engine import make_url

from neoavlod.database import Base, Database
from neoavlod.models import Attendance, Group, Parent, Role, Staff, Student
from neoavlod.models.common import Status
from neoavlod.roster_import import apply_plan, build_plan
from neoavlod.settings import Settings


async def main() -> None:
    url = os.environ["TEST_DATABASE_URL"]
    parsed = make_url(url)
    if parsed.host != "test-database" or parsed.database != "neoavlod_test":
        raise RuntimeError("Disposable Docker database required")
    root = Path("/workspace/.private/real-data/source")
    plan = build_plan(root)
    assert plan.summary()["by_file"] == {
        "it_even.csv": 11, "it_odd.csv": 9, "english_1.csv": 11, "english_2.csv": 50,
    }
    assert len(plan.groups) == 10 and len(plan.students) == 81
    assert plan.summary()["quarantine_reasons"] == {
        "duplicate_enrollment": 8, "maths_mapping_pending": 53, "non_student_label": 1,
    }
    # 142 roster rows = 81 accepted + 53 mathematics + 8 ambiguous duplicates.
    assert len(plan.students) + len(plan.quarantine) - 1 == 142
    db = Database(Settings(database_url=SecretStr(url), environment="test", _env_file=None))
    async with db.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    try:
        async with db.session() as session, session.begin():
            for username in {g.teacher_username for g in plan.groups}:
                session.add(Staff(first_name="Fixture", username=username,
                                  hashed_password="isolated-test-only", role=Role.TEACHER))
        async with db.session() as session, session.begin():
            assert await apply_plan(session, plan) == {
                "created_groups": 10, "created_students": 81, "quarantine": 62,
            }
        async with db.session() as session, session.begin():
            assert (await apply_plan(session, plan))["created_students"] == 0
            assert await session.scalar(select(func.count()).select_from(Student)) == 81
            assert await session.scalar(select(func.count()).select_from(Group)) == 10
            assert await session.scalar(select(func.count()).select_from(Parent)) == 0
            assert await session.scalar(select(func.count()).select_from(Attendance)) == 0
            for pupil in plan.students:
                record = await session.scalar(select(Student).where(Student.source_key == pupil.key))
                assert record is not None
                assert record.first_name == pupil.full_name and record.last_name is None
                assert record.phone == pupil.phone and record.school_grade == pupil.school_grade
                assert record.source_data == pupil.source and record.status == Status.ACTIVE
                assert record.parent_id is None and record.age is None
            for item in plan.groups:
                group = await session.scalar(select(Group).where(Group.source_key == item.key))
                assert group is not None
                teacher = await session.get(Staff, group.teacher_id)
                assert teacher and teacher.username == item.teacher_username
                assert group.days_of_week == item.days and group.source_data == item.source
        # Changed source must fail without leaving any partial changes.
        changed = copy.deepcopy(plan)
        changed.students[-1].source["contact_raw"] = "changed source"
        try:
            async with db.session() as session, session.begin():
                await apply_plan(session, changed)
            raise AssertionError("Source conflict accepted")
        except ValueError as error:
            assert "source differs" in str(error)
        constrained = copy.deepcopy(plan)
        for group in constrained.groups:
            group.key += ":capacity"
            group.name += " capacity"
        for pupil in constrained.students:
            pupil.key += ":capacity"
            pupil.group_key += ":capacity"
        try:
            async with db.session() as session, session.begin():
                await apply_plan(session, constrained, capacity=1)
            raise AssertionError("Capacity overflow accepted")
        except ValueError as error:
            assert "capacity" in str(error)
        # A real enrolment may appear in both subjects and must not be collapsed.
        memberships: dict[str, set[str]] = {}
        by_key = {g.key: g for g in plan.groups}
        for pupil in plan.students:
            memberships.setdefault(pupil.full_name.casefold(), set()).add(by_key[pupil.group_key].subject)
        cross_subject = sum(len(subjects) > 1 for subjects in memberships.values())
        async with db.session() as session:
            assert await session.scalar(select(func.count()).select_from(Student)) == 81
            assert await session.scalar(select(func.count()).select_from(Group)) == 10
        assert all(hashlib.sha256((root / name).read_bytes()).hexdigest() == digest
                   for name, digest in plan.files.items())
        print(json.dumps({"verified": True, "groups": 10, "enrollments": 81,
                          "quarantine": 62, "cross_subject_names": cross_subject,
                          "rerun": "unchanged", "source_conflict": "rollback",
                          "capacity": "rollback", "source_files": "unchanged"}))
    finally:
        async with db.engine.begin() as connection:
            await connection.run_sync(Base.metadata.drop_all)
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
