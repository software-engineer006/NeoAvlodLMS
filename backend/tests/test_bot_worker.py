import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from factories import parent, staff, student
from pydantic import SecretStr
from test_learning_models import seed_group

from neoavlod.database import Database
from neoavlod.errors import DomainError
from neoavlod.models import Role, Staff, SystemSettings
from neoavlod.models.common import Status
from neoavlod.security.secrets import encrypt_token
from neoavlod.services.bot_worker import (
    BotWorker,
    polling_lease,
    process_telegram_update,
)
from neoavlod.services.onboarding import link_telegram_account
from neoavlod.services.telegram import TelegramClient
from neoavlod.settings import Settings
from neoavlod.worker_health import healthy

pytestmark = pytest.mark.anyio


async def test_polling_lease_rejects_competitor_and_releases_after_restart(
    model_database: Database,
) -> None:
    async with polling_lease(model_database) as first:
        assert first is not None
        async with polling_lease(model_database) as second:
            assert second is None
        worker = BotWorker(model_database, Settings())
        assert await worker.run_single_iteration() == 0
    async with polling_lease(model_database) as restarted:
        assert restarted is not None


async def test_rejected_start_keeps_polling_offset_and_health(model_database: Database) -> None:
    settings = Settings()
    async with model_database.session() as session, session.begin():
        session.add(
            SystemSettings(
                bot_token_encrypted=encrypt_token("fixture-only-token", settings),
                bot_username="FixtureOnlyBot",
                version=1,
            )
        )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("getUpdates"):
            return httpx.Response(
                200,
                json={
                    "ok": True,
                    "result": [
                        {
                            "update_id": 25,
                            "message": {
                                "chat": {"id": 12345, "type": "private"},
                                "text": "/start staff_invalid",
                            },
                        }
                    ],
                },
            )
        return httpx.Response(200, json={"ok": True, "result": {}})

    worker = BotWorker(model_database, settings, transport=httpx.MockTransport(handler))
    assert await worker.run_single_iteration() == 1
    async with model_database.session() as session:
        config = await session.get(SystemSettings, 1)
        assert config and config.last_update_id == 25
        assert config.parameters.get("bot_poll_heartbeat")
    assert await healthy()
    async with model_database.session() as session, session.begin():
        config = await session.get(SystemSettings, 1)
        assert config
        config.parameters = {
            **config.parameters,
            "bot_poll_heartbeat": (datetime.now(UTC) - timedelta(minutes=2)).isoformat(),
        }
    assert not await healthy()


async def test_link_telegram_account_staff_parent_student(model_database: Database) -> None:
    learning_group = await seed_group(model_database)
    async with model_database.session() as session, session.begin():
        teacher_staff = staff(role=Role.TEACHER)
        session.add(teacher_staff)
        guardian = parent()
        session.add(guardian)
        await session.flush()
        learner = student(learning_group.id, guardian.id)
        session.add(learner)

    # 1. Link Staff
    async with model_database.session() as session:
        entity, msg = await link_telegram_account(
            session, f"staff_{teacher_staff.auth_uuid}", 111222
        )
        await session.commit()
        assert entity.id == teacher_staff.id
        assert entity.telegram_id == 111222
        assert "bir martalik tasdiqlash kodini olasiz" in msg

    # 2. Link Parent
    async with model_database.session() as session:
        entity, msg = await link_telegram_account(session, f"parent_{guardian.auth_uuid}", 222333)
        await session.commit()
        assert entity.id == guardian.id
        assert entity.telegram_id == 222333
        assert "bildirishnomalar shu yerga yuboriladi" in msg

    # 3. Link Student
    async with model_database.session() as session:
        entity, msg = await link_telegram_account(session, f"student_{learner.auth_uuid}", 333444)
        await session.commit()
        assert entity.id == learner.id
        assert entity.telegram_id == 333444
        assert "muvaffaqiyatli bog‘landi" in msg


