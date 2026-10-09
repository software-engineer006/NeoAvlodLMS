"""Verify the encrypted configured bot against real Telegram without exposing secrets."""

import asyncio
import json
from pathlib import Path

from neoavlod.database import Database
from neoavlod.models import SystemSettings
from neoavlod.security.secrets import decrypt_token
from neoavlod.services.bot_worker import polling_lease
from neoavlod.services.telegram import TelegramClient
from neoavlod.settings import Settings
from neoavlod.worker_health import healthy


async def main() -> None:
    settings = Settings()
    db = Database(settings)
    try:
        async with db.session() as session:
            config = await session.get(SystemSettings, 1)
            assert config and config.bot_token_encrypted and config.bot_username
            token = decrypt_token(config.bot_token_encrypted, settings)
            result = (await TelegramClient(token).call("getMe", {})).get("result")
            assert isinstance(result, dict) and result.get("is_bot") is True
            assert result.get("username") == config.bot_username
            assert await healthy()
            async with polling_lease(db) as competing:
                assert competing is None, "Running worker must own the polling lock"
            heartbeat = str(config.parameters["bot_poll_heartbeat"])
            checkpoint = Path("/workspace/.private/real-data/worker-heartbeat.txt")
            if checkpoint.exists():
                assert heartbeat > checkpoint.read_text(), "Polling must advance after restart"
            checkpoint.write_text(heartbeat)
            checkpoint.chmod(0o600)
            print(json.dumps({"real_getMe": "verified", "bot_username": config.bot_username,
                              "version": config.version, "active_version": config.active_version,
                              "worker_error": bool(config.last_error),
                              "worker_health": "fresh real poll", "singleton": "owned"}))
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
