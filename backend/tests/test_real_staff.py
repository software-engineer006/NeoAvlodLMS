import json
from pathlib import Path

import pytest
from sqlalchemy import func, select

from neoavlod.database import Database
from neoavlod.models import Role, Staff, SystemSettings
from neoavlod.real_staff import StaffSpec, prepare, provision_staff
from neoavlod.security.passwords import verify_password
from neoavlod.security.secrets import decrypt_token
from neoavlod.services.onboarding import link_telegram_account, resolve_link
from neoavlod.settings import Settings


@pytest.mark.anyio
async def test_prepared_staff_password_link_isolation_and_rerun(
    model_database: Database,
    tmp_path: Path,
) -> None:
    profiles = [
        StaffSpec(username="fixture_ceo", first_name="Owner", role=Role.SUPERADMIN),
        StaffSpec(username="fixture_teacher", first_name="Teacher", role=Role.TEACHER),
    ]
    path = tmp_path / "private" / "accounts.json"
    accounts = prepare(profiles, path)
    assert path.stat().st_mode & 0o777 == 0o600
    assert prepare(profiles, path) == accounts
    assert "password" in json.loads(path.read_text())[0]
    settings = Settings(environment="test", _env_file=None)
    async with model_database.session() as session, session.begin():
        session.add(SystemSettings(bot_username="FixtureOnlyBot"))
        created, links = await provision_staff(session, accounts, settings)
        assert created == 2 and len(set(links.values())) == 2
        for account in accounts:
            record = await session.scalar(
                select(Staff).where(Staff.username == account.profile.username)
            )
            assert record and record.telegram_id is None and record.must_change_password
            assert verify_password(record.hashed_password, account.password.get_secret_value())
            assert (
                decrypt_token(record.temporary_password_encrypted or "", settings)
                == account.password.get_secret_value()
            )
            assert record.last_name is None and record.phone is None
    async with model_database.session() as session, session.begin():
        assert await provision_staff(session, accounts, settings) == (0, links)
        assert await session.scalar(select(func.count()).select_from(Staff)) == 2
        payload = (links["fixture_teacher"] or "").partition("?start=")[2]
        entity, message = await link_telegram_account(session, payload, 876543, settings)
        assert isinstance(entity, Staff) and entity.username == "fixture_teacher"
        assert "None" not in message and "teacher.eduneo.uz" in message
        owner_payload = (links["fixture_ceo"] or "").partition("?start=")[2]
        assert (await resolve_link(session, owner_payload)).telegram_id is None


@pytest.mark.anyio
async def test_conflicting_staff_is_not_overwritten(
    model_database: Database, tmp_path: Path
) -> None:
    accounts = prepare(
        [StaffSpec(username="fixture_teacher", first_name="Teacher", role=Role.TEACHER)],
        tmp_path / "accounts.json",
    )
    settings = Settings(environment="test", _env_file=None)
    async with model_database.session() as session, session.begin():
        session.add(SystemSettings(bot_username="FixtureOnlyBot"))
        await provision_staff(session, accounts, settings)
    accounts[0].profile.role = Role.SUPERADMIN
    with pytest.raises(ValueError, match="differs"):
        async with model_database.session() as session, session.begin():
            await provision_staff(session, accounts, settings)
    async with model_database.session() as session:
        person = await session.scalar(select(Staff))
        assert person and person.role == Role.TEACHER
