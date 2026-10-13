"""Worker readiness based on recent successful polling, never an API socket check."""

import asyncio

from neoavlod.database import Database
from neoavlod.models import SystemSettings
from neoavlod.services.bot_settings import worker_ready
from neoavlod.settings import Settings


async def healthy() -> bool:
    db = Database(Settings())
    try:
        async with db.session() as session:
            config = await session.get(SystemSettings, 1)
            if not config or not config.bot_token_encrypted or config.last_error:
                return False
            return worker_ready(config)
    finally:
        await db.close()


if __name__ == "__main__":
    try:
        result = asyncio.run(healthy())
    except Exception:
        result = False
    raise SystemExit(0 if result else 1)
