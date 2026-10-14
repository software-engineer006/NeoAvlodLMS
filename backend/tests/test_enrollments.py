"""Multiple courses preserve identity, ownership, capacity and notification scope."""

import asyncio
import uuid
from datetime import date

import pytest
from factories import student
from sqlalchemy import func, select
from test_rbac import actor, client_for
from test_teacher_api import setup_two_teachers_with_classes

from neoavlod.database import Database
from neoavlod.errors import DomainError
from neoavlod.models import AuditEvent, Group, NotificationOutbox, Student, StudentGroupEnrollment
from neoavlod.models.common import Status
from neoavlod.services.enrollments import assign_group
from neoavlod.services.messages import candidates
from neoavlod.services.students import set_student_active, transfer_student

pytestmark = pytest.mark.anyio


async def test_shared_identity_teacher_context_and_membership_api(model_database: Database) -> None:
    teacher_a, group_a, teacher_b, group_b, pupil_id, _ = await setup_two_teachers_with_classes(
        model_database
    )
    editor = await actor(model_database, permissions=["students:edit"])
    reader = await actor(model_database, permissions=["students:read"])
    route = f"/api/v1/admin/students/{pupil_id}/groups/{group_b.id}"
    async with client_for(reader) as client:
        assert (await client.put(route, json={"is_active": True})).status_code == 403
    async with client_for(editor) as client:
        for _ in range(2):
            response = await client.put(route, json={"is_active": True})
            assert response.status_code == 200, response.text
            assert len(response.json()["enrollments"]) == 2
    async with model_database.session() as session:
        assert await session.scalar(select(func.count()).select_from(Student)) == 2
        rows = await candidates(session)
        shared = [row for row in rows if row.kind == "student" and row.id == pupil_id]
        assert len(shared) == 1
        assert set(shared[0].group_names) == {group_a.name, group_b.name}
        events = (
            await session.scalars(
                select(AuditEvent).where(
                    AuditEvent.action == "enrollment.insert", AuditEvent.actor_id == editor.staff_id
                )
            )
        ).all()
        assert len(events) == 1
        assert events[0].body["changes"]["group_id"]["after"]["name"] == group_b.name
        assert events[0].body["changes"]["student_id"]["after"]["id"] == str(pupil_id)
    for teacher, owned, foreign in [(teacher_a, group_a, group_b), (teacher_b, group_b, group_a)]:
        async with client_for(teacher) as client:
            response = await client.get(f"/api/v1/teacher/students/{pupil_id}")
            assert response.status_code == 200
            assert response.json()["group_id"] == str(owned.id)
            assert response.json()["group_name"] == owned.name
            assert (
                await client.get(f"/api/v1/teacher/students/{pupil_id}?group_id={foreign.id}")
            ).status_code == 404
            roster = (await client.get(f"/api/v1/teacher/groups/{owned.id}/students")).json()
            shared_profile = next(row for row in roster if row["id"] == str(pupil_id))
            assert shared_profile["group_id"] == str(owned.id)
    async with client_for(editor) as client:
        assert (await client.put(route, json={"is_active": False})).status_code == 200
    async with client_for(teacher_b) as client:
        assert (await client.get(f"/api/v1/teacher/students/{pupil_id}")).status_code == 404


async def test_secondary_group_capacity_serializes_and_reactivation_checks_all(
    model_database: Database,
) -> None:
    _, first, _, second, pupil_id, _ = await setup_two_teachers_with_classes(model_database)
    async with model_database.session() as session:
        second_row = await session.get(Group, second.id)
        assert second_row is not None
        second_row.max_students = 2
        newcomer = student(first.id, None, first_name="Namuna")
        session.add(newcomer)
        await session.commit()
        newcomer_id = newcomer.id

    async def enroll(key: uuid.UUID) -> bool:
        async with model_database.session() as session:
            try:
                await assign_group(session, key, second.id)
                return True
            except DomainError as error:
                assert error.status_code == 409
                return False

    outcomes = await asyncio.gather(enroll(pupil_id), enroll(newcomer_id))
    assert sorted(outcomes) == [False, True]
    winner = pupil_id if outcomes[0] else newcomer_id
    loser = newcomer_id if outcomes[0] else pupil_id
    async with model_database.session() as session:
        await set_student_active(session, winner, active=False)
        await assign_group(session, loser, second.id)
        with pytest.raises(DomainError, match="bo‘sh joy"):
            await set_student_active(session, winner, active=True)
        await session.rollback()
        inactive = await session.get(Student, winner)
        assert inactive is not None and inactive.status == Status.INACTIVE


async def test_primary_transfer_keeps_other_course_and_historical_membership(
    model_database: Database,
) -> None:
    _, first, _, second, pupil_id, _ = await setup_two_teachers_with_classes(model_database)
    async with model_database.session() as session:
        third = Group(
            name="Namuna boshqa kurs",
            subject_id=first.subject_id,
            teacher_id=first.teacher_id,
            max_students=20,
            days_of_week=[1],
        )
        session.add(third)
        await session.commit()
        await assign_group(session, pupil_id, third.id)
        await assign_group(session, pupil_id, second.id)
        await transfer_student(session, pupil_id, second.id)
        memberships = (
            await session.scalars(
                select(StudentGroupEnrollment).where(StudentGroupEnrollment.student_id == pupil_id)
            )
        ).all()
        assert len(memberships) == 3
        assert {row.group_id for row in memberships if row.is_active} == {second.id, third.id}
        assert any(row.group_id == first.id and not row.is_active for row in memberships)


async def test_secondary_attendance_uses_owned_group_and_scoped_statistics(
    model_database: Database, attendance_clock: None
) -> None:
    (
        teacher_a,
        group_a,
        teacher_b,
        group_b,
        pupil_id,
        other_id,
    ) = await setup_two_teachers_with_classes(model_database)
    async with model_database.session() as session:
        await assign_group(session, pupil_id, group_b.id)
    async with client_for(teacher_b) as client:
        response = await client.post(
            f"/api/v1/teacher/groups/{group_b.id}/attendance/finalize",
            json={
                "date": date(2026, 10, 5).isoformat(),
                "items": [
                    {"student_id": str(pupil_id), "status": "present", "note": "Namuna izoh"},
                    {"student_id": str(other_id), "status": "absent"},
                ],
            },
        )
        assert response.status_code == 200, response.text
        profile = (await client.get(f"/api/v1/teacher/students/{pupil_id}?month=2026-10")).json()
        assert profile["attendance_stats"]["present_count"] == 1
    async with client_for(teacher_a) as client:
        profile = (await client.get(f"/api/v1/teacher/students/{pupil_id}?month=2026-10")).json()
        assert profile["attendance_stats"]["total_lessons"] == 0
    async with model_database.session() as session:
        queued = (await session.scalars(select(NotificationOutbox))).all()
        assert len(queued) == 2
        assert all(item.payload["group_name"] == group_b.name for item in queued)
        assert group_a.name != group_b.name
