import uuid
from datetime import time
from decimal import Decimal
from typing import cast

import pytest
from factories import group, parent, staff, student
from sqlalchemy import Table, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from neoavlod.database import Database
from neoavlod.models import Group, Parent, Student, Subject

pytestmark = pytest.mark.anyio


async def seed_group(database: Database) -> Group:
    async with database.session() as session:
        subject = Subject(name="Matematika")
        teacher = staff()
        session.add_all([subject, teacher])
        await session.flush()
        learning_group = group(subject.id, teacher.id)
        session.add(learning_group)
        await session.commit()
        return learning_group


async def test_student_parent_and_group_round_trip(model_database: Database) -> None:
    learning_group = await seed_group(model_database)
    async with model_database.session() as session:
        guardian = parent()
        session.add(guardian)
        await session.flush()
        learner = student(learning_group.id, guardian.id)
        session.add(learner)
        await session.commit()
        assert learner.auth_uuid != guardian.auth_uuid
    async with model_database.session() as session:
        query = select(Student).options(selectinload(Student.parent), selectinload(Student.group))
        saved = (await session.scalars(query)).one()
        assert saved.parent.phone == "+998901234567"
        assert saved.group.monthly_price == Decimal("450000.00")
        assert saved.group.days_of_week == [1, 3, 5]


@pytest.mark.parametrize(
    "overrides",
    [
        {"monthly_price": -1},
        {"max_students": 0},
        {"max_students": 1001},
        {"start_time": time(11)},
        {"days_of_week": []},
        {"days_of_week": [8]},
        {"days_of_week": "monday"},
        {"teacher_id": uuid.uuid4()},
        {"subject_id": uuid.uuid4()},
    ],
)
async def test_group_checks_and_foreign_keys(
    model_database: Database,
    overrides: dict[str, object],
) -> None:
    existing = await seed_group(model_database)
    values: dict[str, object] = {
        "name": "Invalid group",
        "subject_id": existing.subject_id,
        "teacher_id": existing.teacher_id,
        "monthly_price": Decimal("100"),
        "max_students": 10,
        "days_of_week": [1],
        "start_time": time(9),
        "end_time": time(10),
        "room_number": "1",
    }
    values.update(overrides)
    with pytest.raises(IntegrityError):
        async with model_database.session() as session:
            await session.execute(cast(Table, Group.__table__).insert().values(**values))


@pytest.mark.parametrize(
    "overrides",
    [
        {"age": 2},
        {"age": 101},
        {"group_id": uuid.uuid4()},
        {"parent_id": uuid.uuid4()},
        {"status": "unknown"},
        {"phone": "bad"},
    ],
)
async def test_student_validation_and_foreign_keys(
    model_database: Database,
    overrides: dict[str, object],
) -> None:
    existing = await seed_group(model_database)
    async with model_database.session() as session:
        guardian = parent()
        session.add(guardian)
        await session.commit()
    values: dict[str, object] = {
        "first_name": "Test",
        "last_name": "Student",
        "phone": "+998901234567",
        "age": 12,
        "group_id": existing.id,
        "parent_id": guardian.id,
    }
    values.update(overrides)
    with pytest.raises(IntegrityError):
        async with model_database.session() as session:
            await session.execute(cast(Table, Student.__table__).insert().values(**values))


async def test_parent_is_not_implicitly_deduplicated_by_phone(model_database: Database) -> None:
    async with model_database.session() as session:
        first, second = parent(), parent()
        session.add_all([first, second])
        await session.commit()
        assert first.id != second.id
        assert first.auth_uuid != second.auth_uuid
        assert len((await session.scalars(select(Parent))).all()) == 2
