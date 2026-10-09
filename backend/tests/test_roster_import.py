import csv
from pathlib import Path

import pytest
from factories import staff
from sqlalchemy import func, select

from neoavlod.database import Database
from neoavlod.models import Group, Role, Student, Subject
from neoavlod.roster_import import FILES, apply_plan, build_plan, parse_phone, parse_times


def sources(root: Path) -> Path:
    root.mkdir(exist_ok=True)
    for name in FILES:
        odd = name in {"it_odd.csv", "english_1.csv"}
        label = "Beginner" if name.startswith("english") else "Pyhton"
        rows = [
            ["", "", "", label, "Toq kuni" if odd else "Juft kuni", "15:00-16:30"],
            ["mygov", "Maktab", "", "Ism", "Raqam", "Sinf"],
            ["", "25", "1", f"Original {name}", "90 123 45 67", "7-sinf", "k", ""],
            ["", "", "", "", "", ""],
        ]
        with (root / name).open("w", newline="", encoding="utf-8") as file:
            csv.writer(file).writerows(rows)
    return root


def test_plan_preserves_source_and_ambiguous_contacts(tmp_path: Path) -> None:
    plan = build_plan(sources(tmp_path / "csv"))
    assert len(plan.students) == 4 and len(plan.groups) == 4
    assert len(plan.files) == 4
    assert plan.students[0].source["row"] == 3
    assert plan.students[0].source["cells"][6:] == ["k", ""]
    assert parse_phone("90 123 45 67 Mother") == "+998901234567"
    assert parse_phone("90 123 45 67 91 234 56 78") is None
    assert parse_phone("") is None
    assert parse_times("09:30")[1] is None
    assert parse_times("") == (None, None)
    assert build_plan(tmp_path / "csv").digest() == plan.digest()


def test_duplicates_and_maths_are_quarantined(tmp_path: Path) -> None:
    root = sources(tmp_path / "csv")
    with (root / "it_even.csv").open("a", newline="", encoding="utf-8") as file:
        csv.writer(file).writerows(
            [
                ["", "", "", "Original it_even.csv", "901234567", "7-sinf"],
                ["", "", "", "Matematika", "Juft", "9:30-11:00"],
                ["", "", "", "Another Name", "", "8-sinf"],
            ]
        )
    plan = build_plan(root)
    reasons = [r["reason"] for r in plan.quarantine]
    assert reasons.count("duplicate_enrollment") == 2
    assert reasons.count("maths_mapping_pending") == 1
    assert not any(s.source["file"] == "it_even.csv" for s in plan.students)
    assert any(g.subject == "Matematika" for g in build_plan(root, maths="separate").groups)


@pytest.mark.anyio
async def test_apply_is_idempotent_and_capacity_failure_rolls_back(
    model_database: Database,
    tmp_path: Path,
) -> None:
    plan = build_plan(sources(tmp_path / "csv"))
    async with model_database.session() as session:
        for name in ("teacher_dilmurod", "teacher_jasurbek", "teacher_ingliz"):
            session.add(staff(username=name, role=Role.TEACHER))
        await session.commit()
    async with model_database.session() as session, session.begin():
        result = await apply_plan(session, plan)
        assert result["created_students"] == 4
    async with model_database.session() as session, session.begin():
        assert (await apply_plan(session, plan))["created_students"] == 0
        assert await session.scalar(select(func.count()).select_from(Student)) == 4
    # Another cohort is deliberately constrained; even new subjects/groups roll back.
    for group in plan.groups:
        group.key += ":second"
        group.name += " Second"
        group.subject = "Rollback subject"
    for learner in plan.students:
        learner.key += ":second"
        learner.group_key += ":second"
    plan.students.append(
        type(plan.students[0])(
            key="extra",
            group_key=plan.students[0].group_key,
            full_name="Extra Student",
            phone=None,
            school_grade=None,
            source={"file": "fixture", "row": 10},
        )
    )
    with pytest.raises(ValueError, match="capacity"):
        async with model_database.session() as session, session.begin():
            await apply_plan(session, plan, capacity=1)
    async with model_database.session() as session:
        assert (
            await session.scalar(select(Subject.id).where(Subject.name == "Rollback subject"))
            is None
        )
        assert await session.scalar(select(func.count()).select_from(Group)) == 4
        assert await session.scalar(select(func.count()).select_from(Student)) == 4
