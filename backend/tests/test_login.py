import asyncio
import re
import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from factories import staff
from sqlalchemy import func, select

from neoavlod.database import Database
from neoavlod.errors import DomainError
from neoavlod.main import create_app
from neoavlod.models import AuthSession, OTPChallenge, OTPPurpose, Portal, Role
from neoavlod.models.common import Status
from neoavlod.security.passwords import hash_password
from neoavlod.security.secrets import decrypt_token, encrypt_token
from neoavlod.services.login import begin_login, confirm_login
from neoavlod.services.telegram import TelegramClient
from neoavlod.settings import Settings

pytestmark = pytest.mark.anyio
PASSWORD = "Correct-password-001"
ORIGIN = "https://admin.eduneo.uz"


class FakeSender:
    def __init__(self, fail: bool = False) -> None:
        self.messages: list[str] = []
        self.fail = fail

    async def send_message(self, telegram_id: int, message: str) -> None:
        if self.fail:
            raise DomainError("Telegram vaqtincha mavjud emas", 503)
        self.messages.append(message)

    @property
    def code(self) -> str:
        found = re.search(r"kodi: ([0-9]{6})", self.messages[-1])
        assert found is not None
        return found[1]


async def seed(database: Database, **values: object) -> str:
    values.setdefault("role", Role.ADMIN)
    person = staff(hashed_password=hash_password(PASSWORD), telegram_id=7654321, **values)
    async with database.session() as session:
        session.add(person)
        await session.commit()
    return person.username


async def begin(database: Database, username: str, sender: FakeSender) -> OTPChallenge:
    async with database.session() as session:
        return await begin_login(
            session, Settings(), sender, username, PASSWORD, Portal.ADMIN, "test"
        )


async def test_login_api_gives_no_session_before_otp_and_consumes_once(
    model_database: Database,
) -> None:
    username = await seed(model_database)
    sender = FakeSender()
    app = create_app()
    app.state.telegram_sender = sender
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url=ORIGIN, headers={"Origin": ORIGIN}
        ) as client,
    ):
        first = await client.post(
            "/api/v1/auth/admin/login", json={"username": username.upper(), "password": PASSWORD}
        )
        assert first.status_code == 200 and not client.cookies
        assert sender.code not in first.text and PASSWORD not in first.text
        body = {"challenge_id": first.json()["challenge_id"], "code": sender.code}
        async with model_database.session() as session:
            challenge = await session.get(OTPChallenge, uuid.UUID(body["challenge_id"]))
            assert (
                challenge
                and len(challenge.code_hash) == 64
                and sender.code not in challenge.code_hash
            )
            assert await session.scalar(select(func.count()).select_from(AuthSession)) == 0
        result = await client.post("/api/v1/auth/admin/login/confirm", json=body)
        assert result.status_code == 200
        assert "HttpOnly" in result.headers.get_list("set-cookie")[0]
        assert (await client.get("/api/v1/auth/admin/me")).status_code == 200
        assert (await client.post("/api/v1/auth/admin/login/confirm", json=body)).status_code == 401


@pytest.mark.parametrize(
    "values,expected", [({"status": Status.INACTIVE}, 401), ({"role": Role.TEACHER}, 403)]
)
async def test_inactive_or_wrong_portal_never_sends(
    model_database: Database, values: dict[str, object], expected: int
) -> None:
    username = await seed(model_database, **values)
    sender = FakeSender()
    with pytest.raises(DomainError) as error:
        await begin(model_database, username, sender)
    assert error.value.status_code == expected and not sender.messages


async def test_unlinked_or_wrong_password_never_sends(model_database: Database) -> None:
    from neoavlod.models import Staff

    username = await seed(model_database)
    sender = FakeSender()
    async with model_database.session() as session:
        for name in (username, "unknown_user"):
            with pytest.raises(DomainError, match="Username yoki parol"):
                await begin_login(session, Settings(), sender, name, "wrong", Portal.ADMIN, "test")
        person = await session.scalar(select(Staff).where(Staff.username == username))
        assert person
        person.telegram_id = None
        await session.commit()
    with pytest.raises(DomainError, match="ulanmagan"):
        await begin(model_database, username, sender)
    assert not sender.messages


