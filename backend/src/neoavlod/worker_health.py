"""Worker readiness based on recent successful polling, never an API socket check."""

import asyncio
from datetime import UTC, datetime

from neoavlod.database import Database
from neoavlod.models import SystemSettings
from neoavlod.settings import Settings


async def healthy() -> bool:
    db = Database(Settings())
    try:
        async with db.session() as session:
            config = await session.get(SystemSettings, 1)
            if not config or not config.bot_token_encrypted or config.last_error:
                return False
            heartbeat = config.parameters.get("bot_poll_heartbeat")
            if not isinstance(heartbeat, str):
                return False
            age = (datetime.now(UTC) - datetime.fromisoformat(heartbeat)).total_seconds()
            return (
                0 <= age < 90
                and config.version == config.active_version
                and config.parameters.get("bot_poll_version") == config.version
            )
    finally:
        await db.close()


if __name__ == "__main__":
    try:
        result = asyncio.run(healthy())
    except Exception:
        result = False
    raise SystemExit(0 if result else 1)
