import re
import uuid
from datetime import UTC, datetime

import httpx
from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from neoavlod.errors import DomainError
from neoavlod.models import Parent, Staff, Student, SystemSettings
from neoavlod.models.common import link_expiry
from neoavlod.security.secrets import decrypt_token, encrypt_token
from neoavlod.services.telegram import TelegramClient
from neoavlod.settings import Settings


async def get_bot_settings(session: AsyncSession) -> SystemSettings:
    settings = await session.get(SystemSettings, 1)
    if settings is None:
        settings = SystemSettings(id=1, version=0, active_version=0)
        session.add(settings)
        await session.commit()
    return settings


async def locked_bot_settings(session: AsyncSession) -> SystemSettings:
    # Serialize singleton creation, token changes and worker acknowledgements.
    await session.execute(text("SELECT pg_advisory_xact_lock(1313165109)"))
    settings = await session.scalar(
        select(SystemSettings)
        .where(SystemSettings.id == 1)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if settings is None:
        settings = SystemSettings(id=1, version=0, active_version=0, parameters={})
        session.add(settings)
        await session.flush()
    return settings


def worker_ready(settings: SystemSettings) -> bool:
    heartbeat = settings.parameters.get("bot_poll_heartbeat")
    if not isinstance(heartbeat, str) or settings.last_error:
        return False
    try:
        age = (datetime.now(UTC) - datetime.fromisoformat(heartbeat)).total_seconds()
    except (ValueError, TypeError):
        return False
    return (
        0 <= age < 90
        and settings.version == settings.active_version
        and (settings.parameters.get("bot_poll_version") == settings.version)
    )


async def reconnect_count(session: AsyncSession) -> int:
    return sum(
        [
            await session.scalar(
                select(func.count())
                .select_from(model)
                .where(model.telegram_reconnect_required.is_(True))
            )
            or 0
            for model in (Staff, Parent, Student)
        ]
    )


async def bot_identity(token: str, transport: httpx.AsyncBaseTransport | None) -> tuple[int, str]:
    try:
        result = (await TelegramClient(token, transport=transport).call("getMe", {})).get("result")
        if not isinstance(result, dict) or result.get("is_bot") is not True:
            raise DomainError("Telegram bot tokeni yaroqsiz", 422)
        bot_id = result.get("id")
        username = result.get("username")
        if (
            not isinstance(bot_id, int)
            or isinstance(bot_id, bool)
            or bot_id <= 0
            or not isinstance(username, str)
        ):
            raise DomainError("Telegram bot ma’lumotlari yaroqsiz", 422)
        return bot_id, normalize_bot_username(username)
    except DomainError as err:
        raise DomainError(f"Telegram getMe xatosi: {err.message}", 422) from None
    except Exception:
        raise DomainError("Telegram bot bilan bog‘lanib bo‘lmadi", 422) from None


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
    session: AsyncSession,
    username: str,
    *,
    changed_by: uuid.UUID | None = None,
    settings_config: Settings | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> SystemSettings:
    requested = normalize_bot_username(username)
    sys_settings = await locked_bot_settings(session)
    if not sys_settings.bot_token_encrypted:
        raise DomainError("Avval bot tokenini kiriting: bot nomi token orqali tekshiriladi", 422)
    bot_id, verified = await bot_identity(
        decrypt_token(sys_settings.bot_token_encrypted, settings_config or Settings()), transport
    )
    if requested.lower() != verified.lower():
        raise DomainError(
            "Username amaldagi token botiga mos emas. Boshqa bot uchun yangi token kiriting", 422
        )
    sys_settings.bot_username = verified
    sys_settings.parameters = {**sys_settings.parameters, "bot_id": bot_id}
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
    commit: bool = True,
) -> SystemSettings:
    clean_token = token.strip()
    if not clean_token or len(clean_token) > 256:
        raise DomainError("Yaroqsiz bot token formati", 422)

    bot_id, bot_username = await bot_identity(clean_token, transport)

    # 2. Encrypt token using Fernet secret key
    encrypted = encrypt_token(clean_token, settings_config)

    # 3. Update settings record atomically
    sys_settings = await locked_bot_settings(session)
    previous_id = sys_settings.parameters.get("bot_id")
    had_token = sys_settings.bot_token_encrypted is not None
    if had_token and previous_id is None:
        previous_token = decrypt_token(sys_settings.bot_token_encrypted or "", settings_config)
        if previous_token == clean_token:
            previous_id = bot_id
        else:
            try:
                previous_id, _ = await bot_identity(previous_token, transport)
            except DomainError:
                # Unknown/revoked old bot: require Start instead of guessing its identity.
                pass
    changed_bot = had_token and previous_id != bot_id
    if changed_bot:
        for model in (Staff, Parent, Student):
            await session.execute(
                update(model)
                .where(model.telegram_id.is_not(None))
                .values(
                    telegram_reconnect_required=True,
                    auth_uuid=func.gen_random_uuid(),
                    auth_expires_at=link_expiry(),
                    auth_used_at=None,
                )
            )
        sys_settings.last_update_id = 0
    sys_settings.parameters = {**sys_settings.parameters, "bot_id": bot_id}
    sys_settings.bot_token_encrypted = encrypted
    sys_settings.bot_username = bot_username
    sys_settings.version += 1
    sys_settings.last_error = None
    sys_settings.changed_by = changed_by

    if commit:
        await session.commit()
    else:
        await session.flush()
    return sys_settings


async def report_reload_status(
    session: AsyncSession,
    *,
    version: int,
    error: str | None = None,
) -> SystemSettings:
    sys_settings = await locked_bot_settings(session)
    if sys_settings.version != version:
        await session.commit()
        return sys_settings
    if error:
        sys_settings.last_error = error[:500]
    else:
        sys_settings.active_version = version
        sys_settings.last_error = None
    await session.commit()
    return sys_settings
