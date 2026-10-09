"""Idempotent attendance import service and CLI for NeoAvlod LMS."""

import argparse
import asyncio
import csv
import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from neoavlod.database import Database
from neoavlod.models import Attendance, AttendanceBatch, AttendanceStatus, Group, Staff, Student
from neoavlod.settings import Settings

ATTENDANCE_IMPORT_LOCK = 0x4E454F073

FILE_MAPPING = {
    "it_even": "2026-2027 - IT_juft.csv",
    "it_odd": "2026-2027 - IT_Toq _Jasurbek.csv",
    "english_1": "2026-2027 - Ingliz tili_1_smena.csv",
    "english_2": "2026-2027 - Ingliz tili2 .csv",
}


def normalize_name(s: str) -> str:
    return " ".join(s.replace("’", "'").replace("‘", "'").replace("\\", "").split()).casefold()


def parse_cell_status_and_note(cell_value: str) -> tuple[str, str | None]:
    """Applies the rule:

    - 'k' (or 'K') -> present
    - empty -> absent, note=None
    - other text -> absent, note=text
    """
    cleaned = cell_value.strip()
    if not cleaned:
        return "absent", None
    if cleaned.casefold() == "k":
        return "present", None
    return "absent", cleaned


@dataclass
class AttendanceEntry:
    group_name: str
    student_name: str
    date: str  # YYYY-MM-DD
    status: str  # "present" or "absent"
    note: str | None = None
    source_file: str = ""
    source_row: int = 0


@dataclass
class GroupAttendancePlan:
    group_name: str
    subject_name: str
    teacher_username: str
    dates: list[str]
    student_count: int
    records: list[AttendanceEntry] = field(default_factory=list)


