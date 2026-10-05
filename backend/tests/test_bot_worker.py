import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from factories import parent, staff, student
from test_learning_models import seed_group

from neoavlod.database import Database
from neoavlod.errors import DomainError
from neoavlod.models import Role, Staff, SystemSettings
from neoavlod.models.common import Status
from neoavlod.security.secrets import encrypt_token
from neoavlod.services.bot_worker import (
    BotWorker,
    process_telegram_update,
)
from neoavlod.services.onboarding import link_telegram_account
from neoavlod.services.telegram import TelegramClient
from neoavlod.settings import Settings

pytestmark = pytest.mark.anyio


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
        entity, msg = await link_telegram_account(
            session, f"parent_{guardian.auth_uuid}", 222333
        )
        await session.commit()
        assert entity.id == guardian.id
        assert entity.telegram_id == 222333
        assert "bildirishnomalar shu yerga yuboriladi" in msg

    # 3. Link Student
    async with model_database.session() as session:
        entity, msg = await link_telegram_account(
            session, f"student_{learner.auth_uuid}", 333444
        )
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
