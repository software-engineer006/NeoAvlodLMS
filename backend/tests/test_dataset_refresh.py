"""Synthetic seven-source atomic replacement, current isolation and retained evidence."""

import asyncio
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import func, select, text, update
from sqlalchemy.orm import aliased
from test_rbac import actor, client_for
from test_refresh_sources import source_files
from test_teacher_api import setup_two_teachers_with_classes

from neoavlod.database import Database
from neoavlod.dataset_refresh import RECEIPT, refresh_dataset
from neoavlod.models import (
    Attendance,
    AttendanceBatch,
    AttendanceChange,
    AttendanceStatus,
    AuditEvent,
    Group,
    ImportReceipt,
    NotificationOutbox,
    OutboxStatus,
    Parent,
    Room,
    Staff,
    Student,
    StudentGroupEnrollment,
)
from neoavlod.refresh_sources import build_refresh_manifest

pytestmark = pytest.mark.anyio


async def test_refresh_atomic_reconciles_metadata_and_archives_without_fake_authors(
    model_database: Database,
    tmp_path: Path,
) -> None:
    teacher, old_group, _, _, pupil_id, _ = await setup_two_teachers_with_classes(model_database)
    plan = build_refresh_manifest(source_files(tmp_path / "csv"), year=2026)
    editor = await actor(
        model_database, permissions=["students:edit", "groups:read", "attendance:read"]
    )
    async with model_database.session() as session:
        staff_before = (
            await session.execute(
                text("SELECT id,username,hashed_password,auth_uuid FROM staff ORDER BY id")
            )
        ).all()
        pupil = await session.get(Student, pupil_id)
        assert pupil is not None
        parent_id = pupil.parent_id
        old = Attendance(
            group_id=old_group.id,
            student_id=pupil_id,
            date=date(2026, 10, 5),
            status=AttendanceStatus.PRESENT,
            marked_by=teacher.staff_id,
        )
        session.add(old)
        await session.flush()
        change = AttendanceChange(
            attendance_id=old.id,
            actor_id=teacher.staff_id,
            actor_name="Namuna Ustoz",
            actor_role="teacher",
            action="draft",
            new_status="present",
        )
        session.add(change)
        await session.commit()
        old_id, change_id = old.id, change.id
        account = await session.get(Staff, teacher.staff_id)
        assert account
        names = (account.username,) * 7
        dry = await refresh_dataset(
            session, plan, expected_digest=plan.digest(), teacher_usernames=names
        )
        assert dry["status"] == "dry_run"
        assert await session.get(ImportReceipt, RECEIPT) is None
        await session.rollback()
    async with model_database.session() as session, session.begin():
        result = await refresh_dataset(
            session, plan, expected_digest=plan.digest(), apply=True, teacher_usernames=names
        )
        assert result["new"]["profiles"] == 1 and result["new"]["memberships"] == 7
    async with model_database.session() as session:
        assert (
            await session.execute(
                text("SELECT id,username,hashed_password,auth_uuid FROM staff ORDER BY id")
            )
        ).all() == staff_before
        assert await session.get(Student, pupil_id) is None
        assert await session.get(Group, old_group.id) is None
        assert await session.get(Parent, parent_id) is None
        assert await session.get(Attendance, old_id) is None
        assert await session.get(AttendanceChange, change_id) is not None
        for model, count in (
            (Student, 1),
            (Group, 7),
            (Parent, 0),
            (StudentGroupEnrollment, 7),
            (Attendance, 7),
            (AttendanceBatch, 0),
            (NotificationOutbox, 0),
        ):
            assert await session.scalar(select(func.count()).select_from(model)) == count
        pupil = await session.scalar(select(Student))
        assert (
            pupil
            and pupil.parent_id is None
            and pupil.school_name == "26"
            and pupil.school_grade == "7-sinf"
        )
        entries = (await session.scalars(select(StudentGroupEnrollment))).all()
        assert all(
            e.mygov_status == "o'tdi" and e.notes == "Birinchi satr\nikkinchi satr" for e in entries
        )
        assert all(
            record.source_imported and record.marked_by is None and record.batch_id is None
            for record in (await session.scalars(select(Attendance))).all()
        )
        room = await session.scalar(select(Room).where(Room.name == "217"))
        assert room
        assert (
            await session.scalar(
                select(func.count()).select_from(Group).where(Group.room_id == room.id)
            )
            == 4
        )
        alias = aliased(Student)
        assert (await session.scalars(select(alias.id))).all() == [pupil.id]
        await session.execute(
            update(Student).where(Student.id == pupil_id).values(first_name="Must not update")
        )
        await session.commit()
        session.info["include_archived"] = True
        old_pupil = await session.get(Student, pupil_id)
        assert old_pupil and old_pupil.archived_at and old_pupil.first_name != "Must not update"
        assert await session.get(Attendance, old_id) is not None
        assert (
            await session.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(AuditEvent.action == "dataset.refreshed")
            )
            == 1
        )
    async with client_for(editor) as client:
        assert (await client.get(f"/api/v1/admin/students/{pupil_id}")).status_code == 404
        assert (
            await client.patch(
                f"/api/v1/admin/students/{pupil_id}", json={"first_name": "Must not update"}
            )
        ).status_code == 404
        assert (await client.get(f"/api/v1/admin/groups/{old_group.id}")).status_code == 404
        assert (await client.get("/api/v1/admin/students")).json()["total"] == 1
        current_group = (await client.get("/api/v1/admin/groups")).json()["items"][0]
        history = (
            await client.get(
                f"/api/v1/admin/groups/{current_group['id']}/attendance/history",
                params={"month": "2026-10"},
            )
        ).json()
        assert history["dates"] == ["2026-10-14"]
        assert history["summary"]["present_count"] == 1
    async with client_for(teacher) as client:
        assert (await client.get(f"/api/v1/teacher/groups/{old_group.id}")).status_code == 404
        assert (await client.get(f"/api/v1/teacher/students/{pupil_id}")).status_code == 404


