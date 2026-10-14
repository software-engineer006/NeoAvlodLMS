import argparse
import csv
import json
from datetime import time
from pathlib import Path

import pytest
from factories import staff
from sqlalchemy import func, select

from neoavlod.database import Database
from neoavlod.english_import import (
    FILES,
    LESSONS,
    PROFILES,
    SCHEDULES,
    apply_english,
    build_plan,
    run,
)
from neoavlod.models import (
    Attendance,
    AttendanceBatch,
    AttendanceStatus,
    Group,
    ImportReceipt,
    NotificationOutbox,
    Role,
    Staff,
    Student,
    Subject,
)
from neoavlod.models.common import Status
from neoavlod.security.passwords import verify_password


def sources(root: Path) -> Path:
    root.mkdir()
    for i, filename in enumerate(FILES):
        header = ["mygov", "Maktab", "", "Ism", "Raqam", "Sinf"] + [""] * 5
        for col, day in LESSONS[i].items():
            header[col] = str(int(day[-2:]))
        rows = [
            ["", "", "", "Source teacher", "English-2-3", "", "Oktyabr"],
            ["", "", "", "Beginner", "Juft kuni", "16:30-18:00"],
            header,
            ["o'tdi", "1", "1", f"Learner {i} A", "90 123 45 67", "7-sinf", "k", "k", "kasal"],
            ["", "", "", "", "", "", "Oktyabr"],
            ["", "", "", "Elementary", "Juft kuni", ""],
            header,
            ["", "", "2", f"Learner {i} B", "90 123 45 67/91 234 56 78", "", "", "k"],
            ["", "", "", f"Learner {i} A", "901234567", "7-sinf", "", "k"],
            [""] * 9,
        ]
        if i == 0:
            rows.extend(
                [
                    ["", "", "", "Pre-inter", "Juft kuni", "09:30"],
                    header,
                    ["", "", "", "Learner extra", "91 123 45 67", "6-sinf"],
                ]
            )
        with (root / filename).open("w", newline="") as f:
            csv.writer(f, delimiter="," if i == 0 else ";").writerows(rows)
    return root


def test_mixed_delimiters_sections_merged_duplicate_and_explicit_schedule(tmp_path: Path) -> None:
    root = sources(tmp_path / "csv")
    plan = build_plan(root)
    assert plan.digest() == build_plan(root).digest()
    assert plan.summary()["students"] == 7
    for index, group in enumerate(plan.groups):
        assert group.name == Path(FILES[index]).stem
        assert group.subject == "Ingliz tili"
        assert (group.teacher_username, group.days, group.start, group.end) == SCHEDULES[index]
    pupil = plan.students[0]
    assert len(pupil.source["entries"]) == 2
    assert pupil.phone == "+998901234567"
    assert "kasal" in " ".join(pupil.source["notes"])
    assert plan.groups[0].source["attendance_policy"] == "admin_review_empty"
    assert all(g.source["attendance_policy"] == "dated_k_only_draft" for g in plan.groups[1:])
    assert plan.summary()["present_drafts"] == 6
    assert plan.summary()["undated_k_cells"] == 1
    assert plan.summary()["asila_k_cells_deferred"] == 4
    assert plan.students[1].phone is None
    assert plan.students[2].source["entries"][0]["section"] == "Pre-inter"


@pytest.mark.parametrize("change", ["duplicate_contact", "non_student", "header"])
def test_unreviewed_structure_or_ambiguous_duplicate_refused(tmp_path: Path, change: str) -> None:
    root = sources(tmp_path / "csv")
    file = root / FILES[0]
    rows = list(csv.reader(file.read_text().splitlines()))
    if change == "duplicate_contact":
        rows[8][4] = "91 123 45 67"
    elif change == "non_student":
        rows[8][3] = ""
    else:
        rows[2][4] = "New column"
    with file.open("w", newline="") as f:
        csv.writer(f).writerows(rows)
    with pytest.raises(ValueError):
        build_plan(root)


