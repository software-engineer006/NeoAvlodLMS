"""Structured metadata remains scoped to courses and source evidence is preserved."""

import json

import pytest
from sqlalchemy import select
from test_rbac import actor, client_for
from test_teacher_api import setup_two_teachers_with_classes

from neoavlod.database import Database
from neoavlod.models import AuditEvent, Student, StudentGroupEnrollment
from neoavlod.services.enrollments import assign_group

pytestmark = pytest.mark.anyio


async def test_metadata_edit_clear_validation_scope_and_private_audit(
    model_database: Database,
) -> None:
    (
        first_teacher,
        first,
        second_teacher,
        second,
        pupil_id,
        other_id,
    ) = await setup_two_teachers_with_classes(model_database)
    editor = await actor(model_database, permissions=["students:edit"])
    reader = await actor(model_database, permissions=["students:read"])
    async with model_database.session() as session:
        await assign_group(session, pupil_id, second.id)
        primary = await session.scalar(
            select(StudentGroupEnrollment).where(
                StudentGroupEnrollment.student_id == pupil_id,
                StudentGroupEnrollment.group_id == first.id,
            )
        )
        assert primary is not None
        primary.source_data = {"raw_note": "PRIVATE_SOURCE_NOTE"}
        await session.commit()
    profile = f"/api/v1/admin/students/{pupil_id}"
    metadata = f"{profile}/groups/{first.id}"
    async with client_for(reader) as client:
        assert (await client.patch(metadata, json={"level": "Elementary"})).status_code == 403
    async with client_for(editor) as client:
        response = await client.patch(
            profile, json={"school_grade": "7-sinf", "school_name": "Namuna maktab"}
        )
        assert response.status_code == 200, response.text
        assert response.json()["school_name"] == "Namuna maktab"
        response = await client.patch(
            metadata,
            json={"level": "Elementary", "mygov_status": "o‘tdi", "notes": "PRIVATE_COURSE_NOTE"},
        )
        assert response.status_code == 200, response.text
        assert (await client.patch(metadata, json={"level": "x" * 151})).status_code == 422
        assert (await client.patch(metadata, json={"notes": "x" * 4001})).status_code == 422
        assert (await client.patch(metadata, json={"source_data": {}})).status_code == 422
        assert (
            await client.patch(
                f"/api/v1/admin/students/{other_id}/groups/{first.id}", json={"level": "x"}
            )
        ).status_code == 404
    async with client_for(first_teacher) as client:
        payload = (await client.get(f"/api/v1/teacher/students/{pupil_id}")).json()
        assert payload["school_name"] == "Namuna maktab"
        assert payload["level"] == "Elementary" and payload["notes"] == "PRIVATE_COURSE_NOTE"
        assert "source_data" not in payload
    async with client_for(second_teacher) as client:
        payload = (await client.get(f"/api/v1/teacher/students/{pupil_id}")).json()
        assert payload["level"] is None and payload["notes"] is None
        assert "PRIVATE_COURSE_NOTE" not in json.dumps(payload)
    async with model_database.session() as session:
        events = (
            await session.scalars(select(AuditEvent).where(AuditEvent.actor_id == editor.staff_id))
        ).all()
        assert any(
            row.action == "enrollment.update" and "notes" in row.body["private_changed"]
            for row in events
        )
        assert any(
            row.action == "student.update"
            and row.body["changes"].get("school_name", {}).get("after") == "Namuna maktab"
            for row in events
        )
        assert "PRIVATE_COURSE_NOTE" not in json.dumps([row.body for row in events])
    async with client_for(editor) as client:
        assert (
            await client.patch(metadata, json={"level": None, "mygov_status": None, "notes": None})
        ).status_code == 200
        assert (await client.patch(profile, json={"school_name": None})).json()[
            "school_name"
        ] is None
    async with model_database.session() as session:
        primary = await session.scalar(
            select(StudentGroupEnrollment).where(
                StudentGroupEnrollment.student_id == pupil_id,
                StudentGroupEnrollment.group_id == first.id,
            )
        )
        assert primary is not None and primary.source_data == {"raw_note": "PRIVATE_SOURCE_NOTE"}
        pupil = await session.get(Student, pupil_id)
        assert pupil is not None and pupil.school_grade == "7-sinf"


async def test_school_create_optional_bounds_and_no_fabrication(model_database: Database) -> None:
    _, first, _, _, _, _ = await setup_two_teachers_with_classes(model_database)
    editor = await actor(model_database, permissions=["students:create"])
    body = {
        "first_name": "Namuna yangi",
        "group_id": str(first.id),
        "school_grade": "9-sinf",
        "school_name": "Namuna litsey",
    }
    async with client_for(editor) as client:
        response = await client.post("/api/v1/admin/students", json=body)
        assert response.status_code == 201, response.text
        payload = response.json()
        assert payload["school_grade"] == "9-sinf" and payload["school_name"] == "Namuna litsey"
        assert payload["age"] is None and payload["parent"] is None
        assert (
            await client.post("/api/v1/admin/students", json=body | {"school_name": "x" * 151})
        ).status_code == 422


async def test_school_migration_refuses_to_drop_populated_profile(test_database: Database) -> None:
    from factories import group, staff
    from sqlalchemy import text
    from test_migrations import migration

    from neoavlod.database import Base
    from neoavlod.models import Role, Subject

    try:
        migration("upgrade", "head")
        async with test_database.session() as session:
            teacher, subject = staff(role=Role.TEACHER), Subject(name="Namuna kurs")
            session.add_all([teacher, subject])
            await session.flush()
            course = group(subject.id, teacher.id)
            session.add(course)
            await session.flush()
            session.add(
                Student(first_name="Namuna", group_id=course.id, school_name="Namuna maktab")
            )
            await session.commit()
        with pytest.raises(AssertionError, match="School profile data exists"):
            migration("downgrade", "0013_student_enrollments")
    finally:
        async with test_database.engine.begin() as connection:
            await connection.run_sync(Base.metadata.drop_all)
            await connection.execute(text("DROP TABLE IF EXISTS alembic_version"))