async def test_wrong_code_attempts_are_durable_and_lock_after_five(
    model_database: Database,
) -> None:
    sender = FakeSender()
    challenge = await begin(model_database, await seed(model_database), sender)
    wrong = "000000" if sender.code != "000000" else "111111"
    for _ in range(5):
        with pytest.raises(DomainError):
            async with model_database.session() as session:
                await confirm_login(session, Settings(), challenge.id, wrong, Portal.ADMIN)
    with pytest.raises(DomainError):
        async with model_database.session() as session:
            await confirm_login(session, Settings(), challenge.id, sender.code, Portal.ADMIN)
    async with model_database.session() as session:
        saved = await session.get(OTPChallenge, challenge.id)
        assert saved and saved.attempts == 5
        assert await session.scalar(select(func.count()).select_from(AuthSession)) == 0


@pytest.mark.parametrize("mutation", ["expired", "purpose", "undelivered"])
async def test_expiry_purpose_and_delivery_gate(model_database: Database, mutation: str) -> None:
    sender = FakeSender()
    challenge = await begin(model_database, await seed(model_database), sender)
    async with model_database.session() as session:
        saved = await session.get(OTPChallenge, challenge.id)
        assert saved
        if mutation == "expired":
            saved.created_at = datetime.now(UTC) - timedelta(minutes=10)
            saved.expires_at = datetime.now(UTC) - timedelta(minutes=1)
        elif mutation == "purpose":
            saved.purpose = OTPPurpose.RESET
        else:
            saved.delivered_at = None
        await session.commit()
    with pytest.raises(DomainError):
        async with model_database.session() as session:
            await confirm_login(session, Settings(), challenge.id, sender.code, Portal.ADMIN)


async def test_replacement_invalidates_old_and_concurrent_confirmation_once(
    model_database: Database,
) -> None:
    sender = FakeSender()
    username = await seed(model_database)
    old = await begin(model_database, username, sender)
    old_code = sender.code
    latest = await begin(model_database, username, sender)
    with pytest.raises(DomainError):
        async with model_database.session() as session:
            await confirm_login(session, Settings(), old.id, old_code, Portal.ADMIN)

    async def confirm() -> bool:
        try:
            async with model_database.session() as session:
                await confirm_login(session, Settings(), latest.id, sender.code, Portal.ADMIN)
            return True
        except DomainError:
            return False

    assert sorted(await asyncio.gather(confirm(), confirm())) == [False, True]


async def test_rate_limit_survives_rejected_requests(model_database: Database) -> None:
    sender = FakeSender()
    for i in range(11):
        with pytest.raises(DomainError) as error:
            async with model_database.session() as session:
                await begin_login(
                    session, Settings(), sender, "absent", "bad", Portal.ADMIN, "test"
                )
        assert error.value.status_code == (429 if i == 10 else 401)


async def test_delivery_failure_leaves_no_valid_challenge(model_database: Database) -> None:
    with pytest.raises(DomainError) as error:
        await begin(model_database, await seed(model_database), FakeSender(fail=True))
    assert error.value.status_code == 503
    async with model_database.session() as session:
        challenge = await session.scalar(select(OTPChallenge))
        assert challenge and challenge.delivered_at is None


async def test_telegram_request_encryption_and_log_redaction(
    caplog: pytest.LogCaptureFixture,
) -> None:
    token = "123456:secret-telegram-token"
    settings = Settings()
    encrypted = encrypt_token(token, settings)
    assert token not in encrypted and decrypt_token(encrypted, settings) == token

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/sendMessage")
        assert b'"chat_id":123' in request.content
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})

    with caplog.at_level("INFO", logger="httpx"):
        await TelegramClient(token, httpx.MockTransport(handler)).send_message(123, "test message")
    assert token not in caplog.text and "[REDACTED]" in caplog.text


async def test_login_origin_rejected_without_sending(model_database: Database) -> None:
    app = create_app()
    sender = FakeSender()
    app.state.telegram_sender = sender
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=ORIGIN) as client,
    ):
        result = await client.post(
            "/api/v1/auth/admin/login", json={"username": "someone", "password": PASSWORD}
        )
        assert result.status_code == 403 and not sender.messages