@pytest.mark.anyio
async def test_cli_atomic_hash_guard_idempotence_and_admin_profile_preserved(
    model_database: Database, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    args = argparse.Namespace(
        source=sources(tmp_path / "csv"),
        capacity=30,
        report=tmp_path / "private" / "plan.json",
        credentials=tmp_path / "private" / "accounts.json",
        apply=False,
        expected_plan=None,
    )
    await run(args)
    preview = json.loads(capsys.readouterr().out)
    assert not args.credentials.exists()
    assert args.report.stat().st_mode & 0o777 == 0o600
    async with model_database.session() as session:
        assert await session.scalar(select(func.count()).select_from(Staff)) == 0
    args.apply = True
    args.expected_plan = "wrong"
    with pytest.raises(ValueError, match="exact reviewed"):
        await run(args)
    assert not args.credentials.exists()
    args.expected_plan = preview["plan_sha256"]
    args.capacity = 1
    with pytest.raises(ValueError, match="capacity"):
        await run(args)
    async with model_database.session() as session:
        for model in (Staff, Group, Student, Subject, Attendance):
            assert await session.scalar(select(func.count()).select_from(model)) == 0
    args.capacity = 30
    await run(args)
    result = json.loads(capsys.readouterr().out)
    assert result["result"] == {
        "created_staff": 2,
        "created_groups": 3,
        "created_students": 7,
        "quarantine": 0,
        "created_attendance": 6,
    }
    accounts = json.loads(args.credentials.read_text())
    assert args.credentials.stat().st_mode & 0o777 == 0o600
    password_hashes = {}
    async with model_database.session() as session, session.begin():
        for index, account in enumerate(accounts):
            person = await session.scalar(
                select(Staff).where(Staff.username == account["profile"]["username"])
            )
            assert person and person.phone is None and person.must_change_password
            assert verify_password(person.hashed_password, account["password"])
            password_hashes[person.username] = person.hashed_password
            person.phone = f"+9989{index}1234567"  # Administrator's later profile edit.
        pupil = await session.scalar(select(Student))
        assert pupil
        edited_pupil_id = pupil.id
        pupil.phone = "+998991234567"
        record = await session.scalar(select(Attendance))
        assert record
        record.status = AttendanceStatus.ABSENT
        record.note = "Admin checked"
    await run(args)
    stdout = capsys.readouterr().out
    assert all(v == 0 for v in json.loads(stdout)["result"].values())
    assert all(a["password"] not in stdout for a in accounts)
    async with model_database.session() as session:
        for index, profile in enumerate(PROFILES):
            person = await session.scalar(select(Staff).where(Staff.username == profile.username))
            assert person and person.phone == f"+9989{index}1234567"
            assert person.hashed_password == password_hashes[person.username]
        assert await session.scalar(select(func.count()).select_from(Attendance)) == 6
        assert await session.scalar(select(func.count()).select_from(AttendanceBatch)) == 0
        record = await session.scalar(select(Attendance).where(Attendance.note == "Admin checked"))
        assert record and record.status == AttendanceStatus.ABSENT
        assert await session.scalar(select(func.count()).select_from(NotificationOutbox)) == 0
        pupil = await session.get(Student, edited_pupil_id)
        assert pupil and pupil.phone == "+998991234567"


@pytest.mark.anyio
async def test_schedule_source_and_transfer_conflicts_preserve_existing_data(
    model_database: Database, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = sources(tmp_path / "csv")
    args = argparse.Namespace(
        source=root,
        capacity=30,
        report=None,
        credentials=tmp_path / "private" / "accounts.json",
        apply=False,
        expected_plan=None,
    )
    await run(args)
    args.expected_plan = json.loads(capsys.readouterr().out)["plan_sha256"]
    args.apply = True
    await run(args)
    plan = build_plan(root)
    async with model_database.session() as session, session.begin():
        group = await session.scalar(select(Group).where(Group.source_key == plan.groups[0].key))
        assert group
        group.start_time = time(8)
    with pytest.raises(ValueError, match="schedule"):
        async with model_database.session() as session, session.begin():
            await apply_english(session, plan)
    async with model_database.session() as session, session.begin():
        group = await session.scalar(select(Group).where(Group.source_key == plan.groups[0].key))
        other = await session.scalar(select(Group).where(Group.source_key == plan.groups[1].key))
        pupil = await session.scalar(
            select(Student).where(Student.source_key == plan.students[0].key)
        )
        assert group and other and pupil
        group.start_time = time(9)
        pupil.group_id = other.id
    with pytest.raises(ValueError, match="transferred"):
        async with model_database.session() as session, session.begin():
            await apply_english(session, plan)
    plan.students[-1].source = {"file": "changed"}
    with pytest.raises(ValueError, match="source differs"):
        async with model_database.session() as session, session.begin():
            await apply_english(session, plan)
    async with model_database.session() as session:
        assert await session.scalar(select(func.count()).select_from(Student)) == 7


@pytest.mark.anyio
@pytest.mark.parametrize("change", [None, "first", "prefix", "family", "role", "inactive"])
async def test_existing_teacher_given_names_preserved_without_accepting_other_identity(
    model_database: Database, tmp_path: Path, capsys: pytest.CaptureFixture[str], change: str | None
) -> None:
    profile = PROFILES[0]
    person = staff(
        **(
            profile.model_dump()
            | {
                "first_name": "Asila Namuna",
                "phone": "+998991234567",
                "telegram_id": 881000,
                "must_change_password": False,
            }
        )
    )
    if change == "first":
        person.first_name = "Other Namuna"
    elif change == "prefix":
        person.first_name = "Asilabek Namuna"
    elif change == "family":
        person.last_name = "Other"
    elif change == "role":
        person.role = Role.ADMIN
    elif change == "inactive":
        person.status = Status.INACTIVE
    async with model_database.session() as session, session.begin():
        session.add(person)
        await session.flush()
        identity = person.id, person.auth_uuid, person.hashed_password
        old_name = person.first_name
    root = sources(tmp_path / "csv")
    from neoavlod.english_import import reviewed_digest

    args = argparse.Namespace(
        source=root,
        capacity=30,
        report=None,
        credentials=tmp_path / "private/accounts.json",
        apply=True,
        expected_plan=reviewed_digest(build_plan(root)),
        deployment_receipt=True,
    )
    if change:
        with pytest.raises(ValueError, match="Existing username differs"):
            await run(args)
        async with model_database.session() as session:
            for model in (Group, Student, Attendance, ImportReceipt):
                assert await session.scalar(select(func.count()).select_from(model)) == 0
            assert await session.scalar(select(func.count()).select_from(Staff)) == 1
    else:
        await run(args)
        assert json.loads(capsys.readouterr().out)["result"]["created_staff"] == 1
        await run(args)
        assert (
            json.loads(capsys.readouterr().out)["result"]["deployment_status"] == "already_applied"
        )
        async with model_database.session() as session:
            imported_group = await session.scalar(
                select(Group).where(Group.source_key == build_plan(root).groups[0].key)
            )
            assert imported_group and imported_group.teacher_id == identity[0]
    async with model_database.session() as session:
        preserved = await session.get(Staff, identity[0])
        assert preserved
        assert (preserved.id, preserved.auth_uuid, preserved.hashed_password) == identity
        assert preserved.first_name == old_name and preserved.phone == "+998991234567"
        assert preserved.telegram_id == 881000 and not preserved.must_change_password
