"""Read-only real getMe check; never polls, sends messages or changes settings."""

import asyncio
import json

from sqlalchemy import text

from neoavlod.database import Database
from neoavlod.models import SystemSettings
from neoavlod.security.secrets import decrypt_token
from neoavlod.services.bot_settings import bot_identity, worker_ready
from neoavlod.settings import Settings


async def main() -> None:
    settings = Settings()
    database = Database(settings)
    try:
        async with database.session() as session:
            await session.execute(text("SET TRANSACTION READ ONLY"))
            config = await session.get(SystemSettings, 1)
            assert config and config.bot_token_encrypted and config.bot_username
            bot_id, username = await bot_identity(
                decrypt_token(config.bot_token_encrypted, settings), None
            )
            assert username == config.bot_username, "Stored username differs from real getMe"
            known_id = config.parameters.get("bot_id")
            assert known_id is None or known_id == bot_id
            print(
                json.dumps(
                    {
                        "real_getMe": "verified",
                        "bot_username": username,
                        "identity_known": known_id is not None,
                        "configured_version": config.version,
                        "worker_ready": worker_ready(config),
                        "read_only": True,
                        "messages_sent": 0,
                    }
                )
            )
    finally:
        await database.close()


if __name__ == "__main__":
    asyncio.run(main())
