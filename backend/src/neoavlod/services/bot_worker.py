"""Dynamic Telegram bot worker handling long polling, account linking and hot reload.

Telegram at-least-once va timeout eslatmasi:
Agar Telegram sendMessage API so‘rovi tarmoq uzilishi yoki timeout tufayli javobsiz
qolsa yoki xatolik bersa, tranzaksiya rollback qilinadi va xodimning shifrlangan
vaqtinchalik paroli o‘chirilmaydi (credential yo‘qolmaydi). Worker yoki foydalanuvchi
qayta urinishida xabar qayta jo‘natilishi mumkin. Biroq yetkazish Telegram tomonidan
muvaffaqiyatli qabul qilinishi bilan credential darhol tozalanadi (None qilinadi),
shuning uchun keyingi har qanday takroriy /start yoki so‘rovlarda parol qayta
oshkor qilinmaydi.
"""

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

import httpx
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from neoavlod.database import Database
from neoavlod.errors import DomainError
from neoavlod.models import Role, Staff, SystemSettings
from neoavlod.models.common import Status
from neoavlod.security.secrets import decrypt_token
from neoavlod.services.bot_settings import get_bot_settings, report_reload_status
from neoavlod.services.onboarding import link_telegram_account
from neoavlod.services.telegram import TelegramClient
from neoavlod.settings import Settings

logger = logging.getLogger(__name__)
POLLING_LOCK = 0x4E454F067


@asynccontextmanager
async def polling_lease(database: Database) -> AsyncIterator[AsyncConnection | None]:
    """Hold a dedicated PostgreSQL session lock; competing pollers never call Telegram."""
    async with database.engine.connect() as connection:
        acquired = await connection.scalar(
            text("SELECT pg_try_advisory_lock(:key)"), {"key": POLLING_LOCK}
        )
        await connection.commit()
        try:
            yield connection if acquired else None
        finally:
            if acquired:
                try:
                    await connection.execute(
                        text("SELECT pg_advisory_unlock(:key)"), {"key": POLLING_LOCK}
                    )
                    await connection.commit()
                except BaseException:
                    # Never return a session holding this lock to the pool.
                    await connection.invalidate()
                    raise


async def record_poll(
    session: AsyncSession,
    version: int,
    update_id: int | None = None,
) -> None:
    # A rejected /start rolls back and expires ORM state; reload before recording offset.
    config = await session.get(SystemSettings, 1, populate_existing=True)
    if config is None or config.version != version:
        return
    if update_id is not None:
        config.last_update_id = update_id
    config.parameters = {
        **config.parameters,
        "bot_poll_heartbeat": datetime.now(UTC).isoformat(),
        "bot_poll_version": version,
    }
    await session.commit()


WELCOME_MESSAGE = (
    "Assalomu alaykum! NeoAvlod LMS tizimiga xush kelibsiz.\n"
    "Hisobingizni bog‘lash uchun tizim orqali taqdim etilgan havolani bosing."
)


