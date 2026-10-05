"""Dynamic Telegram bot worker handling long polling, account linking and hot reload."""

import asyncio
import logging

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from neoavlod.database import Database
from neoavlod.errors import DomainError
from neoavlod.security.secrets import decrypt_token
from neoavlod.services.bot_settings import get_bot_settings, report_reload_status
from neoavlod.services.onboarding import link_telegram_account
from neoavlod.services.telegram import TelegramClient
from neoavlod.settings import Settings

logger = logging.getLogger(__name__)

WELCOME_MESSAGE = (
    "Assalomu alaykum! NeoAvlod LMS tizimiga xush kelibsiz.\n"
    "Hisobingizni bog‘lash uchun tizim orqali taqdim etilgan havolani bosing."
)


async def process_telegram_update(
    session: AsyncSession,
    client: TelegramClient,
    update: dict[str, object],
) -> bool:
    message = update.get("message")
    if not isinstance(message, dict):
        return False

    chat = message.get("chat")
    if not isinstance(chat, dict):
        return False
    chat_id = chat.get("id")
    if not isinstance(chat_id, int):
        return False

    text = message.get("text")
    if not isinstance(text, str):
        return False

    clean_text = text.strip()
    if clean_text.startswith("/start"):
        payload = clean_text[len("/start"):].strip()
        if payload:
            try:
                _, reply = await link_telegram_account(session, payload, chat_id)
                await session.commit()
            except DomainError as err:
                await session.rollback()
                reply = f"Xatolik: {err.message}"
            except Exception:
                await session.rollback()
                logger.exception("Account linking unexpected failure")
                reply = "Tizimda xatolik yuz berdi. Iltimos keyinroq qaytadan urinib ko‘ring."
        else:
            reply = WELCOME_MESSAGE

        try:
            await client.send_message(chat_id, reply)
        except Exception:
            logger.exception("Failed to send Telegram reply to %d", chat_id)
        return True

    # Default reply for other messages
    try:
        await client.send_message(chat_id, WELCOME_MESSAGE)
    except Exception:
        logger.exception("Failed to send welcome message to %d", chat_id)
    return True


class BotWorker:
    def __init__(
        self,
        database: Database,
        settings: Settings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        poll_timeout: int = 5,
        idle_sleep: float = 1.0,
    ) -> None:
        self.database = database
        self.settings = settings
        self.transport = transport
        self.poll_timeout = poll_timeout
        self.idle_sleep = idle_sleep
        self._stop_event = asyncio.Event()

    def stop(self) -> None:
        self._stop_event.set()

    @property
    def is_stopped(self) -> bool:
        return self._stop_event.is_set()

    async def run_single_iteration(self) -> int:
        """Run a single polling cycle. Useful for testing and step execution."""
        async with self.database.session() as session:
            sys_settings = await get_bot_settings(session)
            if not sys_settings.bot_token_encrypted or sys_settings.version == 0:
                return 0

            token = decrypt_token(sys_settings.bot_token_encrypted, self.settings)
            client = TelegramClient(token, transport=self.transport)

            offset = (
                sys_settings.last_update_id + 1 if sys_settings.last_update_id > 0 else None
            )
            try:
                updates = await client.get_updates(offset=offset, limit=50, timeout=0)
            except Exception as err:
                logger.warning("Error fetching updates in single iteration: %s", err)
                return 0

            processed = 0
            for update in updates:
                update_id = update.get("update_id")
                handled = await process_telegram_update(session, client, update)
                if handled:
                    processed += 1
                if isinstance(update_id, int):
                    sys_settings.last_update_id = update_id
                    await session.commit()

            if sys_settings.active_version != sys_settings.version:
                await report_reload_status(session, version=sys_settings.version)

            return processed

    async def _poll_session(
        self,
        client: TelegramClient,
        version: int,
    ) -> None:
        """Poll updates continuously until stopped or until configuration version changes."""
        logger.info("Bot polling session started for version %d", version)
        try:
            await client.delete_webhook()
        except Exception:
            logger.debug("Webhook deletion skipped or failed")

        while not self._stop_event.is_set():
            async with self.database.session() as session:
                current = await get_bot_settings(session)
                if current.version != version:
                    logger.info(
                        "Bot configuration updated (%d -> %d); closing old polling.",
                        version,
                        current.version,
                    )
                    break

                offset = (
                    current.last_update_id + 1 if current.last_update_id > 0 else None
                )
                try:
                    updates = await client.get_updates(
                        offset=offset, limit=50, timeout=self.poll_timeout
                    )
                except (httpx.HTTPError, DomainError) as err:
                    logger.warning("Telegram polling error: %s", err)
                    await asyncio.sleep(0.5)
                    continue
                except asyncio.CancelledError:
                    raise
                except Exception as err:
                    logger.exception("Unexpected error in bot polling: %s", err)
                    await asyncio.sleep(0.5)
                    continue

                for update in updates:
                    if self._stop_event.is_set():
                        break
                    update_id = update.get("update_id")
                    await process_telegram_update(session, client, update)
                    if isinstance(update_id, int):
                        current.last_update_id = update_id
                        await session.commit()

    async def run_forever(self) -> None:
        """Main lifecycle loop: loads config, starts polling, reloads on config change."""
        logger.info("Bot worker process started")
        while not self._stop_event.is_set():
            try:
                async with self.database.session() as session:
                    sys_settings = await get_bot_settings(session)
                    if not sys_settings.bot_token_encrypted or sys_settings.version == 0:
                        await asyncio.sleep(self.idle_sleep)
                        continue

                    try:
                        token = decrypt_token(sys_settings.bot_token_encrypted, self.settings)
                    except Exception as err:
                        logger.error("Failed to decrypt bot token: %s", err)
                        await report_reload_status(
                            session, version=sys_settings.version, error=str(err)
                        )
                        await asyncio.sleep(self.idle_sleep)
                        continue

                    target_version = sys_settings.version
                    client = TelegramClient(token, transport=self.transport)
                    await report_reload_status(session, version=target_version)

                await self._poll_session(client, target_version)

            except asyncio.CancelledError:
                logger.info("Bot worker cancelled; exiting.")
                break
            except Exception as err:
                logger.exception("Error in bot worker outer loop: %s", err)
                await asyncio.sleep(self.idle_sleep)

        logger.info("Bot worker process terminated cleanly.")
