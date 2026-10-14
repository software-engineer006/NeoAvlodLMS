"""Reviewed one-time dataset replacement; legacy FKs/audit and employee auth survive."""

import argparse
import asyncio
import hashlib
import json
from dataclasses import asdict
from datetime import UTC, date, datetime, time
from pathlib import Path
from typing import Any

from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from neoavlod.audit_context import bind_source, emit
from neoavlod.database import Database
from neoavlod.models import (
    Attendance,
    AttendanceBatch,
    AttendanceStatus,
    Group,
    ImportReceipt,
    MessageCampaign,
    MessageDelivery,
    NotificationOutbox,
    OutboxStatus,
    Parent,
    Role,
    Room,
    Staff,
    Student,
    StudentGroupEnrollment,
    Subject,
)
from neoavlod.models.common import Status
from neoavlod.refresh_sources import FILES, RefreshManifest, build_refresh_manifest
from neoavlod.settings import Settings

RECEIPT = "educenter-refresh-v2-2026"
TEACHERS = (
    "teacher_asila",
    "teacher_jamshidbek",
    "teacher_jamshidbek",
    "teacher_jasurbek",
    "teacher_jasurbek",
    "teacher_dilmurod",
    "teacher_dilmurod",
)
DatasetModel = (
    Subject
    | Group
    | Parent
    | Student
    | StudentGroupEnrollment
    | Attendance
    | AttendanceBatch
    | MessageCampaign
    | MessageDelivery
)
MODELS: tuple[type[DatasetModel], ...] = (
    Subject,
    Group,
    Parent,
    Student,
    StudentGroupEnrollment,
    Attendance,
    AttendanceBatch,
    MessageCampaign,
    MessageDelivery,
)
LOCK_TABLES = ",".join(f"public.{model.__tablename__}" for model in MODELS)


