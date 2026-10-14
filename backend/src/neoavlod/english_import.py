"""Reviewed English import: Asila's attendance stays empty; Jamshidbek's dated k become drafts."""

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
from neoavlod.models import Attendance, AttendanceBatch, AttendanceStatus, Group, Role, Student
from neoavlod.models.common import Status
from neoavlod.real_staff import StaffSpec, prepare, private_write, provision_staff
from neoavlod.roster_import import (
    ImportPlan,
    RosterGroup,
    RosterStudent,
    apply_plan,
    normalized,
    parse_phone,
)
from neoavlod.services.import_receipts import deployment_import
from neoavlod.settings import Settings

FILES = (
    "English_Elementry&Beginer_1_gruh.csv",
    "English_Pre_intermediate_2_gruh.csv",
    "English_Elementry&Beginer_3_gruh.csv",
)
SCHEDULES = (
    ("teacher_asila", [1, 3, 5], "09:00", "10:30"),
    ("teacher_jamshidbek", [2, 4, 6], "15:00", "16:30"),
    ("teacher_jamshidbek", [2, 4, 6], "16:30", "18:00"),
)
PROFILES = (
    StaffSpec(
        username="teacher_asila", first_name="Asila", last_name="Ibragimova", role=Role.TEACHER
    ),
    StaffSpec(
        username="teacher_jamshidbek",
        first_name="Jamshidbek",
        last_name="Juraboev",
        role=Role.TEACHER,
    ),
)
LEVELS = {"beginner", "elementraty", "elementary", "pre-inter"}
# Calendar shared by Beginner/Elementary in the same group. Blank source dates
# are not guessed. September 29 precedes the October dates in the second file.
LESSONS = (
    {7: "2026-10-12", 8: "2026-10-14", 9: "2026-10-16", 10: "2026-10-18"},
    {6: "2026-09-29", 7: "2026-10-03", 8: "2026-10-06", 9: "2026-10-08", 10: "2026-10-10"},
    {6: "2026-10-03", 7: "2026-10-06", 8: "2026-10-08", 9: "2026-10-10"},
)


@dataclass
class EnglishPlan(ImportPlan):
    attendance: list[dict[str, Any]] = field(default_factory=list)
    undated_present: list[dict[str, Any]] = field(default_factory=list)
    deferred_present: list[dict[str, Any]] = field(default_factory=list)

    def summary(self) -> dict[str, Any]:
        return {
            **super().summary(),
            "present_drafts": len(self.attendance),
            "undated_k_cells": len(self.undated_present),
            "asila_k_cells_deferred": len(self.deferred_present),
            "merged_duplicate_rows": sum(len(p.source["entries"]) - 1 for p in self.students),
            "absent_imported": 0,
        }


