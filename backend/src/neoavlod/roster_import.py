"""Preview and atomically import source rosters without inventing missing information."""

import argparse
import asyncio
import csv
import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import time
from pathlib import Path
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from neoavlod.database import Database
from neoavlod.models import Group, Role, Staff, Student, Subject
from neoavlod.models.common import Status
from neoavlod.settings import Settings

FILES = ("it_even.csv", "it_odd.csv", "english_1.csv", "english_2.csv")
COHORT = "2026-2027"
IMPORT_LOCK = 0x4E454F063
LEVELS = {
    "beginner": "Beginner",
    "elementraty": "Elementary",
    "elementary": "Elementary",
    "pre-inter": "Pre-intermediate",
    "intermediate": "Intermediate",
}


def normalized(value: str) -> str:
    return " ".join(value.replace("’", "'").replace("‘", "'").split()).casefold()


def parse_phone(raw: str) -> str | None:
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 9:
        return "+998" + digits
    if len(digits) == 12 and digits.startswith("998"):
        return "+" + digits
    return None


def parse_times(raw: str) -> tuple[time | None, time | None]:
    match = re.fullmatch(r"\s*(\d{1,2}):(\d{2})(?:\s*-\s*(?:(\d{1,2}):(\d{2}))?)?\s*", raw)
    if not match:
        return None, None
    start = time(int(match[1]), int(match[2]))
    end = time(int(match[3]), int(match[4])) if match[3] else None
    if end is not None and start >= end:
        raise ValueError("Invalid source time order")
    return start, end


@dataclass
class RosterGroup:
    key: str
    name: str
    subject: str
    teacher_username: str
    days: list[int]
    start: str | None
    end: str | None
    source: dict[str, Any]


@dataclass
class RosterStudent:
    key: str
    group_key: str
    full_name: str
    phone: str | None
    school_grade: str | None
    source: dict[str, Any]


