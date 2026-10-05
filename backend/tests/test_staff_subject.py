import uuid
from typing import cast

import pytest
from factories import staff
from sqlalchemy import Table, select
from sqlalchemy.exc import IntegrityError

from neoavlod.database import Database
from neoavlod.models import Role, Staff, Subject
from neoavlod.models.common import Status

pytestmark = pytest.mark.anyio


async def test_staff_defaults_uuid_and_mutable_permissions(model_database: Database) -> None:
    person = staff()
    async with model_database.session() as session:
        session.add(person)
        await session.commit()
        assert isinstance(person.id, uuid.UUID)
        assert person.auth_uuid != person.id
        assert person.role == Role.TEACHER
        assert person.status == Status.ACTIVE
        assert person.permissions == []
        assert person.auth_expires_at > person.created_at
        person.permissions.append("students:create")
        await session.commit()
    async with model_database.session() as session:
        saved = await session.get(Staff, person.id)
        assert saved is not None
        assert saved.permissions == ["students:create"]


@pytest.mark.parametrize("field", ["phone", "username", "telegram_id", "auth_uuid"])
async def test_staff_identity_is_unique(model_database: Database, field: str) -> None:
    first = staff(telegram_id=12345)
    async with model_database.session() as session:
        session.add(first)
        await session.commit()
    second = staff(**{field: getattr(first, field)})
    with pytest.raises(IntegrityError):
        async with model_database.session() as session:
            session.add(second)
            await session.flush()


@pytest.mark.parametrize(
    "overrides",
    [
        {"role": "owner"},
        {"status": "unknown"},
        {"phone": "998123"},
        {"username": "UPPERCASE"},
        {"first_name": " "},
        {"telegram_id": -1},
        {"permissions": {"staff:manage": True}},
    ],
)
async def test_staff_invalid_values_rejected_by_database(
    model_database: Database,
    overrides: dict[str, object],
) -> None:
    # SQL Core bypasses MutableList's Python validation to test DB constraints.
    person = staff()
    values = {
        "first_name": person.first_name,
        "last_name": person.last_name,
        "phone": person.phone,
        "username": person.username,
        "hashed_password": person.hashed_password,
    } | overrides
    with pytest.raises(IntegrityError):
        async with model_database.session() as session:
            await session.execute(cast(Table, Staff.__table__).insert().values(**values))


async def test_subject_default_and_deactivate(model_database: Database) -> None:
    async with model_database.session() as session:
        subject = Subject(name="Matematika", description="Asosiy kurs")
        session.add(subject)
        await session.commit()
        assert subject.is_active
        subject.is_active = False
        await session.commit()
    async with model_database.session() as session:
        saved = (await session.scalars(select(Subject))).one()
        assert not saved.is_active
        assert saved.description == "Asosiy kurs"


async def test_subject_blank_name_rejected(model_database: Database) -> None:
    with pytest.raises(IntegrityError):
        async with model_database.session() as session:
            session.add(Subject(name=" "))
            await session.flush()
