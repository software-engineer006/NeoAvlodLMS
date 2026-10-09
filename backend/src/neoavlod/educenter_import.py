"""Reviewed, atomic import of the four educenter Python CSVs and historical attendance."""

import argparse
import asyncio
import csv
import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import date, time
from pathlib import Path
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from neoavlod.database import Database
from neoavlod.errors import DomainError
from neoavlod.models import (
    Attendance,
    AttendanceBatch,
    AttendanceStatus,
    Group,
    Role,
    Student,
)
from neoavlod.real_staff import StaffSpec, prepare, private_write, provision_staff
from neoavlod.roster_import import (
    ImportPlan,
    RosterGroup,
    RosterStudent,
    apply_plan,
    normalized,
    parse_phone,
)
from neoavlod.settings import Settings

SUBJECT = "Python dasturlash&vibecoding"
FILES = tuple(f"Python&vibecoding {n}-gruh.csv" for n in range(1, 5))
# User reviewed: Group 3's ambiguous '23' is preserved raw, excluded from history.
LESSONS = (
    {6: "09-23", 7: "09-25", 8: "09-28", 9: "09-30", 11: "10-02", 12: "10-05", 13: "10-07"},
    {
        6: "09-23",
        7: "09-25",
        8: "09-28",
        9: "09-30",
        11: "10-02",
        12: "10-05",
        13: "10-07",
        14: "10-09",
    },
    {7: "10-06", 8: "10-08"},
    {6: "09-26", 7: "09-29", 9: "10-03", 10: "10-06", 11: "10-08"},
)
SCHEDULES = (
    ("teacher_jasurbek", [1, 3, 5], "14:30", "16:00"),
    ("teacher_jasurbek", [1, 3, 5], "16:30", "18:00"),
    ("teacher_dilmurod", [2, 4, 6], "09:30", "11:00"),
    ("teacher_dilmurod", [2, 4, 6], "16:00", "18:00"),
)


