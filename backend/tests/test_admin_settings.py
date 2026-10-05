import io
import json
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import anyio
import httpx
import pytest
from sqlalchemy import select
from test_rbac import Actor, actor

from neoavlod.cli import main as cli_main
from neoavlod.database import Database
from neoavlod.main import create_app
from neoavlod.models import Role, SystemSettings
from neoavlod.security.secrets import decrypt_token
from neoavlod.security.sessions import ACCESS_COOKIE, CSRF_COOKIE
from neoavlod.services.telegram import TelegramClient
from neoavlod.settings import Settings

pytestmark = pytest.mark.anyio
BASE = "/api/v1/admin/settings/bot"


def make_telegram_mock(valid_token: str = "valid_token_123") -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "getMe" in url:
            if valid_token in url:
                return httpx.Response(
                    200,
                    json={
                        "ok": True,
                        "result": {
                            "id": 987654321,
                            "is_bot": True,
                            "first_name": "EduNeo",
                            "username": "eduneo_bot",
                        },
                    },
                )
            return httpx.Response(
                401,
                json={"ok": False, "error_code": 401, "description": "Unauthorized"},
            )
        return httpx.Response(404, json={"ok": False})

    return httpx.MockTransport(handler)


@asynccontextmanager
async def client_for_settings(
    who: Actor,
    transport: httpx.AsyncBaseTransport | None = None,
) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app()
    if transport is not None:
        app.state.telegram_transport = transport
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url=who.origin,
            headers={"Origin": who.origin, "X-CSRF-Token": who.tokens.csrf},
        ) as client,
    ):
        client.cookies.set(ACCESS_COOKIE, who.tokens.access)
        client.cookies.set(CSRF_COOKIE, who.tokens.csrf)
        yield client


async def superadmin_actor(database: Database) -> Actor:
    return await actor(database, role=Role.SUPERADMIN)


async def test_only_superadmin_can_access_bot_settings(model_database: Database) -> None:
    admin = await actor(model_database, role=Role.ADMIN, permissions=["staff:manage"])
    teacher = await actor(model_database, role=Role.TEACHER)

    for person in (admin, teacher):
        async with client_for_settings(person) as client:
            res_get = await client.get(BASE)
            assert res_get.status_code == 403
            res_post = await client.post(BASE, json={"token": "test_token"})
            assert res_post.status_code == 403
            res_reload = await client.post(f"{BASE}/reload-status", json={"version": 1})
            assert res_reload.status_code == 403


async def test_get_bot_settings_initial_state(model_database: Database) -> None:
    who = await superadmin_actor(model_database)
    async with client_for_settings(who) as client:
        res = await client.get(BASE)
        assert res.status_code == 200
        data = res.json()
        assert data["configured"] is False
        assert data["bot_username"] is None
        assert data["version"] == 0
        assert data["active_version"] == 0
        assert data["last_error"] is None
        assert data["reload_in_progress"] is False


async def test_update_bot_token_success_and_encryption(model_database: Database) -> None:
    token = "valid_token_123"
    transport = make_telegram_mock(valid_token=token)
    who = await superadmin_actor(model_database)

    async with client_for_settings(who, transport=transport) as client:
        res = await client.post(BASE, json={"token": token})
        assert res.status_code == 200
        data = res.json()
        assert data["configured"] is True
        assert data["bot_username"] == "eduneo_bot"
        assert data["version"] == 1
        assert data["active_version"] == 0
        assert data["last_error"] is None
        assert data["reload_in_progress"] is True
        assert token not in res.text

    # Verify directly in database
    settings = Settings()
    async with model_database.session() as session:
        record = await session.get(SystemSettings, 1)
        assert record is not None
        assert record.bot_token_encrypted is not None
        assert record.bot_token_encrypted != token
        assert decrypt_token(record.bot_token_encrypted, settings) == token
        assert record.bot_username == "eduneo_bot"
        assert record.version == 1
        assert record.changed_by == who.staff_id


async def test_update_bot_token_rejection_on_telegram_error(model_database: Database) -> None:
    transport = make_telegram_mock(valid_token="known_token")
    who = await superadmin_actor(model_database)

    async with client_for_settings(who, transport=transport) as client:
        res = await client.post(BASE, json={"token": "wrong_unauthorized_token"})
        assert res.status_code == 422
        assert "xatosi" in res.json()["detail"] or "yaroqsiz" in res.json()["detail"]

    # Verify database unchanged
    async with model_database.session() as session:
        record = await session.get(SystemSettings, 1)
        if record is not None:
            assert record.version == 0
            assert record.bot_token_encrypted is None


async def test_update_bot_token_validation_error(model_database: Database) -> None:
    who = await superadmin_actor(model_database)
    async with client_for_settings(who) as client:
        res = await client.post(BASE, json={"token": "   "})
        assert res.status_code == 422


async def test_report_reload_status(model_database: Database) -> None:
    who = await superadmin_actor(model_database)
    transport = make_telegram_mock("valid_token_123")

    async with client_for_settings(who, transport=transport) as client:
        # First set token to advance version to 1
        await client.post(BASE, json={"token": "valid_token_123"})

        # Report reload success for version 1
        res = await client.post(f"{BASE}/reload-status", json={"version": 1})
        assert res.status_code == 200
        data = res.json()
        assert data["active_version"] == 1
        assert data["reload_in_progress"] is False
        assert data["last_error"] is None

        # Report reload failure
        res_fail = await client.post(
            f"{BASE}/reload-status",
            json={"version": 1, "error": "Connection timed out"},
        )
        assert res_fail.status_code == 200
        fail_data = res_fail.json()
        assert fail_data["active_version"] == 1
        assert fail_data["last_error"] == "Connection timed out"


async def test_cli_reads_token_from_stdin_without_echo(
    model_database: Database,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = "cli_secret_bot_token_456"

    async def mock_call(
        self: TelegramClient, method: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        if method == "getMe":
            return {
                "ok": True,
                "result": {
                    "id": 11223344,
                    "is_bot": True,
                    "first_name": "EduNeo CLI",
                    "username": "eduneo_cli_bot",
                },
            }
        return {"ok": True}

    monkeypatch.setattr(TelegramClient, "call", mock_call)
    monkeypatch.setattr(sys, "argv", ["neoavlod", "set-bot-token", "--token-stdin"])
    monkeypatch.setattr(sys, "stdin", io.StringIO(f"{token}\n"))

    captured_out = io.StringIO()
    captured_err = io.StringIO()
    monkeypatch.setattr(sys, "stdout", captured_out)
    monkeypatch.setattr(sys, "stderr", captured_err)

    code = await anyio.to_thread.run_sync(cli_main)
    stderr = captured_err.getvalue()
    stdout = captured_out.getvalue()
    assert code == 0, f"CLI error: {stderr}"

    assert token not in stdout
    assert token not in stderr
    payload = json.loads(stdout)
    assert payload["configured"] is True
    assert payload["bot_username"] == "eduneo_cli_bot"
    assert payload["version"] >= 1

    settings = Settings()
    async with model_database.session() as session:
        records = (await session.scalars(select(SystemSettings))).all()
        assert len(records) == 1
        assert records[0].bot_token_encrypted is not None
        assert decrypt_token(records[0].bot_token_encrypted, settings) == token