async def test_failed_refresh_rolls_back_archive_and_parallel_retry_keeps_manual_edits(
    model_database: Database,
    tmp_path: Path,
) -> None:
    teacher, _, _, _, pupil_id, _ = await setup_two_teachers_with_classes(model_database)
    plan = build_refresh_manifest(source_files(tmp_path / "csv"), year=2026)
    async with model_database.session() as session:
        account = await session.get(Staff, teacher.staff_id)
        assert account
        names = (account.username,) * 7
    with pytest.raises(RuntimeError):
        async with model_database.session() as session, session.begin():
            await refresh_dataset(
                session, plan, expected_digest=plan.digest(), apply=True, teacher_usernames=names
            )
            raise RuntimeError("Synthetic crash before commit")
    async with model_database.session() as session:
        assert await session.get(Student, pupil_id) is not None
        assert await session.get(ImportReceipt, RECEIPT) is None

    async def apply() -> str:
        async with model_database.session() as session, session.begin():
            result = await refresh_dataset(
                session, plan, expected_digest=plan.digest(), apply=True, teacher_usernames=names
            )
            return str(result["status"])

    assert sorted(await asyncio.gather(apply(), apply())) == ["already_applied", "applied"]
    async with model_database.session() as session, session.begin():
        pupil = await session.scalar(select(Student))
        assert pupil
        pupil.school_name = "Admin corrected"
    assert await apply() == "already_applied"
    async with model_database.session() as session:
        pupil = await session.scalar(select(Student))
        assert pupil and pupil.school_name == "Admin corrected"
        with pytest.raises(ValueError):
            await refresh_dataset(
                session, plan, expected_digest="0" * 64, apply=True, teacher_usernames=names
            )


async def test_refresh_suppresses_queued_attendance_and_revokes_legacy_capability(
    model_database: Database,
    tmp_path: Path,
) -> None:
    from test_attendance_outbox_worker import CapturingSender, setup_attendance_fixture

    from neoavlod.errors import DomainError
    from neoavlod.services.onboarding import resolve_link
    from neoavlod.services.outbox import dispatch_pending_outbox

    guardian, pupil, record = await setup_attendance_fixture(model_database)
    plan = build_refresh_manifest(source_files(tmp_path / "csv"), year=2026)
    async with model_database.session() as session, session.begin():
        teacher = await session.get(Staff, record.marked_by)
        assert teacher
        names = (teacher.username,) * 7
        pending = NotificationOutbox(
            idempotency_key="refresh-synthetic",
            attendance_id=record.id,
            parent_id=guardian.id,
            payload={"student_name": "Namuna"},
            status=OutboxStatus.PROCESSING,
        )
        session.add(pending)
        await session.flush()
        key = pending.id
    async with model_database.session() as session, session.begin():
        await refresh_dataset(
            session, plan, expected_digest=plan.digest(), apply=True, teacher_usernames=names
        )
    async with model_database.session() as session:
        archived_pending = await session.get(NotificationOutbox, key)
        assert archived_pending and archived_pending.status == OutboxStatus.SKIPPED
        assert archived_pending.locked_by is None
        with pytest.raises(DomainError):
            await resolve_link(session, f"student_{pupil.auth_uuid}")
        with pytest.raises(DomainError):
            await resolve_link(session, f"parent_{guardian.auth_uuid}")
    sender = CapturingSender()
    assert await dispatch_pending_outbox(model_database, sender=sender) == 0
    assert sender.sent == []


async def test_offline_preflight_validates_digest_and_rejects_macos_sidecars_without_db(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import argparse

    from neoavlod import dataset_refresh
    from neoavlod.refresh_sources import FILES

    root = source_files(tmp_path / "csv")
    plan = build_refresh_manifest(
        root, year=2026, time_overrides={Path(FILES[-1]).stem: ("16:00", "18:00")}
    )

    def forbid_database(*args: object, **kwargs: object) -> None:
        raise AssertionError("Source validation must precede DB/schema maintenance")

    monkeypatch.setattr(dataset_refresh, "Database", forbid_database)
    args = argparse.Namespace(
        source=root, expected_digest=plan.digest(), validate_only=True, apply=False
    )
    assert (await dataset_refresh.run(args))["status"] == "source_validated"
    args.expected_digest = "0" * 64
    with pytest.raises(ValueError, match="digest differs"):
        await dataset_refresh.run(args)
    args.expected_digest = plan.digest()
    (root / ("._" + FILES[0])).write_text("macOS metadata")
    with pytest.raises(ValueError, match="CSV"):
        await dataset_refresh.run(args)