async def test_link_telegram_account_rejects_invalid_payload(model_database: Database) -> None:
    async with model_database.session() as session:
        # Invalid telegram ID
        with pytest.raises(DomainError, match="yaroqsiz"):
            await link_telegram_account(session, f"staff_{uuid.uuid4()}", -5)

        # Invalid payload shape
        for bad in ("admin_123", "staff_not_a_uuid", "x" * 65):
            with pytest.raises(DomainError, match="yaroqsiz"):
                await link_telegram_account(session, bad, 10001)

        # Non-existent UUID
        with pytest.raises(DomainError, match="yaroqsiz yoki muddati tugagan"):
            await link_telegram_account(session, f"staff_{uuid.uuid4()}", 10001)


async def test_link_telegram_account_rejects_expired_or_used(model_database: Database) -> None:
    async with model_database.session() as session, session.begin():
        person = staff()
        session.add(person)
        await session.flush()
        person.auth_expires_at = datetime.now(UTC) - timedelta(hours=1)

    # Expired
    async with model_database.session() as session:
        with pytest.raises(DomainError, match="muddati tugagan"):
            await link_telegram_account(session, f"staff_{person.auth_uuid}", 10002)

    # Reset expiry but mark as used
    async with model_database.session() as session, session.begin():
        person_db = await session.get(Staff, person.id)
        assert person_db is not None
        person_db.auth_expires_at = datetime.now(UTC) + timedelta(days=1)
        person_db.auth_used_at = datetime.now(UTC)

    async with model_database.session() as session:
        with pytest.raises(DomainError, match="allaqachon ishlatilgan"):
            await link_telegram_account(session, f"staff_{person.auth_uuid}", 10002)


async def test_link_telegram_account_rejects_inactive(model_database: Database) -> None:
    async with model_database.session() as session, session.begin():
        person = staff(status=Status.INACTIVE)
        session.add(person)

    async with model_database.session() as session:
        with pytest.raises(DomainError, match="faol emas"):
            await link_telegram_account(session, f"staff_{person.auth_uuid}", 10003)


async def test_link_telegram_account_prevents_duplicate_telegram_id(
    model_database: Database,
) -> None:
    async with model_database.session() as session, session.begin():
        first = staff(telegram_id=999888)
        second = staff()
        session.add_all([first, second])

    async with model_database.session() as session:
        with pytest.raises(DomainError, match="allaqachon boshqa foydalanuvchiga"):
            await link_telegram_account(session, f"staff_{second.auth_uuid}", 999888)


async def test_process_telegram_update_flow(model_database: Database) -> None:
    sent_messages: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "sendMessage" in url:
            sent_messages.append(request.read().decode())
            return httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)
    client = TelegramClient("dummy_token", transport=transport)

    async with model_database.session() as session, session.begin():
        person = staff()
        session.add(person)

    # 1. /start with valid token
    async with model_database.session() as session:
        update = {
            "update_id": 1,
            "message": {
                "chat": {"id": 777666},
                "text": f"/start staff_{person.auth_uuid}",
            },
        }
        handled = await process_telegram_update(session, client, update)
        assert handled is True
        assert len(sent_messages) == 1
        assert "muvaffaqiyatli bog‘landi" in sent_messages[0]

    # Verify DB update
    async with model_database.session() as session:
        saved = await session.get(Staff, person.id)
        assert saved is not None
        assert saved.telegram_id == 777666
        assert saved.auth_used_at is not None

    # 2. Plain /start without token
    async with model_database.session() as session:
        sent_messages.clear()
        update = {
            "update_id": 2,
            "message": {"chat": {"id": 777666}, "text": "/start"},
        }
        handled = await process_telegram_update(session, client, update)
        assert handled is True
        assert len(sent_messages) == 1
        assert "NeoAvlod LMS" in sent_messages[0]

    # 3. /start with invalid token
    async with model_database.session() as session:
        sent_messages.clear()
        update = {
            "update_id": 3,
            "message": {"chat": {"id": 777666}, "text": "/start staff_invalid"},
        }
        handled = await process_telegram_update(session, client, update)
        assert handled is True
        assert len(sent_messages) == 1
        assert "Xatolik" in sent_messages[0]


