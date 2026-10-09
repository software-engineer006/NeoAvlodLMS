import csv
from datetime import date, time
from pathlib import Path

import pytest
from factories import staff
from sqlalchemy import func, select

from neoavlod.database import Database
from neoavlod.educenter_import import (
    FILES,
    LESSONS,
    SCHEDULES,
    SUBJECT,
    apply_educenter,
    build_plan,
)
from neoavlod.models import (
    Attendance,
    AttendanceBatch,
    AttendanceStatus,
    Group,
    NotificationOutbox,
    Role,
    Student,
    Subject,
)
from neoavlod.services.attendance import get_group_monthly_attendance_history


def sources(root: Path) -> Path:
    root.mkdir()
    for index, filename in enumerate(FILES):
        header = ["Mygov", "Maktab", "", "Ism", "Raqam", "Sinf"] + [""] * 9
        for col, day in LESSONS[index].items():
            header[col] = str(int(day[-2:]))
        if index == 2:
            header[6] = "23"
        one = ["o'tdi", "1", "1", f"Learner {index} A", "90 123 45 67", "7-sinf"] + [""] * 9
        two = ["", "2", "2", f"Learner {index} B", "90 123 45 67 / 91 234 56 78", ""] + [""] * 9
        for col in LESSONS[index]:
            one[col] = "k"
        two[min(LESSONS[index])] = "p"
        with (root / filename).open("w", newline="") as f:
            csv.writer(f, delimiter=";").writerows([header, one, two, [""] * 15])
    return root


def test_semicolon_dates_unknown_and_exact_schedules(tmp_path: Path) -> None:
    source = sources(tmp_path / "csv")
    plan = build_plan(source)
    assert plan.digest() == build_plan(source).digest()
    assert plan.summary()["students"] == 8
    assert plan.summary()["lessons"] == 22
    assert plan.summary()["present"] == 22
    assert plan.summary()["absent"] == 18
    assert len(plan.unknown_cells) == 4
    assert all(s.phone is None for s in plan.roster.students[1::2])
    assert plan.roster.students[0].source["cells"][0] == "o'tdi"
    assert plan.roster.students[0].source["row"] == 2
    assert plan.lessons[plan.roster.groups[2].key] == ["2026-10-06", "2026-10-08"]
    for i, g in enumerate(plan.roster.groups):
        assert g.name == Path(FILES[i]).stem
        assert g.subject == SUBJECT
        assert (g.teacher_username, g.days, g.start, g.end) == SCHEDULES[i]


def test_duplicate_and_unreviewed_dates_refused(tmp_path: Path) -> None:
    root = sources(tmp_path / "csv")
    file = root / FILES[0]
    rows = list(csv.reader(file.read_text().splitlines(), delimiter=";"))
    rows.append(rows[1])
    file.write_text("\n".join(";".join(r) for r in rows))
    with pytest.raises(ValueError, match="Duplicate"):
        build_plan(root)
    rows.pop()
    rows[0][10] = "1"
    file.write_text("\n".join(";".join(r) for r in rows))
    with pytest.raises(ValueError, match="Unreviewed"):
        build_plan(root)


async def teachers(db: Database) -> None:
    async with db.session() as s, s.begin():
        for username in {r[0] for r in SCHEDULES}:
            s.add(staff(username=username, role=Role.TEACHER))


@pytest.mark.anyio
async def test_atomic_rerun_monthly_stats_and_conflicting_history(
    model_database: Database,
    tmp_path: Path,
) -> None:
    plan = build_plan(sources(tmp_path / "csv"))
    await teachers(model_database)
    async with model_database.session() as s, s.begin():
        result = await apply_educenter(s, plan)
        assert result["created_groups"] == 4 and result["created_students"] == 8
        assert result["created_attendance"] == 40 and result["created_batches"] == 22
    async with model_database.session() as s, s.begin():
        result = await apply_educenter(s, plan)
        assert all(v == 0 for k, v in result.items() if k.startswith("created"))
        assert await s.scalar(select(func.count()).select_from(NotificationOutbox)) == 0
        group = await s.scalar(select(Group).where(Group.source_key == plan.roster.groups[0].key))
        assert group and group.start_time == time(14, 30)
        history = await get_group_monthly_attendance_history(s, group.id, "2026-09")
        assert history.summary.present_count == 4 and history.summary.absent_count == 3
        record = await s.scalar(
            select(Attendance).where(
                Attendance.group_id == group.id, Attendance.date == date(2026, 9, 23)
            )
        )
        assert record
        record.status = AttendanceStatus.ABSENT
    with pytest.raises(ValueError, match="history conflict"):
        async with model_database.session() as s, s.begin():
            await apply_educenter(s, plan)
    async with model_database.session() as s:
        assert await s.scalar(select(func.count()).select_from(Attendance)) == 40


