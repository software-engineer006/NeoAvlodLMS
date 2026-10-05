import os
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from pydantic import SecretStr
from sqlalchemy.engine import make_url

from neoavlod.database import Base, Database
from neoavlod.settings import Settings


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(autouse=True)
def isolate_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[None]:
    """Local developer .env and process variables must not affect tests."""
    monkeypatch.chdir(tmp_path)
    for key in ("NEOAVLOD_APP_NAME", "NEOAVLOD_ENVIRONMENT", "NEOAVLOD_DEBUG"):
        monkeypatch.delenv(key, raising=False)
    yield


@pytest.fixture
async def test_database() -> AsyncIterator[Database]:
    url = os.environ["TEST_DATABASE_URL"]
    parsed = make_url(url)
    if parsed.host != "test-database" or parsed.database != "neoavlod_test":
        raise RuntimeError("Integration tests require the isolated Compose test-database")
    db = Database(Settings(database_url=SecretStr(url), environment="test"))
    try:
        yield db
    finally:
        await db.close()


@pytest.fixture
async def model_database(test_database: Database) -> AsyncIterator[Database]:
    async with test_database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    try:
        yield test_database
    finally:
        async with test_database.engine.begin() as connection:
            await connection.run_sync(Base.metadata.drop_all)
