import uuid
from datetime import UTC, datetime, timedelta

import pytest
from factories import parent, staff, student
from test_learning_models import seed_group

from neoavlod.database import Database
from neoavlod.errors import DomainError
from neoavlod.models import SystemSettings
from neoavlod.models.common import Status
from neoavlod.services.onboarding import link_state, resolve_link, rotate_staff_link

pytestmark = pytest.mark.anyio


async def test_link_generation_rotation_and_old_token_revocation(model_database: Database) -> None:
    async with model_database.session() as session, session.begin():
        session.add(
            SystemSettings(bot_username="NeoAvlodBot", bot_token_encrypted="test-ciphertext")
        )
        person = staff()
        session.add(person)
        state = await link_state(session, person)
        old = person.auth_uuid
        assert state.deep_link == f"https://t.me/NeoAvlodBot?start=staff_{old}"
        assert not state.connected
    async with model_database.session() as session, session.begin():
        renewed = await rotate_staff_link(session, person.id)
        assert renewed.deep_link != state.deep_link
        with pytest.raises(DomainError, match="yaroqsiz"):
            await resolve_link(session, f"staff_{old}")
        payload = (renewed.deep_link or "").partition("?start=")[2]
        assert (await resolve_link(session, payload)).id == person.id


@pytest.mark.parametrize("override", ["expired", "used", "inactive"])
async def test_link_cannot_resolve_expired_used_or_inactive_staff(
    model_database: Database,
    override: str,
) -> None:
    async with model_database.session() as session, session.begin():
        person = staff()
        session.add(person)
        await session.flush()
        if override == "expired":
            person.auth_expires_at = datetime.now(UTC) - timedelta(days=1)
        elif override == "used":
            person.auth_used_at = datetime.now(UTC)
        else:
            person.status = Status.INACTIVE
        await session.flush()
        with pytest.raises(DomainError):
            await resolve_link(session, f"staff_{person.auth_uuid}")


async def test_connected_account_cannot_be_relinked(model_database: Database) -> None:
    async with model_database.session() as session, session.begin():
        person = staff(telegram_id=123456)
        session.add(person)
        state = await link_state(session, person)
        assert state.connected and state.deep_link is None
        with pytest.raises(DomainError, match="allaqachon"):
            await rotate_staff_link(session, person.id)


async def test_missing_bot_and_invalid_payloads_are_rejected(model_database: Database) -> None:
    async with model_database.session() as session, session.begin():
        person = staff()
        session.add(person)
        with pytest.raises(DomainError, match="sozlanishi"):
            await link_state(session, person)
        for payload in ("admin_bad", "staff_bad", f"staff_{uuid.uuid4()}", "x" * 65):
            with pytest.raises(DomainError):
                await resolve_link(session, payload)


async def test_parent_and_student_receive_distinct_links(model_database: Database) -> None:
    learning_group = await seed_group(model_database)
    async with model_database.session() as session, session.begin():
        session.add(
            SystemSettings(bot_username="NeoAvlodBot", bot_token_encrypted="test-ciphertext")
        )
        guardian = parent()
        session.add(guardian)
        await session.flush()
        learner = student(learning_group.id, guardian.id)
        session.add(learner)
        for entity, prefix in ((guardian, "parent"), (learner, "student")):
            state = await link_state(session, entity)
            assert state.deep_link == f"https://t.me/NeoAvlodBot?start={prefix}_{entity.auth_uuid}"
            assert (await resolve_link(session, f"{prefix}_{entity.auth_uuid}")).id == entity.id
