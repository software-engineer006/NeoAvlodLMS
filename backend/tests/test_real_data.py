import pytest
from argon2 import PasswordHasher
from factories import group, parent, staff, student
from sqlalchemy import func, select

from neoavlod.database import Database
from neoavlod.models import Group, Role, Staff, Student, Subject
from neoavlod.real_data import cleanup_demo


async def seed_demo(db: Database) -> None:
    async with db.session() as session, session.begin():
        admin = staff(
            username="superadmin",
            first_name="Sinov",
            last_name="Superadmin",
            phone="+998990000001",
            role=Role.SUPERADMIN,
            hashed_password=PasswordHasher().hash("1234"),
        )
        teacher = staff(
            username="teacher",
            first_name="Sinov",
            last_name="O‘qituvchi",
            phone="+998990000002",
            role=Role.TEACHER,
            hashed_password=PasswordHasher().hash("1234"),
        )
        subject = Subject(name="Demo matematika", description="Local frontend sinovi")
        session.add_all([admin, teacher, subject])
        await session.flush()
        cohort = group(subject.id, teacher.id, name="Demo guruh")
        session.add(cohort)
        await session.flush()
        for i, name in enumerate(("Ali", "Malika", "Aziz"), 1):
            guardian = parent(first_name="Sinov", last_name="Ota-ona", phone=f"+99899000001{i}")
            session.add(guardian)
            await session.flush()
            session.add(
                student(
                    cohort.id,
                    guardian.id,
                    first_name=name,
                    last_name="Sinov",
                    phone=f"+99899000002{i}",
                    age=14,
                )
            )


@pytest.mark.anyio
async def test_cleanup_rolls_back_with_import_and_preserves_unrelated_staff(
    model_database: Database,
) -> None:
    await seed_demo(model_database)
    async with model_database.session() as session, session.begin():
        session.add(staff(username="unrelated_real_account"))
    with pytest.raises(ValueError, match="Import failed"):
        async with model_database.session() as session, session.begin():
            counts = await cleanup_demo(session, apply=True)
            assert counts["students"] == 3 and counts["staff"] == 2
            raise ValueError("Import failed")
    async with model_database.session() as session:
        assert await session.scalar(select(func.count()).select_from(Student)) == 3
        assert await session.scalar(select(func.count()).select_from(Staff)) == 3
    async with model_database.session() as session, session.begin():
        await cleanup_demo(session, apply=True)
    async with model_database.session() as session, session.begin():
        assert await session.scalar(select(func.count()).select_from(Student)) == 0
        assert await session.scalar(select(func.count()).select_from(Staff)) == 1
        assert (await cleanup_demo(session, apply=True))["staff"] == 0


@pytest.mark.anyio
async def test_cleanup_refuses_real_group_referencing_test_teacher(
    model_database: Database,
) -> None:
    await seed_demo(model_database)
    async with model_database.session() as session, session.begin():
        teacher = await session.scalar(select(Staff).where(Staff.username == "teacher"))
        subject = Subject(name="Real subject")
        session.add(subject)
        await session.flush()
        assert teacher
        session.add(group(subject.id, teacher.id, name="Real group"))
    with pytest.raises(ValueError, match="unrelated references"):
        async with model_database.session() as session, session.begin():
            await cleanup_demo(session, apply=True)
    async with model_database.session() as session:
        assert await session.scalar(select(func.count()).select_from(Group)) == 2
