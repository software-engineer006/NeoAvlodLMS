"""Backed-up local data cutover: proven demo cleanup and real import in one transaction."""

import argparse
import asyncio
import json
from pathlib import Path

from sqlalchemy import delete, func, select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession

from neoavlod.database import Database
from neoavlod.models import (
    Attendance,
    AttendanceBatch,
    Group,
    NotificationOutbox,
    Parent,
    Role,
    Staff,
    Student,
    Subject,
)
from neoavlod.real_staff import PreparedAccount, private_write, provision_staff
from neoavlod.roster_import import apply_plan, build_plan
from neoavlod.security.passwords import verify_password
from neoavlod.settings import Settings


async def cleanup_demo(session: AsyncSession, *, apply: bool = False) -> dict[str, int]:
    """Match exact seed identities; unrelated FK references abort rather than cascade."""
    people: list[Staff] = []
    for index, username, role, surname in (
        (1, "superadmin", Role.SUPERADMIN, "Superadmin"),
        (2, "teacher", Role.TEACHER, "O‘qituvchi"),
    ):
        person = await session.scalar(
            select(Staff).where(Staff.username == username).with_for_update()
        )
        if person is None:
            continue
        if (
            person.first_name != "Sinov"
            or person.last_name != surname
            or person.role != role
            or person.phone != f"+99899000000{index}"
            or not verify_password(person.hashed_password, "1234")
        ):
            raise ValueError("Legacy username is not a proven demo account")
        people.append(person)
    subject = await session.scalar(select(Subject).where(Subject.name == "Demo matematika"))
    group = await session.scalar(select(Group).where(Group.name == "Demo guruh").with_for_update())
    students: list[Student] = []
    parents: list[Parent] = []
    if group:
        teacher = next((p for p in people if p.username == "teacher"), None)
        if not subject or subject.description != "Local frontend sinovi" or not teacher:
            raise ValueError("Demo group provenance differs")
        if group.teacher_id != teacher.id or group.subject_id != subject.id or group.source_key:
            raise ValueError("Demo group identity differs")
        students = list(await session.scalars(select(Student).where(Student.group_id == group.id)))
        expected = {name: i for i, name in enumerate(("Ali", "Malika", "Aziz"), 1)}
        if len(students) != 3:
            raise ValueError("Demo group has unexpected students; manual reconciliation required")
        for pupil in students:
            pupil_index = expected.get(pupil.first_name)
            if (
                not pupil_index
                or pupil.last_name != "Sinov"
                or pupil.age != 14
                or pupil.source_key
                or pupil.phone != f"+99899000002{pupil_index}"
                or not pupil.parent_id
            ):
                raise ValueError("Demo student provenance differs")
            parent = await session.get(Parent, pupil.parent_id)
            if (
                not parent
                or parent.first_name != "Sinov"
                or parent.last_name != "Ota-ona"
                or parent.phone != f"+99899000001{pupil_index}"
            ):
                raise ValueError("Demo parent provenance differs")
            if (
                await session.scalar(
                    select(func.count()).select_from(Student).where(Student.parent_id == parent.id)
                )
                != 1
            ):
                raise ValueError("Demo parent has unrelated student")
            parents.append(parent)
    if subject and (
        subject.description != "Local frontend sinovi"
        or await session.scalar(
            select(func.count()).select_from(Group).where(Group.subject_id == subject.id)
        )
        != int(group is not None)
    ):
        raise ValueError("Demo subject has unrelated references")
    group_ids = [group.id] if group else []
    people_ids = [p.id for p in people]
    # Protect real groups/history that happen to reference a test teacher/admin.
    if (
        await session.scalar(
            select(func.count())
            .select_from(Group)
            .where(Group.teacher_id.in_(people_ids), Group.id.not_in(group_ids))
        )
        or await session.scalar(
            select(func.count())
            .select_from(Attendance)
            .where(Attendance.marked_by.in_(people_ids), Attendance.group_id.not_in(group_ids))
        )
        or await session.scalar(
            select(func.count())
            .select_from(AttendanceBatch)
            .where(
                AttendanceBatch.finalized_by.in_(people_ids),
                AttendanceBatch.group_id.not_in(group_ids),
            )
        )
    ):
        raise ValueError("Demo staff has unrelated references; cleanup refused")
    attendance_ids = select(Attendance.id).where(Attendance.group_id.in_(group_ids))
    counts = {
        "staff": len(people),
        "groups": len(group_ids),
        "students": len(students),
        "parents": len(parents),
        "subjects": int(subject is not None),
        "attendance": await session.scalar(
            select(func.count()).select_from(Attendance).where(Attendance.group_id.in_(group_ids))
        )
        or 0,
        "outbox": await session.scalar(
            select(func.count())
            .select_from(NotificationOutbox)
            .where(NotificationOutbox.attendance_id.in_(attendance_ids))
        )
        or 0,
    }
    if apply:
        await session.execute(
            delete(NotificationOutbox).where(NotificationOutbox.attendance_id.in_(attendance_ids))
        )
        await session.execute(delete(Attendance).where(Attendance.group_id.in_(group_ids)))
        await session.execute(
            delete(AttendanceBatch).where(AttendanceBatch.group_id.in_(group_ids))
        )
        await session.execute(delete(Student).where(Student.id.in_([p.id for p in students])))
        await session.execute(delete(Parent).where(Parent.id.in_([p.id for p in parents])))
        await session.execute(delete(Group).where(Group.id.in_(group_ids)))
        if subject:
            await session.execute(delete(Subject).where(Subject.id == subject.id))
        await session.execute(delete(Staff).where(Staff.id.in_(people_ids)))
    return counts


