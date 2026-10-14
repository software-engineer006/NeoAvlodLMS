"""Selected course transfers preserve other courses, family and history."""

import asyncio
from datetime import date

import pytest
from factories import group
from sqlalchemy import select
from test_rbac import actor, client_for
from test_teacher_api import setup_two_teachers_with_classes

from neoavlod.database import Database
from neoavlod.models import (
    Attendance,
    AttendanceStatus,
    AuditEvent,
    Student,
    StudentGroupEnrollment,
    Subject,
)
from neoavlod.services.enrollments import assign_group

pytestmark = pytest.mark.anyio


async def test_selected_secondary_transfer_preserves_primary_family_and_metadata(
    model_database: Database,
) -> None:
    _, primary, teacher_b, secondary, pupil_id, _ = await setup_two_teachers_with_classes(
        model_database
    )
    editor = await actor(model_database, permissions=["students:edit"])
    async with model_database.session() as session:
        subject = Subject(name="Python namuna")
        session.add(subject)
        await session.flush()
        second = await session.get(type(secondary), secondary.id)
        assert second is not None
        second.subject_id = subject.id
        target = group(subject.id, teacher_b.staff_id, name="Python yangi")
        session.add(target)
        await session.commit()
        target_id = target.id
        await assign_group(session, pupil_id, secondary.id)
        source = await session.scalar(
            select(StudentGroupEnrollment).where(
                StudentGroupEnrollment.student_id == pupil_id,
                StudentGroupEnrollment.group_id == secondary.id,
            )
        )
        assert source is not None
        source.level, source.mygov_status, source.notes = (
            "Python boshlang‘ich",
            "o‘tdi",
            "Namuna kurs izohi",
        )
        source.source_data = {"source": "private synthetic"}
        pupil = await session.get(Student, pupil_id)
        assert pupil is not None
        parent_id = pupil.parent_id
        old = Attendance(
            student_id=pupil_id,
            group_id=secondary.id,
            date=date(2026, 10, 5),
            status=AttendanceStatus.PRESENT,
            marked_by=teacher_b.staff_id,
        )
        session.add(old)
        await session.commit()
        attendance_id = old.id
    request = {
        "source_group_id": str(secondary.id),
        "target_group_id": str(target_id),
        "reason": "Dars vaqti moslashdi",
    }
    async with client_for(editor) as client:
        assert (
            await client.post(
                f"/api/v1/admin/students/{pupil_id}/transfer", json=request | {"reason": " "}
            )
        ).status_code == 422
        responses = await asyncio.gather(
            *[
                client.post(f"/api/v1/admin/students/{pupil_id}/transfer", json=request)
                for _ in range(2)
            ]
        )
        assert all(response.status_code == 200 for response in responses)
        payload = responses[0].json()
        assert payload["group_id"] == str(primary.id) and payload["parent_id"] == str(parent_id)
        assert {row["group"]["id"] for row in payload["enrollments"] if row["is_active"]} == {
            str(primary.id),
            str(target_id),
        }
        target_data = next(
            row for row in payload["enrollments"] if row["group"]["id"] == str(target_id)
        )
        assert (
            target_data["level"] == "Python boshlang‘ich"
            and target_data["notes"] == "Namuna kurs izohi"
        )
    async with model_database.session() as session:
        historic = await session.get(Attendance, attendance_id)
        assert historic is not None and historic.group_id == secondary.id
        events = (
            await session.scalars(
                select(AuditEvent).where(AuditEvent.action == "student.transferred")
            )
        ).all()
        assert len(events) == 1 and events[0].actor_id == editor.staff_id
        assert events[0].body["details"]["reason"] == request["reason"]
        assert events[0].body["details"]["source_group"]["id"] == str(secondary.id)
        assert events[0].body["details"]["target_group"]["id"] == str(target_id)


async def test_transfer_capacity_race_allows_only_one_and_other_course_survives(
    model_database: Database,
) -> None:
    _, source, teacher, _, first_id, second_id = await setup_two_teachers_with_classes(
        model_database
    )
    editor = await actor(model_database, permissions=["students:edit"])
    async with model_database.session() as session:
        target = group(source.subject_id, teacher.staff_id, max_students=1, name="Bir o‘rin")
        session.add(target)
        await session.commit()
        target_id = target.id
        await assign_group(session, second_id, source.id)
    async with client_for(editor) as client:
        responses = await asyncio.gather(
            *[
                client.post(
                    f"/api/v1/admin/students/{key}/transfer",
                    json={
                        "source_group_id": str(source.id),
                        "target_group_id": str(target_id),
                        "reason": "Jadval",
                    },
                )
                for key in (first_id, second_id)
            ]
        )
        assert sorted(response.status_code for response in responses) == [200, 409]
    async with model_database.session() as session:
        target_members = (
            await session.scalars(
                select(StudentGroupEnrollment).where(
                    StudentGroupEnrollment.group_id == target_id,
                    StudentGroupEnrollment.is_active.is_(True),
                )
            )
        ).all()
        assert len(target_members) == 1


async def test_transfer_racing_secondary_assignment_uses_one_student_lock(
    model_database: Database,
) -> None:
    _, source, _, target, pupil_id, _ = await setup_two_teachers_with_classes(model_database)
    editor = await actor(model_database, permissions=["students:edit"])
    async with client_for(editor) as client:
        transfer, assignment = await asyncio.wait_for(
            asyncio.gather(
                client.post(
                    f"/api/v1/admin/students/{pupil_id}/transfer",
                    json={
                        "source_group_id": str(source.id),
                        "target_group_id": str(target.id),
                        "reason": "Jadval",
                    },
                ),
                client.put(
                    f"/api/v1/admin/students/{pupil_id}/groups/{target.id}",
                    json={"is_active": True},
                ),
            ),
            timeout=5,
        )
        assert transfer.status_code == assignment.status_code == 200
    async with model_database.session() as session:
        active = (
            await session.scalars(
                select(StudentGroupEnrollment.group_id).where(
                    StudentGroupEnrollment.student_id == pupil_id,
                    StudentGroupEnrollment.is_active.is_(True),
                )
            )
        ).all()
        assert active == [target.id]