@dataclass
class EducPlan:
    roster: ImportPlan
    lessons: dict[str, list[str]] = field(default_factory=dict)
    attendance: list[dict[str, Any]] = field(default_factory=list)
    unknown_cells: list[dict[str, Any]] = field(default_factory=list)

    def summary(self) -> dict[str, Any]:
        return {
            **self.roster.summary(),
            "lessons": sum(len(v) for v in self.lessons.values()),
            "attendance": len(self.attendance),
            "present": sum(r["status"] == "present" for r in self.attendance),
            "absent": sum(r["status"] == "absent" for r in self.attendance),
            "unknown_cells": len(self.unknown_cells),
            "excluded_group3_column": "23",
        }

    def digest(self) -> str:
        return hashlib.sha256(
            json.dumps(asdict(self), sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()


def build_plan(source: Path, *, year: int = 2026) -> EducPlan:
    plan = EducPlan(ImportPlan(maths="not_applicable"))
    for index, filename in enumerate(FILES):
        raw = (source / filename).read_bytes()
        sha = hashlib.sha256(raw).hexdigest()
        plan.roster.files[filename] = sha
        rows = list(csv.reader(raw.decode("utf-8-sig").splitlines(), delimiter=";"))
        headers = [i for i, r in enumerate(rows) if len(r) > 3 and normalized(r[3]) == "ism"]
        if len(headers) != 1:
            raise ValueError(f"Expected one roster header: {filename}")
        header = headers[0]
        columns = LESSONS[index]
        if index == 2 and rows[header][6].strip() != "23":
            raise ValueError("Excluded Group3 date changed; review required")
        for col, month_day in columns.items():
            if col >= len(rows[header]) or rows[header][col].strip() != str(int(month_day[-2:])):
                raise ValueError(f"Attendance header changed: {filename}, column {col + 1}")
        # Never silently ignore a newly added dated column.
        dated = {c for c, v in enumerate(rows[header]) if c >= 6 and v.strip()}
        if dated != set(columns) | ({6} if index == 2 else set()):
            raise ValueError(f"Unreviewed attendance dates: {filename}")
        key = f"educenter:{year}:python:{index + 1}"
        teacher, days, start, end = SCHEDULES[index]
        plan.roster.groups.append(
            RosterGroup(
                key,
                Path(filename).stem,
                SUBJECT,
                teacher,
                days,
                start,
                end,
                {
                    "file": filename,
                    "sha256": sha,
                    "header": rows[: header + 1],
                    "year": year,
                    "excluded_columns": [6] if index == 2 else [],
                },
            )
        )
        plan.lessons[key] = [f"{year}-{v}" for v in columns.values()]
        for day in plan.lessons[key]:
            date.fromisoformat(day)
        names: set[str] = set()
        for row_number, original in enumerate(rows[header + 1 :], header + 2):
            row = original + [""] * max(0, len(rows[header]) - len(original))
            if not any(v.strip() for v in row):
                continue
            name = " ".join(row[3].split())
            if not name:
                raise ValueError(f"Nonempty row without student: {filename}:{row_number}")
            canonical = normalized(name)
            if canonical in names:
                raise ValueError(f"Duplicate student in {filename}:{row_number}")
            names.add(canonical)
            student_key = key + ":" + hashlib.sha256(canonical.encode()).hexdigest()[:32]
            notes = []
            if row[0].strip():
                notes.append(f"Mygov/manba holati: {row[0].strip()}")
            if row[1].strip():
                notes.append(f"Maktab: {row[1].strip()}")
            if row[4].strip():
                notes.append(f"Manbadagi kontakt: {row[4].strip()}")
            notes.extend(
                f"{year}-{day} davomat belgisi aniqlashtirilmagan: {row[col].strip()}"
                for col, day in columns.items()
                if row[col].strip() and row[col].strip().casefold() != "k"
            )
            plan.roster.students.append(
                RosterStudent(
                    student_key,
                    key,
                    name,
                    parse_phone(row[4]),
                    row[5].strip() or None,
                    {
                        "file": filename,
                        "sha256": sha,
                        "row": row_number,
                        "cells": original,
                        "contact_raw": row[4],
                        "notes": notes,
                    },
                )
            )
            for col, month_day in columns.items():
                value = row[col].strip()
                record = {
                    "group_key": key,
                    "student_key": student_key,
                    "date": f"{year}-{month_day}",
                    "source_row": row_number,
                    "source_column": col + 1,
                    "raw": row[col],
                }
                if value and value.casefold() != "k":
                    plan.unknown_cells.append(record)
                    continue
                plan.attendance.append({**record, "status": "present" if value else "absent"})
    return plan


async def apply_educenter(
    session: AsyncSession, plan: EducPlan, *, capacity: int = 30
) -> dict[str, int]:
    """Caller owns transaction. Conflicting finalized/manual history is never overwritten."""
    await session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": 0x4E454F076})
    for spec in plan.roster.groups:
        existing = await session.scalar(
            select(Group).where(Group.source_key == spec.key).with_for_update()
        )
        if existing and (
            existing.name != spec.name
            or existing.status.value != "active"
            or existing.days_of_week != spec.days
            or existing.start_time != time.fromisoformat(spec.start or "00:00")
            or existing.end_time != time.fromisoformat(spec.end or "00:00")
        ):
            raise ValueError("Existing imported schedule differs; review required")
    result = await apply_plan(session, plan.roster, capacity=capacity)
    groups = {
        g.source_key: g
        for g in (
            await session.scalars(
                select(Group).where(Group.source_key.in_(plan.lessons)).with_for_update()
            )
        ).all()
    }
    students = {
        s.source_key: s
        for s in (
            await session.scalars(
                select(Student).where(Student.source_key.in_([p.key for p in plan.roster.students]))
            )
        ).all()
    }
    for pupil in plan.roster.students:
        if students[pupil.key].group_id != groups[pupil.group_key].id:
            raise ValueError("Imported student was transferred; review required")
    batches: dict[tuple[str, str], AttendanceBatch] = {}
    new_batches = new_attendance = 0
    for group_key, dates in plan.lessons.items():
        group = groups[group_key]
        for day in dates:
            batch = await session.scalar(
                select(AttendanceBatch).where(
                    AttendanceBatch.group_id == group.id,
                    AttendanceBatch.date == date.fromisoformat(day),
                )
            )
            if batch is None:
                batch = AttendanceBatch(
                    group_id=group.id, date=date.fromisoformat(day), finalized_by=group.teacher_id
                )
                session.add(batch)
                await session.flush()
                new_batches += 1
            elif batch.finalized_by != group.teacher_id:
                raise ValueError("Attendance teacher conflict")
            batches[(group_key, day)] = batch
    for item in plan.attendance:
        group = groups[item["group_key"]]
        student = students[item["student_key"]]
        attendance_day = date.fromisoformat(item["date"])
        batch = batches[(item["group_key"], item["date"])]
        status = AttendanceStatus(item["status"])
        record = await session.scalar(
            select(Attendance).where(
                Attendance.group_id == group.id,
                Attendance.student_id == student.id,
                Attendance.date == attendance_day,
            )
        )
        if record is not None:
            if (
                record.status != status
                or record.batch_id != batch.id
                or record.marked_by != group.teacher_id
                or record.note is not None
            ):
                raise ValueError("Attendance history conflict; no records overwritten")
            continue
        session.add(
            Attendance(
                group_id=group.id,
                student_id=student.id,
                date=attendance_day,
                status=status,
                batch_id=batch.id,
                marked_by=group.teacher_id,
            )
        )
        new_attendance += 1
    await session.flush()
    return {**result, "created_batches": new_batches, "created_attendance": new_attendance}


def read_profiles(source: Path) -> list[StaffSpec]:
    profiles = [
        StaffSpec.model_validate(p)
        for p in json.loads((source / "staff-profiles.json").read_text())
    ]
    roles = {p.username: p.role for p in profiles}
    if (
        len(roles) != len(profiles)
        or roles.get("ceo_mohira") != Role.SUPERADMIN
        or any(roles.get(n) != Role.TEACHER for n, _, _, _ in SCHEDULES)
    ):
        raise ValueError("Reviewed superadmin and teacher profiles required")
    return profiles


async def run(args: argparse.Namespace) -> None:
    plan = build_plan(args.source, year=args.year)
    profiles = read_profiles(args.source)
    # Bind reviewed staff profiles to the hash; credentials are never part of it.
    digest = hashlib.sha256(
        (
            plan.digest()
            + json.dumps([p.model_dump(mode="json") for p in profiles], sort_keys=True)
        ).encode()
    ).hexdigest()
    output: dict[str, Any] = {"summary": plan.summary(), "plan_sha256": digest}
    if args.report:
        private_write(
            args.report, json.dumps({**output, "plan": asdict(plan)}, ensure_ascii=False, indent=2)
        )
    if args.apply:
        if args.expected_plan != digest:
            raise ValueError("Apply requires exact reviewed --expected-plan hash")
        accounts = prepare(profiles, args.credentials)
        settings = Settings()
        db = Database(settings)
        try:
            async with db.session() as session, session.begin():
                created, links = await provision_staff(
                    session, accounts, settings, require_bot=False
                )
                output["result"] = {
                    "created_staff": created,
                    **await apply_educenter(session, plan, capacity=args.capacity),
                }
            private_write(args.credentials.with_name("links.json"), json.dumps(links, indent=2))
        finally:
            await db.close()
    print(json.dumps(output, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--year", type=int, default=2026)
    parser.add_argument("--capacity", type=int, default=30)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--credentials", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--expected-plan")
    args = parser.parse_args()
    try:
        asyncio.run(run(args))
    except (ValueError, OSError, KeyError, SQLAlchemyError, DomainError):
        # Avoid leaking PII or passwords through parser/DB diagnostics.
        parser.exit(1, "Import failed: inspect private source/report and resolve conflicts.\n")


if __name__ == "__main__":
    main()
