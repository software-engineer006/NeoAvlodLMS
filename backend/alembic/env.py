import asyncio
from logging.config import fileConfig

from sqlalchemy import Connection
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from alembic import context
from neoavlod import models  # noqa: F401 - register all model tables
from neoavlod.database import Base
from neoavlod.settings import Settings

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def run_offline() -> None:
    context.configure(
        url=Settings().database_url.get_secret_value(),
        target_metadata=Base.metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_sync(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=Base.metadata,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_online() -> None:
    engine = create_async_engine(
        Settings().database_url.get_secret_value(),
        poolclass=NullPool,
        hide_parameters=True,
    )
    try:
        async with engine.connect() as connection:
            await connection.run_sync(run_sync)
    finally:
        await engine.dispose()


if context.is_offline_mode():
    run_offline()
elif config.attributes.get("connection") is not None:
    run_sync(config.attributes["connection"])
else:
    asyncio.run(run_online())