async def test_bot_worker_single_iteration(model_database: Database) -> None:
    settings = Settings()
    token = "test_bot_token_worker"
    encrypted = encrypt_token(token, settings)

    async with model_database.session() as session, session.begin():
        person = staff()
        session.add(person)
        sys_settings = SystemSettings(
            id=1,
            bot_token_encrypted=encrypted,
            bot_username="test_worker_bot",
            version=1,
            active_version=0,
            last_update_id=0,
        )
        session.add(sys_settings)

    mock_update = {
        "update_id": 55,
        "message": {
            "chat": {"id": 888999},
            "text": f"/start staff_{person.auth_uuid}",
        },
    }

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "getUpdates" in url:
            return httpx.Response(200, json={"ok": True, "result": [mock_update]})
        if "sendMessage" in url:
            return httpx.Response(200, json={"ok": True, "result": {"message_id": 10}})
        return httpx.Response(200, json={"ok": True})

    worker = BotWorker(model_database, settings, transport=httpx.MockTransport(handler))
    processed = await worker.run_single_iteration()
    assert processed == 1

    async with model_database.session() as session:
        conf = await session.get(SystemSettings, 1)
        assert conf is not None
        assert conf.last_update_id == 55
        assert conf.active_version == 1
        linked = await session.get(Staff, person.id)
        assert linked is not None
        assert linked.telegram_id == 888999


async def test_bot_worker_dynamic_reload_shuts_down_old_polling(
    model_database: Database,
) -> None:
    settings = Settings()
    token_v1 = "token_v1"
    encrypted_v1 = encrypt_token(token_v1, settings)

    async with model_database.session() as session, session.begin():
        sys_settings = SystemSettings(
            id=1,
            bot_token_encrypted=encrypted_v1,
            bot_username="v1_bot",
            version=1,
            active_version=1,
            last_update_id=0,
        )
        session.add(sys_settings)

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "deleteWebhook" in url:
            return httpx.Response(200, json={"ok": True})
        if "getUpdates" in url:
            return httpx.Response(200, json={"ok": True, "result": []})
        return httpx.Response(200, json={"ok": True})

    worker = BotWorker(
        model_database,
        settings,
        transport=httpx.MockTransport(handler),
        poll_timeout=0,
    )
    client_v1 = TelegramClient(token_v1, transport=httpx.MockTransport(handler))

    # Start polling session for version 1
    poll_task = asyncio.create_task(worker._poll_session(client_v1, version=1))

    # Let it run one cycle
    await asyncio.sleep(0.05)

    # Now simulate superadmin updating token in DB to version 2
    async with model_database.session() as session, session.begin():
        conf = await session.get(SystemSettings, 1)
        assert conf is not None
        conf.version = 2
        conf.bot_username = "v2_bot"

    # Wait for the old polling session task to terminate on its own
    await asyncio.wait_for(poll_task, timeout=3.0)

    # poll_task is done, meaning old polling cleanly exited upon version mismatch
    assert poll_task.done()
    assert not worker.is_stopped  # Worker itself was not stopped, only old session closed


async def test_link_staff_with_temporary_password_delivers_and_wipes_credential(
    model_database: Database,
) -> None:
    settings = Settings(
        database_url=SecretStr("postgresql+asyncpg://user:pass@localhost/db"),
        environment="test",
        admin_origin="https://admin.eduneo.uz",
        teacher_origin="https://teacher.eduneo.uz",
    )
    temp_pw = "Temp-pass-1234!"
    enc_pw = encrypt_token(temp_pw, settings)

    async with model_database.session() as session, session.begin():
        person = staff(role=Role.ADMIN)
        person.temporary_password_encrypted = enc_pw
        person.temporary_password_expires_at = datetime.now(UTC) + timedelta(days=3)
        person.must_change_password = True
        session.add(person)

    sent_messages: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if "sendMessage" in str(request.url):
            sent_messages.append(request.read().decode())
            return httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})
        return httpx.Response(200, json={"ok": True})

    client = TelegramClient("dummy_token", transport=httpx.MockTransport(handler))

    async with model_database.session() as session:
        update = {
            "update_id": 10,
            "message": {
                "chat": {"id": 888999, "type": "private"},
                "text": f"/start staff_{person.auth_uuid}",
            },
        }
        handled = await process_telegram_update(session, client, update, settings=settings)
        assert handled is True
        assert len(sent_messages) == 1
        msg = sent_messages[0]
        assert "https://admin.eduneo.uz" in msg
        assert person.username in msg
        assert temp_pw in msg
        assert "Parolingizni yangilab qo‘ying" in msg

    # In DB: telegram_id linked, encrypted temporary password wiped
    async with model_database.session() as session:
        saved = await session.get(Staff, person.id)
        assert saved is not None
        assert saved.telegram_id == 888999
        assert saved.auth_used_at is not None
        assert saved.temporary_password_encrypted is None
        assert saved.temporary_password_expires_at is None
        assert saved.must_change_password is True


