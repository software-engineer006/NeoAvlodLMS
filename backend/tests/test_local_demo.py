import uuid

import httpx
import pytest
from factories import staff
from pydantic import SecretStr
from sqlalchemy import select
from test_login import FakeSender

from neoavlod.database import Database
from neoavlod.local_demo import create_demo_app, seed_demo
from neoavlod.main import create_app
from neoavlod.models import Role, Staff
from neoavlod.security.passwords import validate_password
from neoavlod.services.otp_store import InMemoryOTPStore
from neoavlod.settings import Settings

pytestmark = pytest.mark.anyio


async def test_demo_seed_is_disabled_after_real_data_cutover() -> None:
    settings = Settings(
        database_url=SecretStr("postgresql+asyncpg://demo@demo-database/neoavlod_demo"),
        environment="development",
    )
    with pytest.raises(RuntimeError, match="seeding is disabled"):
        await seed_demo(settings)


async def test_demo_is_explicit_and_rejects_production() -> None:
    config = Settings()
    for settings in (
        config,
        config.model_copy(update={"environment": "production"}),
        config.model_copy(update={"environment": "test"}),
    ):
        with pytest.raises(RuntimeError, match="isolated"):
            create_demo_app(settings)
    with pytest.raises(ValueError):
        validate_password("1234")
    app = create_app(config)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app), base_url="http://test"
    ) as client:
        fake_id = uuid.uuid4()
        assert (await client.get(f"/api/v1/local-demo/admin/otp/{fake_id}")).status_code == 404
        assert (await client.get(f"/api/v1/local-demo/teacher/otp/{fake_id}")).status_code == 404
    await app.state.database.close()


@pytest.mark.parametrize(
    "portal,username,role",
    [
        ("admin", "superadmin", Role.SUPERADMIN),
        ("teacher", "teacher", Role.TEACHER),
    ],
)
async def test_demo_otp_login_with_telegram_and_unlinked_state(
    model_database: Database, portal: str, username: str, role: Role
) -> None:
    from argon2 import PasswordHasher

    config = Settings(
        database_url=SecretStr("postgresql+asyncpg://demo@demo-database/neoavlod_demo"),
        environment="development",
        admin_origin="http://localhost:3000",
        teacher_origin="http://127.0.0.1:3001",
    )
    otp_store = InMemoryOTPStore()
    app = create_demo_app(config)
    await app.state.database.close()
    app.state.database = model_database
    app.state.otp_store = otp_store

    sender = FakeSender()
    app.state.telegram_sender = sender

    # 1. Unlinked account test: user without telegram_id gets "telegram_not_linked"
    async with model_database.session() as session:
        session.add(
            staff(
                username=username,
                role=role,
                telegram_id=None,
                hashed_password=PasswordHasher().hash("1234"),
            )
        )
        await session.commit()

    origin = config.admin_origin if portal == "admin" else config.teacher_origin
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app), base_url=origin, headers={"Origin": origin}
    ) as client:
        # Wrong password rejected
        login_bad = await client.post(
            f"/api/v1/auth/{portal}/login",
            json={"username": username, "password": "wrong"},
        )
        assert login_bad.status_code == 401

        # Unlinked user gets telegram_not_linked error
        unlinked = await client.post(
            f"/api/v1/auth/{portal}/login",
            json={"username": username, "password": "1234"},
        )
        assert unlinked.status_code == 403
        assert unlinked.json().get("code") == "telegram_not_linked"
        assert "ulanmagan" in unlinked.json().get("detail", "")

        # 2. Link telegram_id and test full OTP login flow
        async with model_database.session() as session:
            person = await session.scalar(select(Staff).where(Staff.username == username))
            assert person
            person.telegram_id = 123456789
            await session.commit()

        login = await client.post(
            f"/api/v1/auth/{portal}/login",
            json={"username": username, "password": "1234"},
        )
        assert login.status_code == 200 and not client.cookies
        challenge = login.json()["challenge_id"]

        # Ensure obsolete local-demo OTP endpoint does not exist
        assert (await client.get(f"/api/v1/local-demo/{portal}/otp/{challenge}")).status_code == 404

        # Confirm using code delivered via Telegram
        code = sender.code
        confirmation = {"challenge_id": challenge, "code": code}
        result = await client.post(f"/api/v1/auth/{portal}/login/confirm", json=confirmation)
        assert result.status_code == 200 and result.json()["role"] == role

        other = "teacher" if portal == "admin" else "admin"
        assert (await client.get(f"/api/v1/auth/{portal}/me")).status_code == 200
        assert (await client.get(f"/api/v1/auth/{other}/me")).status_code == 403

        # Replay attack is rejected
        assert (
            await client.post(f"/api/v1/auth/{portal}/login/confirm", json=confirmation)
        ).status_code == 401