def build_plan(source: Path) -> EnglishPlan:
    plan = EnglishPlan(maths="not_applicable")
    for index, filename in enumerate(FILES):
        raw = (source / filename).read_bytes()
        sha = hashlib.sha256(raw).hexdigest()
        plan.files[filename] = sha
        rows = list(
            csv.reader(raw.decode("utf-8-sig").splitlines(), delimiter="," if index == 0 else ";")
        )
        header_indices = [i for i, r in enumerate(rows) if len(r) > 3 and normalized(r[3]) == "ism"]
        if not header_indices:
            raise ValueError("Expected English roster header")
        for header_index in header_indices:
            for col, value in enumerate(rows[header_index]):
                if (
                    col >= 6
                    and value.strip()
                    and (
                        col not in LESSONS[index]
                        or value.strip() != str(date.fromisoformat(LESSONS[index][col]).day)
                    )
                ):
                    raise ValueError("Unreviewed attendance header")
        key = f"educenter:2026:english:{index + 1}"
        teacher, days, start, end = SCHEDULES[index]
        plan.groups.append(
            RosterGroup(
                key,
                Path(filename).stem,
                "Ingliz tili",
                teacher,
                days,
                start,
                end,
                {
                    "file": filename,
                    "sha256": sha,
                    "headers": [rows[i] for i in header_indices],
                    "attendance_policy": "admin_review_empty"
                    if index == 0
                    else "dated_k_only_draft",
                },
            )
        )
        header: list[str] | None = None
        section: str | None = None
        learners: dict[str, RosterStudent] = {}
        for row_number, original in enumerate(rows, 1):
            row = original + [""] * max(0, 6 - len(original))
            name = " ".join(row[3].split())
            if normalized(name) in LEVELS and "kun" in normalized(row[4]):
                section = name
                header = None
                continue
            if normalized(name) == "ism":
                if section is None or normalized(row[4]) != "raqam" or normalized(row[5]) != "sinf":
                    raise ValueError("Unreviewed English roster structure")
                header = original
                continue
            if not any(v.strip() for v in row):
                continue
            # Reviewed preamble identifies the teacher/month, not an enrolment.
            if row_number <= header_indices[0]:
                continue
            if not name and all(not v.strip() for v in row[:6]):
                continue  # Month separator; kept by file SHA and subsequent row provenance.
            if not name or header is None or len(name.split()) < 2:
                raise ValueError("Non-student row requires review")
            canonical = normalized(name)
            phone = parse_phone(row[4])
            grade = row[5].strip() or None
            entry = {"row": row_number, "cells": original, "header": header, "section": section}
            notes = [f"CSV bo‘limi: {section}"]
            if row[0].strip():
                notes.append(f"Mygov/manba holati: {row[0].strip()}")
            if row[1].strip():
                notes.append(f"Maktab: {row[1].strip()}")
            if row[4].strip() and phone is None:
                notes.append(f"Manbadagi kontakt: {row[4].strip()}")
            notes.extend(
                f"Manba izohi ({col + 1}-ustun): {v.strip()}"
                for col, v in enumerate(row)
                if col >= 6 and v.strip() and v.strip().casefold() != "k"
            )
            student_key = key + ":" + hashlib.sha256(canonical.encode()).hexdigest()[:32]
            if index == 0:
                notes.append("Asila guruhi davomati import qilinmadi; admin tekshiradi.")
            for col, value in enumerate(row):
                if col < 6 or value.strip().casefold() != "k":
                    continue
                record = {
                    "group_key": key,
                    "student_key": student_key,
                    "source_row": row_number,
                    "source_column": col + 1,
                }
                if index == 0:
                    plan.deferred_present.append(record)
                if col not in LESSONS[index]:
                    plan.undated_present.append(record)
                    notes.append(
                        f"Sanasi yozilmagan k belgisi ({col + 1}-ustun); admin tekshiradi."
                    )
                    continue
                if index == 0:
                    continue
                lesson_date = date.fromisoformat(LESSONS[index][col])
                if lesson_date > date(2026, 10, 13) or lesson_date.isoweekday() not in days:
                    raise ValueError("Present date is future or contradicts reviewed schedule")
                record["date"] = lesson_date.isoformat()
                if not any(
                    r["student_key"] == student_key and r["date"] == record["date"]
                    for r in plan.attendance
                ):
                    plan.attendance.append(record)
            existing = learners.get(canonical)
            if existing is not None:
                # Same pupil listed in Beginner and Elementary: one enrolment, both source rows.
                if phone is None or existing.phone != phone or existing.school_grade != grade:
                    raise ValueError(
                        "Duplicate name with differing or unknown contact requires review"
                    )
                existing.source["entries"].append(entry)
                existing.source["notes"] = list(dict.fromkeys(existing.source["notes"] + notes))
                continue
            learners[canonical] = RosterStudent(
                student_key,
                key,
                name,
                phone,
                grade,
                {
                    "file": filename,
                    "sha256": sha,
                    "row": row_number,
                    "cells": original,
                    "entries": [entry],
                    "notes": notes,
                },
            )
        if not learners:
            raise ValueError("Empty English roster")
        plan.students.extend(learners.values())
    return plan


def reviewed_digest(plan: EnglishPlan) -> str:
    return hashlib.sha256(
        (
            plan.digest()
            + json.dumps([p.model_dump(mode="json") for p in PROFILES], sort_keys=True)
        ).encode()
    ).hexdigest()


