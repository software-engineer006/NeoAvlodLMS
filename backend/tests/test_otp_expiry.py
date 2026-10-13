import uuid
from datetime import UTC, datetime, timedelta, tzinfo
from typing import Self

import httpx
import pytest
from test_login import PASSWORD, FakeSender, seed

from neoavlod.api import auth
from neoavlod.database import Database
from neoavlod.main import create_app
from neoavlod.models import Portal, Role
from neoavlod.services import login, otp_store
from neoavlod.services.otp_store import InMemoryOTPStore


@pytest.mark.anyio
@pytest.mark.parametrize("portal", [Portal.ADMIN, Portal.TEACHER])
@pytest.mark.parametrize("purpose", ["login", "password/reset"])
@pytest.mark.parametrize("elapsed,expected", [(179, True), (180, False)])
async def test_api_deadline_telegram_and_code_validity_at_three_minutes(
    model_database: Database,
    monkeypatch: pytest.MonkeyPatch,
    portal: Portal,
    purpose: str,
    elapsed: int,
    expected: bool,
) -> None:
    instant = datetime(2026, 10, 13, 12, tzinfo=UTC)

    class Clock(datetime):
        @classmethod
        def now(cls, tz: tzinfo | None = None) -> Self:
            return cls.fromtimestamp(instant.timestamp(), tz)

    for module in (auth, login, otp_store):
        monkeypatch.setattr(module, "datetime", Clock)
    username = await seed(
        model_database, role=Role.ADMIN if portal == Portal.ADMIN else Role.TEACHER
    )
    store = InMemoryOTPStore()
    sender = FakeSender()
    app = create_app(otp_store=store)
    app.state.telegram_sender = sender
    origin = f"https://{portal.value}.eduneo.uz"
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url=origin, headers={"Origin": origin}
        ) as client,
    ):
        path = f"/api/v1/auth/{portal.value}/{purpose}"
        request_body = {"username": username}
        if purpose == "login":
            request_body["password"] = PASSWORD
        response = await client.post(path, json=request_body)
        assert response.status_code == (200 if purpose == "login" else 202)
        assert datetime.fromisoformat(response.json()["expires_at"]) == instant + timedelta(
            seconds=180
        )
        challenge_id = uuid.UUID(response.json()["challenge_id"])
        assert store._challenges[challenge_id].expires_at == instant + timedelta(seconds=180)
        assert "Amal qilish muddati: 3 daqiqa." in sender.messages[-1]
        if purpose == "password/reset":
            unknown = await client.post(path, json={"username": "unknown_account"})
            assert unknown.status_code == 202
            assert unknown.json()["expires_at"] == response.json()["expires_at"]
        instant += timedelta(seconds=elapsed)
        body = {"challenge_id": str(challenge_id), "code": sender.code}
        if purpose == "password/reset":
            body["new_password"] = "New-password-expiry-123"
        confirmed = await client.post(path + "/confirm", json=body)
        assert confirmed.status_code == ((200 if purpose == "login" else 204) if expected else 401)
        assert (await client.post(path + "/confirm", json=body)).status_code == 401