async def process_telegram_update(
    session: AsyncSession,
    client: TelegramClient,
    update: dict[str, object],
    settings: Settings | None = None,
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

    chat_type = chat.get("type")
    if chat_type and chat_type != "private":
        try:
            await client.send_message(chat_id, "Botdan faqat shaxsiy chatda foydalanish mumkin.")
        except Exception:
            pass
        return True

    text = message.get("text")
    if not isinstance(text, str):
        return False

    clean_text = text.strip()
    if clean_text.startswith("/start"):
        payload = clean_text[len("/start") :].strip()
        if payload:
            try:
                entity, reply = await link_telegram_account(
                    session, payload, chat_id, settings=settings
                )
                await client.send_message(chat_id, reply)

                # Confirmed delivery: wipe temporary credentials from DB
                if isinstance(entity, Staff) and entity.temporary_password_encrypted is not None:
                    entity.temporary_password_encrypted = None
                    entity.temporary_password_expires_at = None

                await session.commit()
            except DomainError as err:
                await session.rollback()
                reply = f"Xatolik: {err.message}"
                try:
                    await client.send_message(chat_id, reply)
                except Exception:
                    logger.exception("Failed to send error reply to %d", chat_id)
            except Exception:
                await session.rollback()
                logger.exception("Account linking unexpected failure or delivery failed")
        else:
            linked_staff = await session.scalar(select(Staff).where(Staff.telegram_id == chat_id))
            if linked_staff is not None:
                if linked_staff.status != Status.ACTIVE:
                    reply = "Hisobingiz faol emas. Iltimos, ma’muriyatga murojaat qiling."
                else:
                    if linked_staff.role == Role.TEACHER:
                        portal_url = (
                            settings.teacher_origin if settings else "https://teacher.eduneo.uz"
                        )
                        portal_name = "O‘qituvchi portali"
                    else:
                        portal_url = (
                            settings.admin_origin if settings else "https://admin.eduneo.uz"
                        )
                        portal_name = "Admin portali"

                    reply = (
                        f"Assalomu alaykum, {linked_staff.first_name} "
                        f"{linked_staff.last_name or ''}!\n"
                        f"(NeoAvlod LMS) Hisobingiz tizimga bog‘langan.\n\n"
                        f"{portal_name}: {portal_url}\n"
                        f"Login: {linked_staff.username}\n\n"
                        "Xavfsizlik maqsadida parollar botda saqlanmaydi va qayta ko‘rsatilmaydi.\n"
                        "Agar parolingizni unutgan bo‘lsangiz, login sahifasidagi "
                        "«Parolni unutdingizmi?» havolasi orqali yangi parol o‘rnatishingiz mumkin."
                    )
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
        async with polling_lease(self.database) as lease:
            if lease is None:
                return 0
            return await self._run_single_iteration_owned()

    async def _run_single_iteration_owned(self) -> int:
        async with self.database.session() as session:
            sys_settings = await get_bot_settings(session)
            if not sys_settings.bot_token_encrypted or sys_settings.version == 0:
                return 0

            token = decrypt_token(sys_settings.bot_token_encrypted, self.settings)
            version = sys_settings.version
            client = TelegramClient(token, transport=self.transport)

            offset = sys_settings.last_update_id + 1 if sys_settings.last_update_id > 0 else None
            try:
                updates = await client.get_updates(offset=offset, limit=50, timeout=0)
            except Exception as err:
                logger.warning("Error fetching updates in single iteration: %s", err)
                return 0

            processed = 0
            for update in updates:
                update_id = update.get("update_id")
                handled = await process_telegram_update(
                    session, client, update, settings=self.settings
                )
                if handled:
                    processed += 1
                if isinstance(update_id, int):
                    await record_poll(session, version, update_id)

            await record_poll(session, version)
            await report_reload_status(session, version=version)

            return processed

    async def _poll_session(
        self,
        client: TelegramClient,
        version: int,
        lease: AsyncConnection | None = None,
    ) -> None:
        """Poll updates continuously until stopped or until configuration version changes."""
        logger.info("Bot polling session started for version %d", version)
        try:
            await client.delete_webhook()
        except Exception:
            logger.debug("Webhook deletion skipped or failed")

        while not self._stop_event.is_set():
            if lease is not None:
                # Lost DB connection means lost ownership: stop before another poll.
                await lease.execute(text("SELECT 1"))
                await lease.commit()
            async with self.database.session() as session:
                current = await get_bot_settings(session)
                if current.version != version:
                    logger.info(
                        "Bot configuration updated (%d -> %d); closing old polling.",
                        version,
                        current.version,
                    )
                    break

                offset = current.last_update_id + 1 if current.last_update_id > 0 else None
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
                    await process_telegram_update(session, client, update, settings=self.settings)
                    if isinstance(update_id, int):
                        await record_poll(session, version, update_id)
                await record_poll(session, version)

    async def run_forever(self) -> None:
        """Wait for exclusive polling ownership, and reacquire it after a DB reconnect."""
        while not self.is_stopped:
            try:
                async with polling_lease(self.database) as lease:
                    if lease is not None:
                        await self._run_forever_owned(lease)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.warning("Bot polling lease lost; waiting to reacquire")
            if not self.is_stopped:
                await asyncio.sleep(self.idle_sleep)

    async def _run_forever_owned(self, lease: AsyncConnection) -> None:
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

                await self._poll_session(client, target_version, lease=lease)

            except asyncio.CancelledError:
                logger.info("Bot worker cancelled; exiting.")
                break
            except Exception as err:
                logger.exception("Error in bot worker outer loop: %s", err)
                # Connection errors require a fresh lease; never continue as stale owner.
                raise

        logger.info("Bot worker process terminated cleanly.")
