import csv
from pathlib import Path

import pytest

from neoavlod.refresh_sources import FILES, build_refresh_manifest


def source_files(root: Path) -> Path:
    root.mkdir()
    for filename in FILES:
        header = ["T/r", "Guruh nomi", "Teacher", "Ism va familiya", "Telefon raqam", "Sinf"]
        row = [
            "1",
            Path(filename).stem,
            "Namuna Ustoz",
            "Namuna O‘quvchi",
            "90 000 00 00",
            "7-sinf",
        ]
        if filename.startswith("English"):
            header.append("Darajasi")
            row.append("Beginner")
        header += [
            "Dars kuni",
            "Dars vaqti",
            "Maktabi",
            "MyGov statusi",
            "1-dars (14-oktyabr)",
            "2-dars (16-oktyabr)",
            'Jami kelgan ("k")',
            "Izoh",
        ]
        row += [
            "Dushanba, Chorshanba va Juma",
            "9:00-10:30",
            "26",
            "o'tdi",
            "k",
            "",
            "1",
            "Birinchi satr\nikkinchi satr",
        ]
        footer = [""] * len(header)
        footer[0] = 'Jami qatnashganlar ("k" soni):'
        footer[-4:] = ["1", "0", "1", ""]
        with (root / filename).open("w", newline="") as stream:
            csv.writer(stream).writerows([header, row, footer])
    return root


def rewrite(root: Path, filename: str, column: str, value: str) -> None:
    path = root / filename
    with path.open(newline="") as stream:
        rows = list(csv.reader(stream))
    rows[1][rows[0].index(column)] = value
    with path.open("w", newline="") as stream:
        csv.writer(stream).writerows(rows)


def test_one_person_seven_memberships_exact_marks_and_raw_provenance(tmp_path: Path) -> None:
    root = source_files(tmp_path / "csv")
    plan = build_refresh_manifest(root, year=2026)
    assert plan.summary() == {
        "files": 7,
        "groups": 7,
        "profiles": 1,
        "memberships": 7,
        "source_rows": 7,
        "present_drafts": 7,
        "absent_inferred": 0,
        "profiles_to_review": 0,
    }
    assert plan.digest() == build_refresh_manifest(root, year=2026).digest()
    assert plan.people[0].phone == "+998900000000"
    assert plan.enrollments[0].notes == "Birinchi satr\nikkinchi satr"
    assert all(e.present_dates == ["2026-10-14"] for e in plan.enrollments)
    assert all(g.room_number == "217" for g in plan.groups if g.file.startswith("Python"))


def test_conflicting_profile_fields_are_reviewed_not_guessed(tmp_path: Path) -> None:
    root = source_files(tmp_path / "csv")
    rewrite(root, FILES[-1], "Telefon raqam", "91 000 00 00")
    rewrite(root, FILES[-1], "Sinf", "8-sinf")
    rewrite(root, FILES[-1], "Maktabi", "27")
    person = build_refresh_manifest(root, year=2026).people[0]
    assert person.phone is person.school_grade is person.school_name is None
    assert person.phone_candidates == ["+998900000000", "+998910000000"]
    assert person.review_fields == ["phone", "school_grade", "school_name"]


@pytest.mark.parametrize(
    "column,value",
    [("1-dars (14-oktyabr)", "p"), ('Jami kelgan ("k")', "0"), ("Guruh nomi", "Boshqa")],
)
def test_rejects_unreviewed_tokens_or_failed_reconciliation(
    tmp_path: Path,
    column: str,
    value: str,
) -> None:
    root = source_files(tmp_path / "csv")
    rewrite(root, FILES[0], column, value)
    with pytest.raises(ValueError):
        build_refresh_manifest(root, year=2026)


def test_authoritative_schedule_override_and_invalid_phone_preservation(tmp_path: Path) -> None:
    root = source_files(tmp_path / "csv")
    rewrite(root, FILES[-1], "Telefon raqam", "noto‘g‘ri raqam")
    plan = build_refresh_manifest(
        root, year=2026, time_overrides={Path(FILES[-1]).stem: ("16:00", "18:00")}
    )
    assert (plan.groups[-1].start_time, plan.groups[-1].end_time) == ("16:00", "18:00")
    assert plan.groups[-1].source_times == ["9:00-10:30"]
    assert "invalid_source_phone" in plan.people[0].review_fields
    assert plan.people[0].sources[-1].cells[4] == "noto‘g‘ri raqam"


def test_duplicate_course_rows_merge_and_conflicting_schedule_requires_approval(
    tmp_path: Path,
) -> None:
    root = source_files(tmp_path / "csv")
    path = root / FILES[-1]
    with path.open(newline="") as stream:
        header, one, footer = list(csv.reader(stream))
    two = one.copy()
    two[0] = "2"
    two[header.index("Dars vaqti")] = "15:00-16:30"
    footer[-4] = footer[-2] = "2"
    with path.open("w", newline="") as stream:
        csv.writer(stream).writerows([header, one, two, footer])
    with pytest.raises(ValueError, match="tasdiq kerak"):
        build_refresh_manifest(root, year=2026)
    plan = build_refresh_manifest(
        root, year=2026, time_overrides={Path(FILES[-1]).stem: ("16:00", "18:00")}
    )
    assert plan.summary()["source_rows"] == 8
    assert plan.summary()["profiles"] == 1
    assert plan.summary()["memberships"] == plan.summary()["present_drafts"] == 7
    assert len(plan.enrollments[-1].sources) == 2
