"""Room catalogue RBAC, assignment consistency, unique names and audit."""

import asyncio
import uuid

import pytest
from sqlalchemy import select
from test_rbac import actor, client_for
from test_teacher_api import setup_two_teachers_with_classes

from neoavlod.database import Database
from neoavlod.models import AuditEvent, Role, Room
from neoavlod.services.rooms import create_room

pytestmark = pytest.mark.anyio


async def test_room_roles_assignment_rename_and_in_use_rules(model_database: Database) -> None:
    teacher, first, _, _, _, _ = await setup_two_teachers_with_classes(model_database)
    manager = await actor(model_database, permissions=["rooms:manage"])
    editor = await actor(model_database, permissions=["groups:edit"])
    reader = await actor(model_database, permissions=["groups:read"])
    superadmin = await actor(model_database, role=Role.SUPERADMIN)
    for person in (teacher, editor, reader):
        async with client_for(person) as client:
            assert (await client.get("/api/v1/admin/rooms")).status_code == 403
            assert (
                await client.post("/api/v1/admin/rooms", json={"name": "217"})
            ).status_code == 403
    async with client_for(reader) as client:
        assert (await client.get("/api/v1/admin/lookups/rooms")).status_code == 403
    async with client_for(manager) as client:
        response = await client.post(
            "/api/v1/admin/rooms", json={"name": " 217 ", "description": "Namuna xona"}
        )
        assert response.status_code == 201, response.text
        room_id = response.json()["id"]
        assert (await client.post("/api/v1/admin/rooms", json={"name": "217"})).status_code == 409
        assert (
            await client.post("/api/v1/admin/rooms", json={"name": "x" * 31})
        ).status_code == 422
    async with client_for(editor) as client:
        options = (await client.get("/api/v1/admin/lookups/rooms")).json()["items"]
        assert options == [{"id": room_id, "name": "217", "is_active": True}]
        response = await client.patch(f"/api/v1/admin/groups/{first.id}", json={"room_id": room_id})
        assert response.status_code == 200, response.text
        assert response.json()["room_number"] == "217"
        assert response.json()["room_id"] == room_id
        assert (
            await client.patch(
                f"/api/v1/admin/groups/{first.id}",
                json={"room_id": room_id, "room_number": "Wrong"},
            )
        ).status_code == 422
        assert (
            await client.patch(
                f"/api/v1/admin/groups/{first.id}", json={"room_id": str(uuid.uuid4())}
            )
        ).status_code == 404
    async with client_for(manager) as client:
        assert (await client.delete(f"/api/v1/admin/rooms/{room_id}")).status_code == 409
        assert (
            await client.patch(f"/api/v1/admin/rooms/{room_id}", json={"is_active": False})
        ).status_code == 409
        assert (
            await client.patch(f"/api/v1/admin/rooms/{room_id}", json={"name": "218"})
        ).status_code == 200
    async with client_for(teacher) as client:
        assert (await client.get(f"/api/v1/teacher/groups/{first.id}")).json()[
            "room_number"
        ] == "218"
    async with model_database.session() as session:
        records = (
            await session.scalars(select(AuditEvent).where(AuditEvent.entity_type == "room"))
        ).all()
        assert any(
            row.actor_id == manager.staff_id
            and row.action == "room.update"
            and row.body["changes"]["name"] == {"before": "217", "after": "218"}
            for row in records
        )
        assigned = (
            await session.scalars(
                select(AuditEvent).where(
                    AuditEvent.actor_id == editor.staff_id, AuditEvent.action == "group.update"
                )
            )
        ).all()
        assert any(row.body["changes"]["room_id"]["after"]["name"] == "217" for row in assigned)
    async with client_for(editor) as client:
        assert (
            await client.patch(f"/api/v1/admin/groups/{first.id}", json={"room_id": None})
        ).json()["room_number"] is None
    async with client_for(manager) as client:
        assert (
            await client.patch(f"/api/v1/admin/rooms/{room_id}", json={"is_active": False})
        ).status_code == 200
    async with client_for(editor) as client:
        assert (
            await client.patch(f"/api/v1/admin/groups/{first.id}", json={"room_id": room_id})
        ).status_code == 409
        assert (
            await client.patch(f"/api/v1/admin/groups/{first.id}", json={"room_number": "218"})
        ).status_code == 409
    async with client_for(superadmin) as client:
        assert (await client.delete(f"/api/v1/admin/rooms/{room_id}")).status_code == 204