async def run(args: argparse.Namespace) -> None:
    settings = Settings()
    if (
        settings.environment != "development"
        or make_url(settings.database_url.get_secret_value()).database != "neoavlod_demo"
    ):
        raise ValueError("Explicit local portal DB required")
    plan = build_plan(args.root / "source")
    if args.expected_plan != plan.digest():
        raise ValueError("Reviewed source plan hash required")
    if args.apply and not (args.root / "backup/pre-real-data.dump.verified").is_file():
        raise ValueError("Verified backup/restore required before apply")
    accounts = [
        PreparedAccount.model_validate(row)
        for row in json.loads((args.root / "prepared-accounts.json").read_text())
    ]
    db = Database(settings)
    try:
        async with db.session() as session, session.begin():
            removed = await cleanup_demo(session, apply=args.apply)
            result: dict[str, object] = {"demo": removed, "plan": plan.summary()}
            if args.apply:
                created, links = await provision_staff(session, accounts, settings)
                result["staff_created"] = created
                result["import"] = await apply_plan(session, plan)
            else:
                links = {}
        if args.apply:
            lines = [
                "# NeoAvlod — haqiqiy hisoblar",
                "",
                "Telegram havolasini faqat hisob egasi ochsin.",
                "Startdan keyin username/parol bilan portalga kiring "
                "va Telegramdagi 6 xonali kodni kiriting.",
                "Birinchi kirishda vaqtinchalik parolni yangilang. "
                "Havola 7 kun, bot orqali parol yetkazish 3 kun amal qiladi.",
                "",
            ]
            for account in accounts:
                spec = account.profile
                portal = (
                    settings.teacher_origin if spec.role == Role.TEACHER else settings.admin_origin
                )
                lines.extend(
                    [
                        f"## {spec.first_name} {spec.last_name or ''}".strip(),
                        f"Username: `{spec.username}`",
                        f"Parol: `{account.password.get_secret_value()}`",
                        f"Portal: {portal}",
                        f"Telegram: {links.get(spec.username) or 'Ulangan/havola eskirgan'}",
                        "",
                    ]
                )
            private_write(args.root / "HISOBLAR.md", "\n\n".join(lines))
            private_write(args.root / "links.json", json.dumps(links, indent=2))
            audit = args.root / "apply-audit.json"
            if audit.exists():
                audit = args.root / "last-run-audit.json"
            private_write(audit, json.dumps(result, ensure_ascii=False, indent=2))
        print(json.dumps(result, ensure_ascii=False))
    finally:
        await db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--expected-plan", required=True)
    parser.add_argument("--apply", action="store_true")
    asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    main()
