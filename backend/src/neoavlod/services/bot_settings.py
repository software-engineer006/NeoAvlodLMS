import re
import uuid

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from neoavlod.errors import DomainError
from neoavlod.models import SystemSettings
from neoavlod.security.secrets import encrypt_token
from neoavlod.services.telegram import TelegramClient
from neoavlod.settings import Settings


async def get_bot_settings(session: AsyncSession) -> SystemSettings:
    settings = await session.get(SystemSettings, 1)
    if settings is None:
        settings = SystemSettings(id=1, version=0, active_version=0)
        session.add(settings)
        await session.commit()
    return settings


_USERNAME_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9_]{4,31}")


def normalize_bot_username(raw: str) -> str:
    """Accept `name`, `@name` or `https://t.me/name`; Telegram bot names end in `bot`."""
    value = raw.strip()
    for prefix in ("https://t.me/", "http://t.me/", "t.me/"):
        if value.lower().startswith(prefix):
            value = value[len(prefix) :]
            break
    value = value.removeprefix("@").strip()
    if _USERNAME_PATTERN.fullmatch(value) is None or not value.lower().endswith("bot"):
        raise DomainError(
            "Bot username noto‘g‘ri: 5–32 ta lotin harf, raqam yoki _ bo‘lib, "
            "'bot' bilan tugashi kerak",
            422,
        )
    return value


async def set_bot_username(
    session: AsyncSession, username: str, *, changed_by: uuid.UUID | None = None
) -> SystemSettings:
    """Store the username used for staff/parent/student deep links.

    The token and the polling worker are untouched, so no reload is requested.
    """
    sys_settings = await get_bot_settings(session)
    sys_settings.bot_username = normalize_bot_username(username)
    sys_settings.changed_by = changed_by
    await session.commit()
    return sys_settings


async def update_bot_token(
    session: AsyncSession,
    settings_config: Settings,
    token: str,
    *,
    changed_by: uuid.UUID | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> SystemSettings:
    clean_token = token.strip()
    if not clean_token or len(clean_token) > 256:
        raise DomainError("Yaroqsiz bot token formati", 422)

    # 1. Validate token with getMe
    client = TelegramClient(clean_token, transport=transport)
    try:
        data = await client.call("getMe", {})
        result = data.get("result")
        if not isinstance(result, dict) or not result.get("username"):
            raise DomainError("Telegram bot tokeni yaroqsiz", 422)
        bot_username = str(result["username"])
    except DomainError as err:
        raise DomainError(f"Telegram getMe xatosi: {err.message}", 422) from None
    except Exception:
        raise DomainError("Telegram bot bilan bog‘lanib bo‘lmadi", 422) from None

    # 2. Encrypt token using Fernet secret key
    encrypted = encrypt_token(clean_token, settings_config)

    # 3. Update settings record atomically
    sys_settings = await get_bot_settings(session)
    sys_settings.bot_token_encrypted = encrypted
    sys_settings.bot_username = bot_username
    sys_settings.version += 1
    sys_settings.last_error = None
    sys_settings.changed_by = changed_by

    await session.commit()
    return sys_settings


async def report_reload_status(
    session: AsyncSession,
    *,
    version: int,
    error: str | None = None,
) -> SystemSettings:
    sys_settings = await get_bot_settings(session)
    if error:
        sys_settings.last_error = error[:500]
    else:
        sys_settings.active_version = version
        sys_settings.last_error = None
    await session.commit()
    return sys_settings