async def test_room_names_are_case_insensitive_under_concurrent_creation(
    model_database: Database,
) -> None:
    from neoavlod.errors import DomainError

    async def add(name: str) -> bool:
        async with model_database.session() as session:
            try:
                await create_room(session, name, None)
                return True
            except DomainError as error:
                assert error.status_code == 409
                return False

    assert sorted(await asyncio.gather(add("Lab A"), add("lab a"))) == [False, True]
    async with model_database.session() as session:
        assert len((await session.scalars(select(Room))).all()) == 1


async def test_room_migration_backfills_labels_and_protects_catalogue(
    test_database: Database,
) -> None:
    from factories import staff
    from sqlalchemy import text
    from test_migrations import migration

    from neoavlod.database import Base
    from neoavlod.models import Group, Subject

    try:
        migration("upgrade", "0014_student_profile")
        async with test_database.session() as session:
            teacher, subject = (
                staff(role=Role.TEACHER),
                Subject(id=uuid.uuid4(), name="Namuna xona fani"),
            )
            session.add(teacher)
            await session.flush()
            await session.execute(
                text("INSERT INTO subjects(id,name) VALUES (:id,:name)"),
                {"id": subject.id, "name": subject.name},
            )
            for label in ("217", "LAB A", "lab a"):
                await session.execute(
                    text("""INSERT INTO groups(id,name,subject_id,teacher_id,
                  max_students,days_of_week,room_number) VALUES
                  (:id,:name,:subject,:teacher,20,'[1,3,5]'::jsonb,:room)"""),
                    {
                        "id": uuid.uuid4(),
                        "name": f"Namuna {label}",
                        "subject": subject.id,
                        "teacher": teacher.id,
                        "room": label,
                    },
                )
            await session.commit()
        migration("upgrade", "head")
        migration("upgrade", "head")
        migration("check")
        async with test_database.session() as session:
            rooms = (await session.scalars(select(Room))).all()
            assert {room.name.lower() for room in rooms} == {"217", "lab a"}
            groups = (await session.scalars(select(Group))).all()
            assert len(groups) == 3 and all(group.room_id for group in groups)
            assert len({group.room_id for group in groups}) == 2
        with pytest.raises(AssertionError, match="Room catalogue data exists"):
            migration("downgrade", "0014_student_profile")
    finally:
        async with test_database.engine.begin() as connection:
            await connection.run_sync(Base.metadata.drop_all)
            await connection.execute(text("DROP TABLE IF EXISTS alembic_version"))


async def test_room_assignment_racing_deactivation_cannot_leave_active_group_in_inactive_room(
    model_database: Database,
) -> None:
    from neoavlod.models import Group

    _, first, _, _, _, _ = await setup_two_teachers_with_classes(model_database)
    manager = await actor(model_database, permissions=["rooms:manage"])
    editor = await actor(model_database, permissions=["groups:edit"])
    async with client_for(manager) as client:
        room_id = (await client.post("/api/v1/admin/rooms", json={"name": "217"})).json()["id"]
    async with client_for(manager) as manager_client, client_for(editor) as editor_client:
        responses = await asyncio.gather(
            editor_client.patch(f"/api/v1/admin/groups/{first.id}", json={"room_id": room_id}),
            manager_client.patch(f"/api/v1/admin/rooms/{room_id}", json={"is_active": False}),
        )
        assert sorted(response.status_code for response in responses) == [200, 409]
    async with model_database.session() as session:
        room = await session.get(Room, uuid.UUID(room_id))
        course = await session.get(Group, first.id)
        assert room is not None and course is not None
        assert room.is_active if course.room_id is not None else not room.is_active