@pytest.mark.anyio
async def test_capacity_and_missing_teacher_rollback(
    model_database: Database, tmp_path: Path
) -> None:
    plan = build_plan(sources(tmp_path / "csv"))
    with pytest.raises(ValueError, match="teacher missing"):
        async with model_database.session() as s, s.begin():
            await apply_educenter(s, plan)
    await teachers(model_database)
    with pytest.raises(ValueError, match="capacity"):
        async with model_database.session() as s, s.begin():
            await apply_educenter(s, plan, capacity=1)
    async with model_database.session() as s:
        for model in (Group, Subject, Student, AttendanceBatch, Attendance):
            assert await s.scalar(select(func.count()).select_from(model)) == 0


@pytest.mark.anyio
async def test_changed_source_and_schedule_refused(
    model_database: Database, tmp_path: Path
) -> None:
    plan = build_plan(sources(tmp_path / "csv"))
    await teachers(model_database)
    async with model_database.session() as s, s.begin():
        await apply_educenter(s, plan)
    plan.roster.students[0].source = {"file": "changed"}
    with pytest.raises(ValueError, match="source differs"):
        async with model_database.session() as s, s.begin():
            await apply_educenter(s, plan)
    async with model_database.session() as s, s.begin():
        group = await s.scalar(select(Group))
        assert group
        group.start_time = time(1)
    with pytest.raises(ValueError, match="schedule differs"):
        async with model_database.session() as s, s.begin():
            await apply_educenter(s, plan)


@pytest.mark.anyio
async def test_cli_hash_guard_staff_roster_atomic_and_private_output(
    model_database: Database,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    import argparse
    import json

    from neoavlod.educenter_import import run
    from neoavlod.models import Staff
    from neoavlod.security.passwords import verify_password

    source = sources(tmp_path / "csv")
    profiles = [
        {"username": "ceo_mohira", "first_name": "Owner", "role": "superadmin"},
        {"username": "teacher_jasurbek", "first_name": "Jasur", "role": "teacher"},
        {"username": "teacher_dilmurod", "first_name": "Dilmurod", "role": "teacher"},
    ]
    (source / "staff-profiles.json").write_text(json.dumps(profiles))
    args = argparse.Namespace(
        source=source,
        year=2026,
        capacity=30,
        report=tmp_path / "private" / "plan.json",
        credentials=tmp_path / "private" / "accounts.json",
        apply=False,
        expected_plan=None,
    )
    await run(args)
    output = json.loads(capsys.readouterr().out)
    args.apply = True
    args.expected_plan = "wrong"
    with pytest.raises(ValueError, match="exact reviewed"):
        await run(args)
    assert not args.credentials.exists()
    args.expected_plan = output["plan_sha256"]
    await run(args)
    result = json.loads(capsys.readouterr().out)
    assert result["result"]["created_staff"] == 3
    accounts = json.loads(args.credentials.read_text())
    assert args.credentials.stat().st_mode & 0o777 == 0o600
    async with model_database.session() as s:
        for account in accounts:
            person = await s.scalar(
                select(Staff).where(Staff.username == account["profile"]["username"])
            )
            assert person and verify_password(person.hashed_password, account["password"])
    await run(args)
    rerun_text = capsys.readouterr().out
    rerun = json.loads(rerun_text)
    assert all(v == 0 for k, v in rerun["result"].items() if k.startswith("created"))
    assert all(a["password"] not in rerun_text for a in accounts)
