"""Local portal factory. Demo seeding is disabled after the real-data cutover."""

from fastapi import FastAPI
from sqlalchemy.engine import make_url

from neoavlod.main import create_app
from neoavlod.settings import Settings


def ensure_local(settings: Settings) -> None:
    url = make_url(settings.database_url.get_secret_value())
    if settings.environment != "development" or url.database != "neoavlod_demo":
        raise RuntimeError("Local demo requires development and the isolated neoavlod_demo DB")


def create_demo_app(settings: Settings | None = None) -> FastAPI:
    config = settings or Settings()
    ensure_local(config)
    return create_app(config)


async def seed_demo(settings: Settings) -> None:
    ensure_local(settings)
    raise RuntimeError("Demo seeding is disabled; use the reviewed real-data import")


if __name__ == "__main__":
    raise SystemExit("Demo seeding is disabled; existing real records are preserved")