async def test_delivery_failure_retains_credential_for_retry(
    model_database: Database,
) -> None:
    settings = Settings(
        database_url=SecretStr("postgresql+asyncpg://user:pass@localhost/db"),
        environment="test",
    )
    temp_pw = "Temp-pass-retry!"
    enc_pw = encrypt_token(temp_pw, settings)

    async with model_database.session() as session, session.begin():
        person = staff(role=Role.TEACHER)
        person.temporary_password_encrypted = enc_pw
        person.temporary_password_expires_at = datetime.now(UTC) + timedelta(days=3)
        person.must_change_password = True
        session.add(person)

    def failing_handler(request: httpx.Request) -> httpx.Response:
        if "sendMessage" in str(request.url):
            return httpx.Response(500, json={"ok": False, "description": "Telegram network error"})
        return httpx.Response(200, json={"ok": True})

    client = TelegramClient("dummy_token", transport=httpx.MockTransport(failing_handler))

    async with model_database.session() as session:
        update = {
            "update_id": 11,
            "message": {
                "chat": {"id": 555666, "type": "private"},
                "text": f"/start staff_{person.auth_uuid}",
            },
        }
        handled = await process_telegram_update(session, client, update, settings=settings)
        assert handled is True

    # In DB: transaction rolled back; credential is NOT lost
    async with model_database.session() as session:
        saved = await session.get(Staff, person.id)
        assert saved is not None
        assert saved.telegram_id is None
        assert saved.auth_used_at is None
        assert saved.temporary_password_encrypted == enc_pw


async def test_repeat_start_does_not_reveal_password_and_explains_reset(
    model_database: Database,
) -> None:
    settings = Settings(
        database_url=SecretStr("postgresql+asyncpg://user:pass@localhost/db"),
        environment="test",
        teacher_origin="https://teacher.eduneo.uz",
    )
    async with model_database.session() as session, session.begin():
        person = staff(role=Role.TEACHER)
        person.telegram_id = 444333
        person.auth_used_at = datetime.now(UTC)
        person.temporary_password_encrypted = None
        session.add(person)

    sent_messages: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if "sendMessage" in str(request.url):
            sent_messages.append(request.read().decode())
            return httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})
        return httpx.Response(200, json={"ok": True})

    client = TelegramClient("dummy_token", transport=httpx.MockTransport(handler))

    # 1. Plain /start from linked staff
    async with model_database.session() as session:
        update = {
            "update_id": 12,
            "message": {
                "chat": {"id": 444333, "type": "private"},
                "text": "/start",
            },
        }
        handled = await process_telegram_update(session, client, update, settings=settings)
        assert handled is True
        assert len(sent_messages) == 1
        msg = sent_messages[0]
        assert "saqlanmaydi" in msg
        assert "Parolni unutdingizmi?" in msg
        assert "https://teacher.eduneo.uz" in msg

    # 2. Re-using old token
    sent_messages.clear()
    async with model_database.session() as session:
        update = {
            "update_id": 13,
            "message": {
                "chat": {"id": 444333, "type": "private"},
                "text": f"/start staff_{person.auth_uuid}",
            },
        }
        handled = await process_telegram_update(session, client, update, settings=settings)
        assert handled is True
        assert len(sent_messages) == 1
        msg = sent_messages[0]
        assert "ishlatilgan" in msg
        assert "Parolni unutdingizmi?" in msg