def build_attendance_plan(data_dir: Path) -> dict[str, Any]:
    # 1. Parse IT Juft: "Python&vibecoding — Juft kunlar"
    it_juft_path = data_dir / FILE_MAPPING["it_even"]
    it_juft_rows = list(csv.reader(it_juft_path.read_text(encoding="utf-8-sig").splitlines()))
    it_juft_cols = [
        (6, "2026-09-26"),
        (7, "2026-09-29"),
        (9, "2026-10-03"),
        (10, "2026-10-06"),
        (11, "2026-10-08"),
    ]
    it_juft_plan = GroupAttendancePlan(
        group_name="Python&vibecoding — Juft kunlar",
        subject_name="Python&vibecoding",
        teacher_username="teacher_dilmurod",
        dates=[d for _, d in it_juft_cols],
        student_count=11,
    )
    for r_num in range(11, 22):
        row = it_juft_rows[r_num - 1]
        student_name = " ".join(row[3].split())
        for c_idx, d_str in it_juft_cols:
            raw_cell = row[c_idx] if c_idx < len(row) else ""
            status, note = parse_cell_status_and_note(raw_cell)
            it_juft_plan.records.append(
                AttendanceEntry(
                    group_name=it_juft_plan.group_name,
                    student_name=student_name,
                    date=d_str,
                    status=status,
                    note=note,
                    source_file=FILE_MAPPING["it_even"],
                    source_row=r_num,
                )
            )

    # 2. Parse IT Toq: "Python&vibecoding — Toq kunlar"
    it_toq_path = data_dir / FILE_MAPPING["it_odd"]
    it_toq_rows = list(csv.reader(it_toq_path.read_text(encoding="utf-8-sig").splitlines()))
    it_toq_cols = [
        (6, "2026-09-23"),
        (7, "2026-09-25"),
        (8, "2026-09-28"),
        (9, "2026-09-30"),
        (11, "2026-10-02"),
        (12, "2026-10-05"),
        (13, "2026-10-07"),
    ]
    it_toq_plan = GroupAttendancePlan(
        group_name="Python&vibecoding — Toq kunlar",
        subject_name="Python&vibecoding",
        teacher_username="teacher_jasurbek",
        dates=[d for _, d in it_toq_cols],
        student_count=9,
    )
    for r_num in range(4, 13):
        row = it_toq_rows[r_num - 1]
        student_name = " ".join(row[3].split())
        for c_idx, d_str in it_toq_cols:
            raw_cell = row[c_idx] if c_idx < len(row) else ""
            status, note = parse_cell_status_and_note(raw_cell)
            it_toq_plan.records.append(
                AttendanceEntry(
                    group_name=it_toq_plan.group_name,
                    student_name=student_name,
                    date=d_str,
                    status=status,
                    note=note,
                    source_file=FILE_MAPPING["it_odd"],
                    source_row=r_num,
                )
            )

    # 3. Parse English 1-smena: 4 groups
    eng1_path = data_dir / FILE_MAPPING["english_1"]
    eng1_rows = list(csv.reader(eng1_path.read_text(encoding="utf-8-sig").splitlines()))
    eng1_groups_def = [
        ("Ingliz tili — Beginner · 1-smena", [5, 6, 7]),
        ("Ingliz tili — Elementary · 1-smena", [12, 13, 14]),
        ("Ingliz tili — Pre-intermediate · 1-smena", [19, 20, 21]),
        ("Ingliz tili — Intermediate · 1-smena", [28, 29]),
    ]
    eng1_plans = []
    for g_name, r_nums in eng1_groups_def:
        g_plan = GroupAttendancePlan(
            group_name=g_name,
            subject_name="Ingliz tili",
            teacher_username="teacher_ingliz",
            dates=["2026-10-02"],
            student_count=len(r_nums),
        )
        for r_num in r_nums:
            row = eng1_rows[r_num - 1]
            student_name = " ".join(row[3].split())
            col_6_val = row[6] if len(row) > 6 else ""
            status, note = parse_cell_status_and_note(col_6_val)
            if len(row) > 11 and row[11].strip() and not note:
                note = row[11].strip()
            g_plan.records.append(
                AttendanceEntry(
                    group_name=g_name,
                    student_name=student_name,
                    date="2026-10-02",
                    status=status,
                    note=note,
                    source_file=FILE_MAPPING["english_1"],
                    source_row=r_num,
                )
            )
        eng1_plans.append(g_plan)

    # 4. Parse English 2-smena: 4 groups
    eng2_path = data_dir / FILE_MAPPING["english_2"]
    eng2_rows = list(csv.reader(eng2_path.read_text(encoding="utf-8-sig").splitlines()))

    # a) Beginner: 2 dates: 2026-10-06, 2026-10-08
    eng2_beginner_plan = GroupAttendancePlan(
        group_name="Ingliz tili — Beginner · 2-smena",
        subject_name="Ingliz tili",
        teacher_username="teacher_ingliz",
        dates=["2026-10-06", "2026-10-08"],
        student_count=6,
    )
    beg_rows = [4, 5, 7, 8, 9, 10]
    beg_cols = [(7, "2026-10-06"), (8, "2026-10-08")]
    for r_num in beg_rows:
        row = eng2_rows[r_num - 1]
        student_name = " ".join(row[3].split())
        for c_idx, d_str in beg_cols:
            raw_cell = row[c_idx] if c_idx < len(row) else ""
            status, note = parse_cell_status_and_note(raw_cell)
            if not note and len(row) > 12 and row[12].strip():
                note = row[12].strip()
            eng2_beginner_plan.records.append(
                AttendanceEntry(
                    group_name=eng2_beginner_plan.group_name,
                    student_name=student_name,
                    date=d_str,
                    status=status,
                    note=note,
                    source_file=FILE_MAPPING["english_2"],
                    source_row=r_num,
                )
            )

    # b) Elementary: 3 dates: 2026-10-03, 2026-10-06, 2026-10-08
    elem_rows = [r for r in range(17, 33) if r != 29]
    elem_cols = [(6, "2026-10-03"), (7, "2026-10-06"), (8, "2026-10-08")]
    eng2_elementary_plan = GroupAttendancePlan(
        group_name="Ingliz tili — Elementary · 2-smena",
        subject_name="Ingliz tili",
        teacher_username="teacher_ingliz",
        dates=[d for _, d in elem_cols],
        student_count=len(elem_rows),
    )
    for r_num in elem_rows:
        row = eng2_rows[r_num - 1]
        student_name = " ".join(row[3].split())
        for c_idx, d_str in elem_cols:
            raw_cell = row[c_idx] if c_idx < len(row) else ""
            status, note = parse_cell_status_and_note(raw_cell)
            eng2_elementary_plan.records.append(
                AttendanceEntry(
                    group_name=eng2_elementary_plan.group_name,
                    student_name=student_name,
                    date=d_str,
                    status=status,
                    note=note,
                    source_file=FILE_MAPPING["english_2"],
                    source_row=r_num,
                )
            )

    # c) Pre-intermediate: 4 dates: 2026-10-01, 2026-10-03, 2026-10-06, 2026-10-08
    pre_cols = [
        (6, "2026-10-01"),
        (7, "2026-10-03"),
        (8, "2026-10-06"),
        (9, "2026-10-08"),
    ]
    eng2_pre_plan = GroupAttendancePlan(
        group_name="Ingliz tili — Pre-intermediate · 2-smena",
        subject_name="Ingliz tili",
        teacher_username="teacher_ingliz",
        dates=[d for _, d in pre_cols],
        student_count=0,
    )
    pre_names_rows: list[tuple[str, int, list[str]]] = []
    for r_num in range(39, 57):
        row = eng2_rows[r_num - 1]
        pre_names_rows.append((" ".join(row[3].split()), r_num, row))
    row_79 = eng2_rows[79 - 1]
    pre_names_rows.append((" ".join(row_79[3].split()), 79, row_79))
    # Additional reviewed legacy enrollments belong in private data, never source code.
    overrides_path = data_dir / "legacy-attendance-overrides.json"
    if overrides_path.is_file():
        overrides = json.loads(overrides_path.read_text(encoding="utf-8"))
        for extra in overrides.get("english_pre_extra", []):
            if not isinstance(extra, str) or not extra.strip():
                raise ValueError("Invalid private legacy attendance override")
            pre_names_rows.append((" ".join(extra.split()), 0, []))
    eng2_pre_plan.student_count = len(pre_names_rows)

    for s_name, r_num, row in pre_names_rows:
        for c_idx, d_str in pre_cols:
            raw_cell = row[c_idx] if r_num > 0 and c_idx < len(row) else ""
            status, note = parse_cell_status_and_note(raw_cell)
            eng2_pre_plan.records.append(
                AttendanceEntry(
                    group_name=eng2_pre_plan.group_name,
                    student_name=s_name,
                    date=d_str,
                    status=status,
                    note=note,
                    source_file=FILE_MAPPING["english_2"] if r_num > 0 else "source_roster",
                    source_row=r_num,
                )
            )

    # d) Intermediate: 4 dates: 2026-10-01, 2026-10-03, 2026-10-06, 2026-10-08
    inter_cols = [
        (6, "2026-10-01"),
        (7, "2026-10-03"),
        (8, "2026-10-06"),
        (9, "2026-10-08"),
    ]
    inter_students_rows = [62, 63, 64, 65, 66, 67, 78, 101]
    eng2_inter_plan = GroupAttendancePlan(
        group_name="Ingliz tili — Intermediate · 2-smena",
        subject_name="Ingliz tili",
        teacher_username="teacher_ingliz",
        dates=[d for _, d in inter_cols],
        student_count=len(inter_students_rows),
    )
    for r_num in inter_students_rows:
        row = eng2_rows[r_num - 1]
        s_name = " ".join(row[3].split())
        for c_idx, d_str in inter_cols:
            raw_cell = row[c_idx] if c_idx < len(row) else ""
            status, note = parse_cell_status_and_note(raw_cell)
            eng2_inter_plan.records.append(
                AttendanceEntry(
                    group_name=eng2_inter_plan.group_name,
                    student_name=s_name,
                    date=d_str,
                    status=status,
                    note=note,
                    source_file=FILE_MAPPING["english_2"],
                    source_row=r_num,
                )
            )

    all_groups = [
        it_juft_plan,
        it_toq_plan,
        *eng1_plans,
        eng2_beginner_plan,
        eng2_elementary_plan,
        eng2_pre_plan,
        eng2_inter_plan,
    ]

    total_records = sum(len(g.records) for g in all_groups)
    total_present = sum(sum(1 for r in g.records if r.status == "present") for g in all_groups)
    total_absent = sum(sum(1 for r in g.records if r.status == "absent") for g in all_groups)
    total_notes = sum(sum(1 for r in g.records if r.note) for g in all_groups)
    total_lessons = sum(len(g.dates) for g in all_groups)
    total_students = sum(g.student_count for g in all_groups)

    result = {
        "summary": {
            "groups_count": len(all_groups),
            "total_students": total_students,
            "total_lessons": total_lessons,
            "total_records": total_records,
            "present_count": total_present,
            "absent_count": total_absent,
            "with_notes_count": total_notes,
        },
        "groups": [
            {
                "group_name": g.group_name,
                "subject_name": g.subject_name,
                "teacher_username": g.teacher_username,
                "dates": g.dates,
                "student_count": g.student_count,
                "present_count": sum(1 for r in g.records if r.status == "present"),
                "absent_count": sum(1 for r in g.records if r.status == "absent"),
                "records_count": len(g.records),
                "records": [asdict(r) for r in g.records],
            }
            for g in all_groups
        ],
    }
    return result


