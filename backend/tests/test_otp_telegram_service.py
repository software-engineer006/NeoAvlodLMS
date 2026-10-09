import logging
import os
import re
import uuid

import httpx
import pytest
from factories import staff

from neoavlod.database import Database
from neoavlod.errors import DomainError
from neoavlod.models import OTPPurpose, Portal, Role, Staff
from neoavlod.security.passwords import hash_password
from neoavlod.services.login import (
    begin_login,
    code_hash,
    confirm_login,
    deliver_challenge,
    verify_challenge,
)
from neoavlod.services.otp_store import InMemoryOTPStore, OTPVerdict, RedisOTPStore
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
    store = InMemoryOTPStore()

    async with model_database.session() as session:
        challenge = await begin_login(
            session, settings, sender, store, person.username, PASSWORD, Portal.ADMIN, "127.0.0.1"
        )

    code = sender.latest_code
    assert re.fullmatch(r"[0-9]{6}", code) is not None

    stored = store._challenges.get(challenge.id)
    assert stored is not None
    assert stored.code_hash != code
    assert len(stored.code_hash) == 64
    assert stored.purpose == OTPPurpose.LOGIN
    assert stored.staff_id == person.id

    # First consumption succeeds
    async with model_database.session() as session:
        user, tokens = await confirm_login(
            session, settings, store, challenge.id, code, Portal.ADMIN
        )
        assert user.id == person.id
        assert tokens.access is not None

    # Challenge is removed after consumption (one-time consume)
    assert challenge.id not in store._challenges

    # Replay attack is rejected
    async with model_database.session() as session:
        with pytest.raises(DomainError, match="yaroqsiz yoki muddati tugagan"):
            await confirm_login(session, settings, store, challenge.id, code, Portal.ADMIN)


async def test_purpose_binding_prevents_cross_use(model_database: Database) -> None:
    settings = Settings()
    person = await create_user(model_database)
    sender = CapturingSender()
    store = InMemoryOTPStore()

    # Generate Login challenge
    async with model_database.session() as session:
        login_ch = await begin_login(
            session, settings, sender, store, person.username, PASSWORD, Portal.ADMIN, "127.0.0.1"
        )
    login_code = sender.latest_code

    # Attempt to verify login challenge for RESET purpose -> rejected
    async with model_database.session() as session:
        with pytest.raises(DomainError, match="yaroqsiz yoki muddati tugagan"):
            await verify_challenge(
                session, settings, store, login_ch.id, login_code, Portal.ADMIN, OTPPurpose.RESET
            )

    # Generate Reset challenge
    async with model_database.session() as session:
        staff_member = await session.get(Staff, person.id)
        assert staff_member is not None
        reset_ch = await deliver_challenge(
            session, staff_member, Portal.ADMIN, OTPPurpose.RESET, settings, sender, store
        )
    reset_code = sender.latest_code

    # Attempt to verify reset challenge for LOGIN purpose -> rejected
    async with model_database.session() as session:
        with pytest.raises(DomainError, match="yaroqsiz yoki muddati tugagan"):
            await verify_challenge(
                session, settings, store, reset_ch.id, reset_code, Portal.ADMIN, OTPPurpose.LOGIN
            )


async def test_delivery_failure_prevents_session_creation(model_database: Database) -> None:
    settings = Settings()
    person = await create_user(model_database)
    failing_sender = CapturingSender(should_fail=True)
    store = InMemoryOTPStore()

    # Delivery fails during begin_login
    with pytest.raises(DomainError, match="Telegram xizmati"):
        async with model_database.session() as session:
            await begin_login(
                session,
                settings,
                failing_sender,
                store,
                person.username,
                PASSWORD,
                Portal.ADMIN,
                "127.0.0.1",
            )

    # Discarded immediately on delivery failure
    assert not store._challenges


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

    store = InMemoryOTPStore()
    with caplog.at_level(logging.DEBUG):
        async with model_database.session() as session:
            await begin_login(
                session,
                settings,
                sender,
                store,
                person.username,
                PASSWORD,
                Portal.ADMIN,
                "127.0.0.1",
            )

    code = sender.latest_code
    assert len(code) == 6
    for record in caplog.records:
        assert code not in record.getMessage()


async def test_redis_otp_store_live_operations() -> None:
    redis_url = os.environ.get("TEST_REDIS_URL")
    if not redis_url:
        pytest.skip("TEST_REDIS_URL not configured")
    store = RedisOTPStore.from_url(redis_url)
    try:
        challenge_id = uuid.uuid4()
        staff_id = uuid.uuid4()
        portal = Portal.ADMIN
        purpose = OTPPurpose.LOGIN
        code = "123456"
        settings = Settings()
        c_hash = code_hash(settings, challenge_id, purpose, code)

        # 1. Put challenge
        await store.put(
            challenge_id=challenge_id,
            staff_id=staff_id,
            portal=portal,
            purpose=purpose,
            code_hash=c_hash,
            ttl_seconds=300,
        )

        # 2. Wrong code -> mismatch
        wrong_hash = code_hash(settings, challenge_id, purpose, "999999")
        v = await store.verify(
            challenge_id=challenge_id, portal=portal, purpose=purpose, code_hash=wrong_hash
        )
        assert v.verdict is OTPVerdict.MISMATCH

        # 3. Correct code -> OK and consumed atomically
        v_ok = await store.verify(
            challenge_id=challenge_id, portal=portal, purpose=purpose, code_hash=c_hash
        )
        assert v_ok.verdict is OTPVerdict.OK
        assert v_ok.staff_id == staff_id

        # 4. Second attempt -> missing
        v_replay = await store.verify(
            challenge_id=challenge_id, portal=portal, purpose=purpose, code_hash=c_hash
        )
        assert v_replay.verdict is OTPVerdict.MISSING
    finally:
        await store.close()
