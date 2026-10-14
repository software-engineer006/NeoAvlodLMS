"""Owner-only deployment step; never expose credentials or SQL in output."""

import asyncio
import re
from pathlib import Path
from urllib.parse import urlsplit

from sqlalchemy import text

from neoavlod.database import Database
from neoavlod.settings import Settings


async def provision() -> None:
    values = dict(
        line.split("=", 1)
        for line in Path("/production.env").read_text().splitlines()
        if "=" in line and not line.startswith("#")
    )
    database = Database(Settings())
    try:
        async with database.engine.begin() as connection:
            for key, role in (
                ("NEOAVLOD_APP_DATABASE_URL", "neoavlod_app"),
                ("NEOAVLOD_ARCHIVE_DATABASE_URL", "neoavlod_archiver"),
            ):
                url = urlsplit(values[key])
                password = url.password or ""
                if url.username != role or not re.fullmatch(r"[a-f0-9]{64}", password):
                    raise ValueError("Invalid restricted role configuration")
                await connection.execute(
                    text(f"ALTER ROLE {role} LOGIN PASSWORD '{password}'")
                )
    finally:
        await database.close()


if __name__ == "__main__":
    try:
        asyncio.run(provision())
    except Exception:
        raise SystemExit("Audit credential provisioning failed; secrets withheld") from None
    print("Restricted audit roles provisioned")