@dataclass
class ImportPlan:
    maths: str
    groups: list[RosterGroup] = field(default_factory=list)
    students: list[RosterStudent] = field(default_factory=list)
    quarantine: list[dict[str, Any]] = field(default_factory=list)
    files: dict[str, str] = field(default_factory=dict)

    def summary(self) -> dict[str, Any]:
        return {
            "groups": len(self.groups),
            "students": len(self.students),
            "quarantine": len(self.quarantine),
            "maths": self.maths,
            "by_file": {
                name: sum(s.source["file"] == name for s in self.students) for name in self.files
            },
            "quarantine_reasons": {
                reason: sum(r["reason"] == reason for r in self.quarantine)
                for reason in sorted({r["reason"] for r in self.quarantine})
            },
        }

    def digest(self) -> str:
        return hashlib.sha256(
            json.dumps(asdict(self), sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()


def build_plan(source: Path, *, maths: str = "exclude") -> ImportPlan:
    if maths not in {"exclude", "python", "separate"}:
        raise ValueError("Unknown maths mapping")
    plan = ImportPlan(maths=maths)
    for name in FILES:
        raw = (source / name).read_bytes()
        file_hash = hashlib.sha256(raw).hexdigest()
        plan.files[name] = file_hash
        rows = list(csv.reader(raw.decode("utf-8-sig").splitlines()))
        header: list[str] | None = None
        section_key: str | None = None
        section_counts: dict[str, int] = {}
        names: dict[str, list[RosterStudent]] = {}
        for number, original in enumerate(rows, 1):
            row = original + [""] * max(0, 6 - len(original))
            full_name = " ".join(row[3].split())
            if full_name and re.search(r"toq|juft", row[4], re.IGNORECASE):
                header = row
                label = normalized(full_name)
                section_counts[label] = section_counts.get(label, 0) + 1
                section_key = f"{COHORT}:{name}:{label}:{section_counts[label]}"
                is_math = label == "matematika"
                if is_math and maths == "exclude":
                    continue
                subject = (
                    "Ingliz tili"
                    if name.startswith("english")
                    else ("Matematika" if is_math and maths == "separate" else "Python&vibecoding")
                )
                odd = name in {"it_odd.csv", "english_1.csv"}
                teacher = (
                    "teacher_ingliz"
                    if name.startswith("english")
                    else ("teacher_jasurbek" if odd else "teacher_dilmurod")
                )
                start, end = parse_times(row[5])
                level = LEVELS.get(label, "")
                suffix = (
                    f"{level} · {'1' if odd else '2'}-smena"
                    if name.startswith("english")
                    else f"{'Toq' if odd else 'Juft'} kunlar"
                )
                if is_math and maths == "python":
                    suffix += f" · {row[5].strip() or str(section_counts[label])}"
                if is_math and maths == "separate":
                    suffix += f" · {row[5].strip() or str(section_counts[label])}"
                plan.groups.append(
                    RosterGroup(
                        key=section_key,
                        name=f"{subject} — {suffix}",
                        subject=subject,
                        teacher_username=teacher,
                        days=[1, 3, 5] if odd else [2, 4, 6],
                        start=start.isoformat() if start else None,
                        end=end.isoformat() if end else None,
                        source={
                            "file": name,
                            "sha256": file_hash,
                            "row": number,
                            "cells": original,
                        },
                    )
                )
                continue
            if not full_name or normalized(full_name) == "ism":
                continue
            if (
                header is None
                or section_key is None
                or len(full_name.split()) < 2
                or normalized(full_name).startswith("boshqa guruhga")
                or not re.search(r"[a-zA-ZА-Яа-я]", full_name)
            ):
                plan.quarantine.append(
                    {"file": name, "row": number, "cells": original, "reason": "non_student_label"}
                )
                continue
            provenance = {
                "file": name,
                "sha256": file_hash,
                "row": number,
                "cells": original,
                "header": header,
                "contact_raw": row[4],
                "notes": [
                    c.strip()
                    for c in row[6:]
                    if c.strip()
                    and not c.strip().isdigit()
                    and c.strip().casefold() not in {"k", "y", "p", "+", "-", "x", "s"}
                ],
            }
            if normalized(header[3]) == "matematika" and maths == "exclude":
                plan.quarantine.append({**provenance, "reason": "maths_mapping_pending"})
                continue
            name_key = normalized(full_name)
            digest = hashlib.sha256(f"{section_key}:{name_key}".encode()).hexdigest()[:32]
            learner = RosterStudent(
                key=f"{COHORT}:student:{digest}",
                group_key=section_key,
                full_name=full_name,
                phone=parse_phone(row[4]),
                school_grade=row[5].strip() or None,
                source=provenance,
            )
            names.setdefault(name_key, []).append(learner)
        for matches in names.values():
            if len(matches) > 1:
                for learner in matches:
                    plan.quarantine.append(
                        {
                            **learner.source,
                            "reason": "duplicate_enrollment",
                            "full_name": learner.full_name,
                        }
                    )
            else:
                plan.students.extend(matches)
    return plan


async def apply_plan(
    session: AsyncSession, plan: ImportPlan, *, capacity: int = 30
) -> dict[str, int]:
    """Caller owns the transaction; this function never commits partial results."""
    if not 1 <= capacity <= 1000:
        raise ValueError("Capacity must be 1–1000")
    await session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": IMPORT_LOCK})
    subjects: dict[str, Subject] = {}
    groups: dict[str, Group] = {}
    teachers: dict[str, Staff] = {}
    created_groups = created_students = 0
    # Validate every required teacher before any inserts.
    for username in sorted({g.teacher_username for g in plan.groups}):
        teacher = await session.scalar(select(Staff).where(Staff.username == username))
        if teacher is None or teacher.role != Role.TEACHER or teacher.status != Status.ACTIVE:
            raise ValueError(f"Required active teacher missing: {username}")
        teachers[username] = teacher
    for item in plan.groups:
        subject = subjects.get(item.subject)
        if subject is None:
            subject = await session.scalar(select(Subject).where(Subject.name == item.subject))
            if subject is None:
                subject = Subject(name=item.subject)
                session.add(subject)
                await session.flush()
            if not subject.is_active:
                raise ValueError("Import subject is inactive")
            subjects[item.subject] = subject
        group = await session.scalar(
            select(Group).where(Group.source_key == item.key).with_for_update()
        )
        if group is None:
            # Refuse to silently duplicate an existing manually created group.
            if await session.scalar(select(Group.id).where(Group.name == item.name)) is not None:
                raise ValueError("Existing group needs explicit source reconciliation")
            group = Group(
                name=item.name,
                subject_id=subject.id,
                teacher_id=teachers[item.teacher_username].id,
                monthly_price=None,
                max_students=capacity,
                days_of_week=item.days,
                start_time=time.fromisoformat(item.start) if item.start else None,
                end_time=time.fromisoformat(item.end) if item.end else None,
                room_number=None,
                source_key=item.key,
                source_data=item.source,
            )
            session.add(group)
            await session.flush()
            created_groups += 1
        elif (
            group.teacher_id != teachers[item.teacher_username].id
            or group.subject_id != subject.id
            or group.source_data != item.source
        ):
            raise ValueError("Existing import group differs; review before updating")
        groups[item.key] = group
    for pupil in plan.students:
        existing = await session.scalar(select(Student).where(Student.source_key == pupil.key))
        if existing is not None:
            if existing.source_data != pupil.source:
                raise ValueError("Existing imported source differs; review before updating")
            continue
        group = groups[pupil.group_key]
        count = (
            await session.scalar(
                select(func.count())
                .select_from(Student)
                .where(Student.group_id == group.id, Student.status == Status.ACTIVE)
            )
            or 0
        )
        if count >= group.max_students:
            raise ValueError("Import would exceed group capacity")
        # The CSV does not identify first/last name order or guardian ownership.
        # Preserve the full display name without guessing either relationship.
        session.add(
            Student(
                first_name=pupil.full_name,
                last_name=None,
                phone=pupil.phone,
                age=None,
                parent_id=None,
                group_id=group.id,
                school_grade=pupil.school_grade,
                source_key=pupil.key,
                source_data=pupil.source,
            )
        )
        await session.flush()
        created_students += 1
    return {
        "created_groups": created_groups,
        "created_students": created_students,
        "quarantine": len(plan.quarantine),
    }


async def run(args: argparse.Namespace) -> None:
    plan = build_plan(args.source, maths=args.maths)
    output = {"summary": plan.summary(), "plan_sha256": plan.digest()}
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps({**output, "plan": asdict(plan)}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        args.report.chmod(0o600)
    if args.apply:
        if args.expected_plan != plan.digest():
            raise ValueError("Apply requires the exact reviewed --expected-plan hash")
        database = Database(Settings())
        try:
            async with database.session() as session, session.begin():
                output["result"] = await apply_plan(session, plan, capacity=args.capacity)
        finally:
            await database.close()
    print(json.dumps(output, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--maths", choices=("exclude", "python", "separate"), default="exclude")
    parser.add_argument("--capacity", type=int, default=30)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--expected-plan")
    args = parser.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
