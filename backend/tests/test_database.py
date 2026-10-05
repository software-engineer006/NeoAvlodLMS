from collections.abc import AsyncIterator
from typing import cast

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy import text

from neoavlod.database import Base, Database
from neoavlod.main import create_app
from neoavlod.settings import Settings


@pytest.fixture
async def database(test_database: Database) -> AsyncIterator[Database]:
    async with test_database.engine.begin() as connection:
        await connection.execute(text("CREATE TABLE transaction_probe (value integer)"))
    try:
        yield test_database
    finally:
        async with test_database.engine.begin() as connection:
            await connection.execute(text("DROP TABLE transaction_probe"))


@pytest.mark.anyio
async def test_explicit_commit_persists_and_exception_rolls_back(database: Database) -> None:
    async with database.session() as session:
        await session.execute(text("INSERT INTO transaction_probe VALUES (1)"))
        await session.commit()
    with pytest.raises(RuntimeError):
        async with database.session() as session:
            await session.execute(text("INSERT INTO transaction_probe VALUES (2)"))
            raise RuntimeError("rollback")
    async with database.session() as session:
        result = await session.execute(text("SELECT value FROM transaction_probe"))
        assert result.scalars().all() == [1]


@pytest.mark.anyio
async def test_uncommitted_session_closes_without_persisting(database: Database) -> None:
    async with database.session() as session:
        await session.execute(text("INSERT INTO transaction_probe VALUES (3)"))
    async with database.session() as session:
        result = await session.execute(text("SELECT count(*) FROM transaction_probe"))
        assert result.scalar_one() == 0
    assert await database.is_ready()


@pytest.mark.anyio
async def test_readiness_checks_real_database_and_failure_returns_503(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_app(Settings(environment="test"))
    transport = httpx.ASGITransport(app=app)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            assert (await client.get("/api/v1/ready")).json() == {"status": "ready"}

            async def unavailable() -> bool:
                return False

            monkeypatch.setattr(app.state.database, "is_ready", unavailable)
            response = await client.get("/api/v1/ready")
            assert response.status_code == 503
            assert response.json() == {"status": "unavailable"}
            assert (await client.get("/api/v1/health")).status_code == 200


@pytest.mark.anyio
async def test_connection_failure_does_not_log_secrets(caplog: pytest.LogCaptureFixture) -> None:
    db = Database(
        Settings(
            database_url=SecretStr(
                "postgresql+asyncpg://hidden:private-password@127.0.0.1:9/missing"
            )
        )
    )
    try:
        assert not await db.is_ready()
        assert "private-password" not in caplog.text
        assert "Database readiness check failed" in caplog.text
    finally:
        await db.close()


def test_model_base_has_stable_constraint_names() -> None:
    assert Base.metadata.naming_convention["pk"] == "pk_%(table_name)s"


def test_database_url_validation_masks_input() -> None:
    with pytest.raises(ValueError) as error:
        Settings(database_url=SecretStr("sqlite://private-password"))
    assert "private-password" not in str(error.value)


@pytest.mark.anyio
async def test_lifespan_closes_pool_when_application_scope_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = create_app(Settings(environment="test"))
    db = cast(Database, app.state.database)
    close = db.close
    calls = 0

    async def tracked_close() -> None:
        nonlocal calls
        calls += 1
        await close()

    monkeypatch.setattr(db, "close", tracked_close)
    with pytest.raises(RuntimeError, match="scope failed"):
        async with app.router.lifespan_context(app):
            assert await db.is_ready()
            raise RuntimeError("scope failed")
    assert calls == 1
