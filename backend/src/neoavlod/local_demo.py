"""Explicit local-only app factory and isolated demo database seeding."""

import asyncio
import re
import uuid
from datetime import UTC, datetime, time
from decimal import Decimal

from argon2 import PasswordHasher
from fastapi import FastAPI, Response
from sqlalchemy import select
from sqlalchemy.engine import make_url

from neoavlod.api.deps import SessionDependency
from neoavlod.database import Database
from neoavlod.errors import DomainError
from neoavlod.main import create_app
from neoavlod.models import Group, OTPChallenge, Parent, Portal, Role, Staff, Student, Subject
from neoavlod.services.login import code_hash
from neoavlod.settings import Settings

DEMO_IDS = {"superadmin": 900000001, "teacher": 900000002}


def ensure_local(settings: Settings) -> None:
    url = make_url(settings.database_url.get_secret_value())
    if settings.environment != "development" or url.database != "neoavlod_demo":
        raise RuntimeError("Local demo requires development and the isolated neoavlod_demo DB")


class LocalSender:
    def __init__(self) -> None:
        self.codes: dict[int, str] = {}

    async def send_message(self, telegram_id: int, message: str) -> None:
        match = re.search(r"kodi: ([0-9]{6})", message)
        if telegram_id not in DEMO_IDS.values() or match is None:
            raise DomainError("Local demo faqat sinov hisoblariga kod yuboradi", 403)
        self.codes[telegram_id] = match[1]


def create_demo_app(settings: Settings | None = None) -> FastAPI:
    config = settings or Settings()
    ensure_local(config)
    app = create_app(config)
    sender = LocalSender()
    app.state.telegram_sender = sender

    @app.get("/api/v1/local-demo/{portal}/otp/{challenge_id}", include_in_schema=False)
    async def local_otp(
        portal: Portal, challenge_id: uuid.UUID, session: SessionDependency, response: Response
    ) -> dict[str, str]:
        response.headers["Cache-Control"] = "no-store"
        challenge = await session.get(OTPChallenge, challenge_id)
        if (
            challenge is None
            or challenge.portal != portal
            or challenge.consumed_at is not None
            or challenge.expires_at <= datetime.now(UTC)
            or challenge.delivered_at is None
            or challenge.attempts >= 5
        ):
            raise DomainError("Local kod topilmadi", 404)
        person = await session.get(Staff, challenge.staff_id)
        code = sender.codes.get(person.telegram_id or 0) if person else None
        if (
            not person
            or DEMO_IDS.get(person.username) != person.telegram_id
            or not code
            or code_hash(config, challenge, code) != challenge.code_hash
        ):
            raise DomainError("Local kod topilmadi", 404)
        return {"code": code}

    return app


async def seed_demo(settings: Settings) -> None:
    ensure_local(settings)
    database = Database(settings)
    try:
        async with database.session() as session:
            accounts: dict[str, Staff] = {}
            for index, (username, telegram_id) in enumerate(DEMO_IDS.items(), start=1):
                person = await session.scalar(select(Staff).where(Staff.username == username))
                if person is None:
                    person = Staff(
                        username=username,
                        first_name="Sinov",
                        last_name="Superadmin" if index == 1 else "O‘qituvchi",
                        phone=f"+99899000000{index}",
                        # Only this explicit isolated seed permits the requested short password.
                        hashed_password=PasswordHasher().hash("1234"),
                        role=Role.SUPERADMIN if index == 1 else Role.TEACHER,
                        telegram_id=telegram_id,
                        permissions=[],
                    )
                    session.add(person)
                    await session.flush()
                accounts[username] = person
            subject = await session.scalar(select(Subject).where(Subject.name == "Demo matematika"))
            if subject is None:
                subject = Subject(name="Demo matematika", description="Local frontend sinovi")
                session.add(subject)
                await session.flush()
            group = await session.scalar(select(Group).where(Group.name == "Demo guruh"))
            if group is None:
                group = Group(
                    name="Demo guruh",
                    subject_id=subject.id,
                    teacher_id=accounts["teacher"].id,
                    monthly_price=Decimal("450000"),
                    max_students=20,
                    days_of_week=[1, 3, 5],
                    start_time=time(9),
                    end_time=time(10),
                    room_number="101",
                )
                session.add(group)
                await session.flush()
                for index, name in enumerate(("Ali", "Malika", "Aziz"), start=1):
                    parent = Parent(
                        first_name="Sinov", last_name="Ota-ona", phone=f"+99899000001{index}"
                    )
                    session.add(parent)
                    await session.flush()
                    session.add(
                        Student(
                            first_name=name,
                            last_name="Sinov",
                            phone=f"+99899000002{index}",
                            age=14,
                            group_id=group.id,
                            parent_id=parent.id,
                        )
                    )
            await session.commit()
    finally:
        await database.close()


if __name__ == "__main__":
    asyncio.run(seed_demo(Settings()))
    print("Local demo hisoblari va guruh tayyor.")
