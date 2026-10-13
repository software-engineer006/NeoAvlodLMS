from dataclasses import dataclass

from factories import group, parent, staff, student

from neoavlod.database import Database
from neoavlod.models import (
    AuthSession,
    Group,
    Parent,
    Portal,
    Role,
    Student,
    Subject,
    SystemSettings,
)
from neoavlod.models.common import Status
from neoavlod.security.secrets import encrypt_token
from neoavlod.security.sessions import Identity
from neoavlod.settings import Settings


@dataclass
class World:
    identity: Identity
    groups: list[Group]
    parents: list[Parent]
    students: list[Student]


async def world(database: Database) -> World:
    async with database.session() as session, session.begin():
        owner = staff(role=Role.SUPERADMIN, first_name="Sender")
        teacher = staff(role=Role.TEACHER)
        subject = Subject(name="English")
        session.add_all([owner, teacher, subject])
        await session.flush()
        groups = [
            group(subject.id, teacher.id, name="Group A"),
            group(subject.id, teacher.id, name="Group B"),
            group(subject.id, teacher.id, name="Archived", status=Status.INACTIVE),
        ]
        parents = [
            parent(first_name="Parent One", telegram_id=100),
            parent(first_name="Parent Two"),
            parent(first_name="Parent Three", telegram_id=300, telegram_reconnect_required=True),
            parent(first_name="Orphan Parent", telegram_id=400),
        ]
        session.add_all([*groups, *parents])
        await session.flush()
        pupils = [
            student(groups[0].id, parents[0].id, first_name="Child A", telegram_id=200),
            student(groups[1].id, parents[0].id, first_name="Child B", telegram_id=201),
            student(groups[0].id, parents[1].id, first_name="Child C", telegram_id=202),
            student(groups[1].id, parents[2].id, first_name="Child D"),
            student(groups[2].id, parents[0].id, first_name="Old Child", telegram_id=204),
        ]
        session.add_all(pupils)
        session.add(
            SystemSettings(
                id=1,
                bot_username="example_bot",
                version=1,
                active_version=1,
                parameters={"bot_id": 500},
                bot_token_encrypted=encrypt_token("123:MESSAGE_TEST_TOKEN", Settings()),
            )
        )
        await session.flush()
        return World(Identity(owner, AuthSession(portal=Portal.ADMIN)), groups, parents, pupils)
