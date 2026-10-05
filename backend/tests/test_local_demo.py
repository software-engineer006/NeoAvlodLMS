import uuid

import httpx
import pytest
from factories import staff
from pydantic import SecretStr

from neoavlod.database import Database
from neoavlod.local_demo import DEMO_IDS, create_demo_app
from neoavlod.main import create_app
from neoavlod.models import Role
from neoavlod.security.passwords import validate_password
from neoavlod.settings import Settings

pytestmark = pytest.mark.anyio


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
        assert (await client.get(f"/api/v1/local-demo/admin/otp/{uuid.uuid4()}")).status_code == 404
    await app.state.database.close()


@pytest.mark.parametrize(
    "portal,username,role",
    [
        ("admin", "superadmin", Role.SUPERADMIN),
        ("teacher", "teacher", Role.TEACHER),
    ],
)
async def test_demo_otp_login_replay_and_portal_guards(
    model_database: Database, portal: str, username: str, role: Role
) -> None:
    from argon2 import PasswordHasher

    config = Settings(
        database_url=SecretStr("postgresql+asyncpg://demo@demo-database/neoavlod_demo"),
        environment="development",
        admin_origin="http://localhost:3000",
        teacher_origin="http://127.0.0.1:3001",
    )
    app = create_demo_app(config)
    await app.state.database.close()
    app.state.database = model_database
    async with model_database.session() as session:
        session.add(
            staff(
                username=username,
                role=role,
                telegram_id=DEMO_IDS[username],
                hashed_password=PasswordHasher().hash("1234"),
            )
        )
        await session.commit()
    origin = config.admin_origin if portal == "admin" else config.teacher_origin
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app), base_url=origin, headers={"Origin": origin}
    ) as client:
        login = await client.post(
            f"/api/v1/auth/{portal}/login",
            json={
                "username": username,
                "password": "wrong",
            },
        )
        assert login.status_code == 401
        login = await client.post(
            f"/api/v1/auth/{portal}/login",
            json={
                "username": username,
                "password": "1234",
            },
        )
        assert login.status_code == 200 and not client.cookies
        challenge = login.json()["challenge_id"]
        other = "teacher" if portal == "admin" else "admin"
        assert (await client.get(f"/api/v1/local-demo/{other}/otp/{challenge}")).status_code == 404
        code = await client.get(f"/api/v1/local-demo/{portal}/otp/{challenge}")
        assert code.status_code == 200 and code.headers["cache-control"] == "no-store"
        confirmation = {"challenge_id": challenge, "code": code.json()["code"]}
        result = await client.post(f"/api/v1/auth/{portal}/login/confirm", json=confirmation)
        assert result.status_code == 200 and result.json()["role"] == role
        assert (await client.get(f"/api/v1/auth/{portal}/me")).status_code == 200
        assert (await client.get(f"/api/v1/auth/{other}/me")).status_code == 403
        assert (await client.get(f"/api/v1/local-demo/{portal}/otp/{challenge}")).status_code == 404
        assert (
            await client.post(f"/api/v1/auth/{portal}/login/confirm", json=confirmation)
        ).status_code == 401