async def apply_english(
    session: AsyncSession, plan: EnglishPlan, *, capacity: int = 30
) -> dict[str, int]:
    await session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": 0x4E454F090})
    for spec in plan.groups:
        existing = await session.scalar(
            select(Group).where(Group.source_key == spec.key).with_for_update()
        )
        if existing is not None and (
            existing.name != spec.name
            or existing.status != Status.ACTIVE
            or existing.days_of_week != spec.days
            or existing.start_time != time.fromisoformat(spec.start or "00:00")
            or existing.end_time != time.fromisoformat(spec.end or "00:00")
        ):
            raise ValueError("Existing imported schedule differs; review required")
    result = await apply_plan(session, plan, capacity=capacity)
    groups = {
        group.source_key: group
        for group in (
            await session.scalars(
                select(Group).where(Group.source_key.in_([g.key for g in plan.groups]))
            )
        ).all()
    }
    for pupil in plan.students:
        person = await session.scalar(select(Student).where(Student.source_key == pupil.key))
        if person is None or person.group_id != groups[pupil.group_key].id:
            raise ValueError("Imported student was transferred; review required")
    students = {
        p.source_key: p
        for p in (
            await session.scalars(
                select(Student).where(Student.source_key.in_([p.key for p in plan.students]))
            )
        ).all()
    }
    created_attendance = 0
    for item in plan.attendance:
        group = groups[item["group_key"]]
        student = students[item["student_key"]]
        target_date = date.fromisoformat(item["date"])
        existing_record = await session.scalar(
            select(Attendance).where(
                Attendance.group_id == group.id,
                Attendance.student_id == student.id,
                Attendance.date == target_date,
            )
        )
        if existing_record is not None:
            # Admin's later review wins; never replay CSV over saved corrections.
            continue
        if (
            await session.scalar(
                select(AttendanceBatch.id).where(
                    AttendanceBatch.group_id == group.id,
                    AttendanceBatch.date == target_date,
                )
            )
            is not None
        ):
            raise ValueError("Finalized history needs explicit review; import creates drafts only")
        session.add(
            Attendance(
                group_id=group.id,
                student_id=student.id,
                date=target_date,
                status=AttendanceStatus.PRESENT,
                marked_by=group.teacher_id,
                batch_id=None,
            )
        )
        created_attendance += 1
    await session.flush()
    return {**result, "created_attendance": created_attendance}


async def run(args: argparse.Namespace) -> None:
    plan = build_plan(args.source)
    digest = reviewed_digest(plan)
    output: dict[str, Any] = {"summary": plan.summary(), "plan_sha256": digest}
    if args.report:
        private_write(
            args.report, json.dumps({**output, "plan": asdict(plan)}, ensure_ascii=False, indent=2)
        )
    if args.apply:
        if args.expected_plan != digest:
            raise ValueError("Apply requires exact reviewed --expected-plan hash")
        settings = Settings()
        database = Database(settings)
        links: dict[str, str | None] | None = None
        try:
            async with database.session() as session, session.begin():

                async def apply_once() -> dict[str, int]:
                    nonlocal links
                    accounts = prepare(list(PROFILES), args.credentials)
                    created, links = await provision_staff(
                        session,
                        accounts,
                        settings,
                        require_bot=False,
                        preserve_missing_fields=True,
                        preserve_given_names=True,
                    )
                    return {
                        "created_staff": created,
                        **await apply_english(session, plan, capacity=args.capacity),
                    }

                if getattr(args, "deployment_receipt", False):
                    output["result"] = await deployment_import(
                        session,
                        key="educenter:2026:english",
                        digest=digest,
                        roster=plan,
                        attendance=plan.attendance,
                        apply=apply_once,
                    )
                else:
                    output["result"] = await apply_once()
            if links is not None:
                private_write(args.credentials.with_name("links.json"), json.dumps(links, indent=2))
        finally:
            await database.close()
    print(json.dumps(output, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--capacity", type=int, default=30)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--credentials", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--expected-plan")
    parser.add_argument("--deployment-receipt", action="store_true")
    args = parser.parse_args()
    try:
        asyncio.run(run(args))
    except (ValueError, OSError, KeyError, SQLAlchemyError, DomainError):
        parser.exit(1, "Import failed: inspect private source/report and resolve conflicts.\n")


if __name__ == "__main__":
    main()