def compute_plan_hash(plan_dict: dict[str, Any]) -> str:
    serialized = json.dumps(plan_dict, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


async def apply_attendance_import(
    session: AsyncSession,
    plan_dict: dict[str, Any],
) -> dict[str, int]:
    """Caller owns the transaction; this function never commits partial results.

    Applies the attendance plan idempotently with advisory locking.
    """
    await session.execute(
        text("SELECT pg_advisory_xact_lock(:key)"), {"key": ATTENDANCE_IMPORT_LOCK}
    )

    groups = (await session.scalars(select(Group))).all()
    group_map = {g.name: g for g in groups}

    batches_upserted = 0
    records_upserted = 0
    new_records_created = 0

    for g_plan in plan_dict["groups"]:
        g_name = g_plan["group_name"]
        group = group_map.get(g_name)
        if group is None:
            raise ValueError(f"Import group not found in database: {g_name}")

        teacher_id = group.teacher_id
        if teacher_id is None:
            # Fallback to teacher_username
            teacher_username = g_plan["teacher_username"]
            teacher = await session.scalar(select(Staff).where(Staff.username == teacher_username))
            if teacher is None:
                raise ValueError(f"Teacher not found: {teacher_username}")
            teacher_id = teacher.id

        # Map active students by normalized name
        students = (
            await session.scalars(select(Student).where(Student.group_id == group.id))
        ).all()
        student_map = {normalize_name(st.first_name): st for st in students}

        # 1. Upsert AttendanceBatch for each lesson date in group
        batch_ids: dict[date, Any] = {}
        for d_str in g_plan["dates"]:
            target_date = date.fromisoformat(d_str)
            batch_stmt = (
                insert(AttendanceBatch)
                .values(
                    group_id=group.id,
                    date=target_date,
                    finalized_by=teacher_id,
                )
                .on_conflict_do_update(
                    constraint="uq_attendance_batches_group_date",
                    set_={"finalized_by": teacher_id},
                )
                .returning(AttendanceBatch.id)
            )
            batch_id = await session.scalar(batch_stmt)
            batch_ids[target_date] = batch_id
            batches_upserted += 1

        # 2. Upsert Attendance records
        for rec in g_plan["records"]:
            target_date = date.fromisoformat(rec["date"])
            st_name_norm = normalize_name(rec["student_name"])
            student = student_map.get(st_name_norm)
            if student is None:
                raise ValueError(f"Student '{rec['student_name']}' not found in group '{g_name}'")

            batch_id = batch_ids[target_date]
            status_enum = (
                AttendanceStatus.PRESENT if rec["status"] == "present" else AttendanceStatus.ABSENT
            )
            note_val = rec.get("note")

            # Check if record already existed prior to upsert
            existing_att = await session.scalar(
                select(Attendance.id).where(
                    Attendance.group_id == group.id,
                    Attendance.student_id == student.id,
                    Attendance.date == target_date,
                )
            )

            att_stmt = (
                insert(Attendance)
                .values(
                    group_id=group.id,
                    student_id=student.id,
                    date=target_date,
                    status=status_enum,
                    note=note_val,
                    marked_by=teacher_id,
                    batch_id=batch_id,
                )
                .on_conflict_do_update(
                    constraint="uq_attendance_group_student_date",
                    set_={
                        "status": status_enum,
                        "note": note_val,
                        "marked_by": teacher_id,
                        "batch_id": batch_id,
                        "updated_at": func.now(),
                    },
                )
            )
            await session.execute(att_stmt)
            records_upserted += 1
            if existing_att is None:
                new_records_created += 1

    return {
        "batches_upserted": batches_upserted,
        "records_upserted": records_upserted,
        "new_records_created": new_records_created,
    }


async def run(args: argparse.Namespace) -> None:
    if args.plan:
        plan_dict = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    elif args.source:
        plan_dict = build_attendance_plan(Path(args.source))
    else:
        default_plan = Path("/workspace/.private/real-data/attendance-plan.json")
        if default_plan.exists():
            plan_dict = json.loads(default_plan.read_text(encoding="utf-8"))
        else:
            plan_dict = build_attendance_plan(Path("/workspace/educenter_data"))

    plan_hash = compute_plan_hash(plan_dict)
    summary = plan_dict["summary"]

    output: dict[str, Any] = {
        "summary": summary,
        "plan_sha256": plan_hash,
    }

    if args.report:
        report_path = Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps({**output, "plan": plan_dict}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        report_path.chmod(0o600)
        output["report_written"] = str(report_path)

    if args.apply:
        if args.expected_plan and args.expected_plan != plan_hash:
            raise ValueError(
                f"Expected plan hash {args.expected_plan} did not match computed {plan_hash}"
            )
        database = Database(Settings())
        try:
            async with database.session() as session, session.begin():
                result = await apply_attendance_import(session, plan_dict)
                output["result"] = result
        finally:
            await database.close()

    print(json.dumps(output, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, help="Directory containing educenter CSVs")
    parser.add_argument("--plan", type=Path, help="JSON file containing audited attendance plan")
    parser.add_argument("--report", type=Path, help="Write full audit report to path")
    parser.add_argument("--apply", action="store_true", help="Apply attendance import to database")
    parser.add_argument("--expected-plan", type=str, help="Verify expected plan hash before apply")
    args = parser.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