async def refresh_dataset(
    session: AsyncSession,
    manifest: RefreshManifest,
    *,
    expected_digest: str,
    apply: bool = False,
    teacher_usernames: tuple[str, ...] = TEACHERS,
) -> dict[str, Any]:
    """Caller owns transaction. Retry never overwrites subsequent administrator edits."""
    digest = manifest.digest()
    if digest != expected_digest or len(teacher_usernames) != len(manifest.groups):
        raise ValueError("Reviewed dataset digest or teacher mapping differs")
    if not manifest.people or not manifest.enrollments or len(manifest.groups) != len(FILES):
        raise ValueError("Dataset is incomplete")
    await session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": 0x4E454F132})
    receipt = await session.get(ImportReceipt, RECEIPT)
    if receipt is not None:
        if receipt.plan_digest != digest:
            raise ValueError("Refresh receipt differs; explicit new dataset review required")
        return {"status": "already_applied", "created": 0, "digest": digest}
    teachers = {
        row.username: row
        for row in (
            await session.scalars(select(Staff).where(Staff.username.in_(teacher_usernames)))
        ).all()
    }
    if any(
        name not in teachers
        or teachers[name].role != Role.TEACHER
        or teachers[name].status != Status.ACTIVE
        for name in teacher_usernames
    ):
        raise ValueError("Approved active teacher account is missing; staff was not changed")
    current = {
        model.__tablename__: int(await session.scalar(select(func.count()).select_from(model)) or 0)
        for model in MODELS
    }
    result = {
        "status": "applied" if apply else "dry_run",
        "digest": digest,
        "archive": current,
        "new": manifest.summary(),
    }
    if not apply:
        return result
    await bind_source(session, "dataset_refresh")
    # Operator stops API/worker first; the table locks also serialize any in-flight writes.
    await session.execute(
        text(
            f"LOCK TABLE {LOCK_TABLES},public.notification_outbox,public.rooms "
            "IN ACCESS EXCLUSIVE MODE"
        )
    )
    session.info["include_archived"] = True
    now = datetime.now(UTC)
    await session.execute(
        update(NotificationOutbox)
        .where(
            NotificationOutbox.status.in_(
                [OutboxStatus.PENDING, OutboxStatus.PROCESSING, OutboxStatus.FAILED]
            )
        )
        .values(
            status=OutboxStatus.SKIPPED,
            last_error="Dataset yangilandi; eski xabar yuborilmaydi",
            locked_by=None,
            locked_until=None,
        )
    )
    await session.execute(
        update(MessageDelivery)
        .where(
            MessageDelivery.archived_at.is_(None), MessageDelivery.status.in_(["pending", "failed"])
        )
        .values(status="cancelled", last_error="Dataset yangilandi; eski xabar yuborilmaydi")
    )
    for model in reversed(MODELS):
        values: dict[str, Any] = {"archived_at": now}
        if hasattr(model, "updated_at"):
            values["updated_at"] = model.updated_at
        await session.execute(
            update(model).where(model.archived_at.is_(None)).values(**values)
        )
    subjects: dict[str, Subject] = {}
    groups: dict[str, Group] = {}
    room = await session.scalar(select(Room).where(func.lower(Room.name) == "217"))
    if room is None:
        room = Room(name="217", is_active=True)
        session.add(room)
        await session.flush()
    else:
        room.is_active = True
    for spec, username in zip(manifest.groups, teacher_usernames, strict=True):
        if spec.subject_name not in subjects:
            subject = Subject(name=spec.subject_name, is_active=True)
            session.add(subject)
            await session.flush()
            subjects[spec.subject_name] = subject
        count = sum(item.group_name == spec.name for item in manifest.enrollments)
        item = Group(
            name=spec.name,
            subject_id=subjects[spec.subject_name].id,
            teacher_id=teachers[username].id,
            monthly_price=None,
            max_students=max(30, count),
            days_of_week=spec.days,
            start_time=time.fromisoformat(spec.start_time),
            end_time=time.fromisoformat(spec.end_time),
            status=Status.ACTIVE,
            room_id=room.id if spec.room_number == "217" else None,
            room_number=spec.room_number,
            source_key=f"refresh:{digest[:16]}:g:{hashlib.sha256(spec.name.encode()).hexdigest()[:24]}",
            source_data={
                "digest": digest,
                "spec": asdict(spec),
                "header": manifest.headers[spec.file],
                "sha256": manifest.files[spec.file],
            },
        )
        session.add(item)
        await session.flush()
        groups[spec.name] = item
    people: dict[str, Student] = {}
    for person in manifest.people:
        courses = [item for item in manifest.enrollments if item.person_key == person.key]
        first, last = person.full_name.split(maxsplit=1)
        learner = Student(
            first_name=first,
            last_name=last,
            phone=person.phone,
            age=None,
            school_grade=person.school_grade,
            school_name=person.school_name,
            parent_id=None,
            group_id=groups[courses[0].group_name].id,
            status=Status.ACTIVE,
            source_key=f"refresh:{digest[:16]}:p:{person.key}",
            source_data={
                "digest": digest,
                "person": asdict(person),
                "notes": ["Manbada aniqlashtirish kerak: " + ", ".join(person.review_fields)]
                if person.review_fields
                else [],
            },
        )
        session.add(learner)
        await session.flush()
        people[person.key] = learner
    for course in manifest.enrollments:
        learner, group = people[course.person_key], groups[course.group_name]
        membership = await session.scalar(
            select(StudentGroupEnrollment).where(
                StudentGroupEnrollment.student_id == learner.id,
                StudentGroupEnrollment.group_id == group.id,
            )
        )
        if membership is None:
            membership = StudentGroupEnrollment(student_id=learner.id, group_id=group.id)
            session.add(membership)
        membership.level, membership.mygov_status, membership.notes = (
            course.level,
            course.mygov_status,
            course.notes,
        )
        membership.source_data = {"digest": digest, "enrollment": asdict(course)}
        for day in course.present_dates:
            session.add(
                Attendance(
                    student_id=learner.id,
                    group_id=group.id,
                    date=date.fromisoformat(day),
                    status=AttendanceStatus.PRESENT,
                    note=None,
                    marked_by=None,
                    source_imported=True,
                    batch_id=None,
                )
            )
    session.add(ImportReceipt(key=RECEIPT, plan_digest=digest, method="applied"))
    await session.flush()
    await emit(
        session,
        "dataset.refreshed",
        entity_type="dataset",
        details={
            "digest": digest,
            "archived": current,
            "imported": manifest.summary(),
            "notifications": 0,
            "attendance_state": "source_drafts",
        },
    )
    return result


async def run(args: argparse.Namespace) -> dict[str, Any]:
    manifest = build_refresh_manifest(
        args.source, year=2026, time_overrides={Path(FILES[-1]).stem: ("16:00", "18:00")}
    )
    database = Database(Settings())
    try:
        async with database.session() as session, session.begin():
            return await refresh_dataset(
                session, manifest, expected_digest=args.expected_digest, apply=args.apply
            )
    finally:
        await database.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--expected-digest", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        print(json.dumps(asyncio.run(run(args)), ensure_ascii=False, sort_keys=True))
    except Exception:
        # Input/runtime exceptions can contain source PII; detailed investigation stays private.
        raise SystemExit(
            "Dataset refresh failed; transaction rolled back. Check input and DB readiness."
        ) from None


if __name__ == "__main__":
    main()
