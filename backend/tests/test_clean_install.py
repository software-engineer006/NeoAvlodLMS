"""Disposable clean-install and CEO activation evidence; no real Telegram traffic."""

from pathlib import Path

import httpx
import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError
from test_refresh_sources import source_files

from neoavlod.audit_context import bind_source, emit
from neoavlod.clean_install import EXPECTED, InitialProfile, provision_clean_install
from neoavlod.database import Database
from neoavlod.models import AuditActivation, AuditEvent, Role, Staff, Student
from neoavlod.refresh_sources import build_refresh_manifest
from neoavlod.security.passwords import verify_password
from neoavlod.security.secrets import decrypt_token
from neoavlod.services.bot_settings import update_bot_token
from neoavlod.services.bot_worker import process_telegram_update
from neoavlod.services.onboarding import link_telegram_account
from neoavlod.services.telegram import TelegramClient
from neoavlod.settings import Settings

pytestmark = pytest.mark.anyio


async def initialized(database: Database, path: Path) -> list[Staff]:
    plan = build_refresh_manifest(source_files(path / "csv"), year=2026)
    profiles = [
        InitialProfile(username=name, first_name="Namuna", last_name="Hisob", role=role)
        for name, role in EXPECTED.items()
    ]
    async with database.session() as session, session.begin():
        result = await provision_clean_install(
            session, profiles, plan, Settings(), expected_digest=plan.digest()
        )
        assert result["new"]["profiles"] == 1
    async with database.session() as session:
        assert await session.scalar(select(func.count()).select_from(AuditEvent)) == 0
        return list((await session.scalars(select(Staff).order_by(Staff.username))).all())


async def test_empty_install_has_five_new_unlinked_accounts_and_no_import_logs(
    model_database: Database, tmp_path: Path
) -> None:
    accounts = await initialized(model_database, tmp_path)
    assert len(accounts) == 5 and sum(p.role == Role.SUPERADMIN for p in accounts) == 1
    for person in accounts:
        assert person.telegram_id is None and person.auth_used_at is None
        assert person.must_change_password and person.temporary_password_encrypted
        password = decrypt_token(person.temporary_password_encrypted, Settings())
        assert verify_password(person.hashed_password, password)
    async with model_database.session() as session:
        await bind_source(session, "http")
        assert await emit(session, "http.request") == 0
        await session.commit()
        assert await session.scalar(select(func.count()).select_from(Student)) == 1
        assert await session.scalar(select(func.count()).select_from(AuditEvent)) == 0
        gate = await session.get(AuditActivation, 1)
        assert gate and gate.activated_at is None
        assert gate.ceo_id == next(p.id for p in accounts if p.role == Role.SUPERADMIN)


async def test_only_designated_ceo_start_activates_once_and_subsequent_audit_is_immutable(
    model_database: Database, tmp_path: Path
) -> None:
    accounts = await initialized(model_database, tmp_path)
    teacher = next(p for p in accounts if p.role == Role.TEACHER)
    ceo = next(p for p in accounts if p.role == Role.SUPERADMIN)
    async with model_database.session() as session, session.begin():
        await link_telegram_account(session, f"staff_{teacher.auth_uuid}", 101, Settings())
    async with model_database.session() as session:
        assert await session.scalar(select(func.count()).select_from(AuditEvent)) == 0
        assert not await session.scalar(
            text("SELECT audit.activate_onboarding(:id)"), {"id": ceo.id}
        )
    async with model_database.session() as session, session.begin():
        await link_telegram_account(session, f"staff_{ceo.auth_uuid}", 102, Settings())
        assert not await session.scalar(
            text("SELECT audit.activate_onboarding(:id)"), {"id": ceo.id}
        )
    async with model_database.session() as session:
        records = list((await session.scalars(select(AuditEvent).order_by(AuditEvent.id))).all())
        assert [e.action for e in records] == ["audit.activated", "telegram.account_linked"]
        assert all(e.actor_id == ceo.id and e.body["source"] == "telegram" for e in records)
        assert all(str(ceo.auth_uuid) not in str(e.body) for e in records)
        await bind_source(session, "http")
        assert await emit(session, "http.request") > 0
        await session.commit()
        gate = await session.get(AuditActivation, 1)
        assert gate and gate.activated_at
    for sql in (
        "UPDATE audit.activation SET activated_at=NULL",
        "DELETE FROM audit.activation",
        "INSERT INTO audit.activation(id,ceo_id) VALUES(1,gen_random_uuid())",
        "DELETE FROM audit.events",
        "TRUNCATE audit.events",
    ):
        async with model_database.session() as session:
            await session.execute(text("SET LOCAL ROLE neoavlod_app"))
            with pytest.raises(DBAPIError):
                await session.execute(text(sql))
            await session.rollback()


