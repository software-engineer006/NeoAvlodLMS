import logging
import re
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from factories import staff
from sqlalchemy import select

from neoavlod.database import Database
from neoavlod.errors import DomainError
from neoavlod.models import OTPChallenge, OTPPurpose, Portal, Role, Staff
from neoavlod.security.passwords import hash_password
from neoavlod.services.login import (
    begin_login,
    confirm_login,
    deliver_challenge,
    verify_challenge,
)
from neoavlod.services.telegram import TelegramClient
from neoavlod.settings import Settings

pytestmark = pytest.mark.anyio
PASSWORD = "Password-otp-service-123"


class CapturingSender:
    def __init__(self, should_fail: bool = False) -> None:
        self.sent: list[str] = []
        self.should_fail = should_fail

    async def send_message(self, telegram_id: int, message: str) -> None:
        if self.should_fail:
            raise DomainError("Telegram xizmati vaqtincha mavjud emas", 503)
        self.sent.append(message)

    @property
    def latest_code(self) -> str:
        match = re.search(r"kodi: ([0-9]{6})", self.sent[-1])
        assert match is not None
        return match[1]


async def create_user(database: Database) -> Staff:
    person = staff(
        role=Role.ADMIN,
        hashed_password=hash_password(PASSWORD),
        telegram_id=555666777,
    )
    async with database.session() as session, session.begin():
        session.add(person)
    return person


async def test_otp_format_hash_storage_ttl_and_one_time_consume(
    model_database: Database,
) -> None:
    settings = Settings()
    person = await create_user(model_database)
    sender = CapturingSender()

    async with model_database.session() as session:
        challenge = await begin_login(
            session, settings, sender, person.username, PASSWORD, Portal.ADMIN, "127.0.0.1"
        )

    code = sender.latest_code
    assert re.fullmatch(r"[0-9]{6}", code) is not None

    async with model_database.session() as session:
        record = await session.get(OTPChallenge, challenge.id)
        assert record is not None
        assert record.code_hash != code
        assert len(record.code_hash) == 64
        assert record.purpose == OTPPurpose.LOGIN
        assert record.consumed_at is None
        assert record.delivered_at is not None
        assert record.expires_at > datetime.now(UTC)
        assert record.expires_at <= datetime.now(UTC) + timedelta(minutes=6)

    # First consumption succeeds
    async with model_database.session() as session:
        user, tokens = await confirm_login(
            session, settings, challenge.id, code, Portal.ADMIN
        )
        assert user.id == person.id
        assert tokens.access is not None

    # Check consumed_at in DB
    async with model_database.session() as session:
        record = await session.get(OTPChallenge, challenge.id)
        assert record is not None
        assert record.consumed_at is not None

    # Replay attack is rejected
    async with model_database.session() as session:
        with pytest.raises(DomainError, match="yaroqsiz yoki muddati tugagan"):
            await confirm_login(session, settings, challenge.id, code, Portal.ADMIN)


async def test_purpose_binding_prevents_cross_use(model_database: Database) -> None:
    settings = Settings()
    person = await create_user(model_database)
    sender = CapturingSender()

    # Generate Login challenge
    async with model_database.session() as session:
        login_ch = await begin_login(
            session, settings, sender, person.username, PASSWORD, Portal.ADMIN, "127.0.0.1"
        )
    login_code = sender.latest_code

    # Attempt to verify login challenge for RESET purpose -> rejected
    async with model_database.session() as session:
        with pytest.raises(DomainError, match="yaroqsiz yoki muddati tugagan"):
            await verify_challenge(
                session, settings, login_ch.id, login_code, Portal.ADMIN, OTPPurpose.RESET
            )

    # Generate Reset challenge
    async with model_database.session() as session:
        staff_member = await session.get(Staff, person.id)
        assert staff_member is not None
        reset_ch = await deliver_challenge(
            session, staff_member, Portal.ADMIN, OTPPurpose.RESET, settings, sender
        )
    reset_code = sender.latest_code

    # Attempt to verify reset challenge for LOGIN purpose -> rejected
    async with model_database.session() as session:
        with pytest.raises(DomainError, match="yaroqsiz yoki muddati tugagan"):
            await verify_challenge(
                session, settings, reset_ch.id, reset_code, Portal.ADMIN, OTPPurpose.LOGIN
            )


async def test_delivery_failure_prevents_session_creation(model_database: Database) -> None:
    settings = Settings()
    person = await create_user(model_database)
    failing_sender = CapturingSender(should_fail=True)

    # Delivery fails during begin_login
    with pytest.raises(DomainError, match="Telegram xizmati"):
        async with model_database.session() as session:
            await begin_login(
                session,
                settings,
                failing_sender,
                person.username,
                PASSWORD,
                Portal.ADMIN,
                "127.0.0.1",
            )

    # Any unconfirmed challenge without delivered_at cannot create session
    async with model_database.session() as session:
        undelivered = (
            await session.scalars(
                select(OTPChallenge).where(
                    OTPChallenge.staff_id == person.id,
                    OTPChallenge.delivered_at.is_(None),
                )
            )
        ).all()
        for ch in undelivered:
            with pytest.raises(DomainError, match="yaroqsiz yoki muddati tugagan"):
                await confirm_login(session, settings, ch.id, "123456", Portal.ADMIN)


async def test_telegram_client_retry_on_429_and_transient_failure() -> None:
    # 1. 429 retry success
    call_count_429 = 0

    def handler_429(request: httpx.Request) -> httpx.Response:
        nonlocal call_count_429
        call_count_429 += 1
        if call_count_429 == 1:
            return httpx.Response(
                429,
                json={"ok": False, "parameters": {"retry_after": 0.01}},
            )
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})

    client = TelegramClient("token_429", transport=httpx.MockTransport(handler_429))
    result = await client.call("sendMessage", {"chat_id": 1, "text": "test"})
    assert result["ok"] is True
    assert call_count_429 == 2

    # 2. 429 exhausted raises 429 DomainError
    def handler_always_429(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"ok": False, "parameters": {"retry_after": 0.01}})

    client_failing = TelegramClient(
        "token_fail", transport=httpx.MockTransport(handler_always_429)
    )
    with pytest.raises(DomainError) as exc_429:
        await client_failing.call("sendMessage", {"chat_id": 1, "text": "test"}, max_retries=1)
    assert exc_429.value.status_code == 429

    # 3. Timeout retry success
    timeout_count = 0

    def handler_timeout(request: httpx.Request) -> httpx.Response:
        nonlocal timeout_count
        timeout_count += 1
        if timeout_count == 1:
            raise httpx.ReadTimeout("Connection timed out")
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 2}})

    client_timeout = TelegramClient(
        "token_timeout", transport=httpx.MockTransport(handler_timeout)
    )
    res_timeout = await client_timeout.call("sendMessage", {"chat_id": 1, "text": "test"})
    assert res_timeout["ok"] is True
    assert timeout_count == 2


async def test_code_never_logged_during_delivery(
    model_database: Database,
    caplog: pytest.LogCaptureFixture,
) -> None:
    settings = Settings()
    person = await create_user(model_database)
    sender = CapturingSender()

    with caplog.at_level(logging.DEBUG):
        async with model_database.session() as session:
            await begin_login(
                session, settings, sender, person.username, PASSWORD, Portal.ADMIN, "127.0.0.1"
            )

    code = sender.latest_code
    assert len(code) == 6
    for record in caplog.records:
        assert code not in record.getMessage()