async def test_failed_telegram_delivery_rolls_back_activation_and_credentials_then_retry_works(
    model_database: Database, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    accounts = await initialized(model_database, tmp_path)
    ceo = next(p for p in accounts if p.role == Role.SUPERADMIN)
    update: dict[str, object] = {
        "message": {"chat": {"id": 201, "type": "private"}, "text": f"/start staff_{ceo.auth_uuid}"}
    }
    original = TelegramClient.send_message

    async def fail(self: TelegramClient, ident: int, message: str) -> None:
        raise RuntimeError("Synthetic failed delivery")

    monkeypatch.setattr(TelegramClient, "send_message", fail)
    async with model_database.session() as session:
        assert await process_telegram_update(
            session, TelegramClient("fixture-token"), update, Settings()
        )
    async with model_database.session() as session:
        gate = await session.get(AuditActivation, 1)
        person = await session.get(Staff, ceo.id)
        assert gate and gate.activated_at is None
        assert person and person.telegram_id is None and person.temporary_password_encrypted
        assert await session.scalar(select(func.count()).select_from(AuditEvent)) == 0
    monkeypatch.setattr(TelegramClient, "send_message", original)
    client = TelegramClient(
        "fixture-token",
        httpx.MockTransport(lambda r: httpx.Response(200, json={"ok": True, "result": {}})),
    )
    async with model_database.session() as session:
        assert await process_telegram_update(session, client, update, Settings())
        assert await process_telegram_update(session, client, update, Settings())
    async with model_database.session() as session:
        gate = await session.get(AuditActivation, 1)
        person = await session.get(Staff, ceo.id)
        assert gate and gate.activated_at
        assert person and person.telegram_connected and person.temporary_password_encrypted is None
        assert (
            await session.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(AuditEvent.action == "audit.activated")
            )
            == 1
        )


async def test_nonempty_or_unapproved_input_cannot_arm_or_replace_existing_installation(
    model_database: Database, tmp_path: Path
) -> None:
    await initialized(model_database, tmp_path)
    plan = build_refresh_manifest(source_files(tmp_path / "other"), year=2026)
    profiles = [
        InitialProfile(username=name, first_name="Namuna", role=role)
        for name, role in EXPECTED.items()
    ]
    async with model_database.session() as session:
        with pytest.raises(ValueError, match="empty database"):
            await provision_clean_install(
                session, profiles, plan, Settings(), expected_digest=plan.digest()
            )
        await session.rollback()
        profiles[0] = InitialProfile(
            username="test_superadmin", first_name="Wrong", role=Role.SUPERADMIN
        )
        with pytest.raises(ValueError, match="approved CEO"):
            await provision_clean_install(
                session, profiles, plan, Settings(), expected_digest=plan.digest()
            )
        assert await session.scalar(select(func.count()).select_from(Staff)) == 5


async def test_bot_configuration_can_roll_back_in_caller_transaction(
    model_database: Database,
) -> None:
    transport = httpx.MockTransport(
        lambda r: httpx.Response(
            200,
            json={
                "ok": True,
                "result": {"id": 12345, "is_bot": True, "username": "FixtureOnlyBot"},
            },
        )
    )
    async with model_database.session() as session:
        await update_bot_token(
            session, Settings(), "fixture-only-token", transport=transport, commit=False
        )
        await session.rollback()
        assert await session.scalar(text("SELECT count(*) FROM system_settings")) == 0
