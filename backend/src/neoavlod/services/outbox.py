"""Notification outbox worker.

Dispatches attendance notifications to parents with retry and lease recovery.
"""

import asyncio
import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from neoavlod.database import Database
from neoavlod.models import NotificationOutbox, OutboxStatus, Parent
from neoavlod.services.telegram import DatabaseTelegramSender, TelegramSender
from neoavlod.settings import Settings

logger = logging.getLogger(__name__)


def format_attendance_message(payload: dict[str, Any]) -> str:
    student = payload.get("student_name", "Talaba")
    group = payload.get("group_name", "Guruh")
    date_val = payload.get("date", "")
    status_label = payload.get("status_label", "")
    note = payload.get("note")

    lines = [
        "📋 Davomat bildirishnomasi",
        f"Farzandingiz: {student}",
        f"Guruh: {group}",
        f"Sana: {date_val}",
        f"Holati: {status_label}",
    ]
    if note:
        lines.append(f"Izoh: {note}")
    return "\n".join(lines)


async def claim_pending_outbox_items(
    session: AsyncSession,
    worker_id: uuid.UUID,
    limit: int = 50,
    lock_timeout_seconds: int = 30,
) -> list[NotificationOutbox]:
    now = datetime.now(UTC)
    stmt = (
        select(NotificationOutbox)
        .where(
            or_(
                and_(
                    NotificationOutbox.status == OutboxStatus.PENDING,
                    NotificationOutbox.available_at <= now,
                ),
                and_(
                    NotificationOutbox.status == OutboxStatus.PROCESSING,
                    NotificationOutbox.locked_until.is_not(None),
                    NotificationOutbox.locked_until <= now,
                ),
            )
        )
        .order_by(NotificationOutbox.available_at)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    items = list((await session.scalars(stmt)).all())
    lock_until = now + timedelta(seconds=lock_timeout_seconds)
    for item in items:
        item.status = OutboxStatus.PROCESSING
        item.locked_by = worker_id
        item.locked_until = lock_until
        item.attempts += 1
    await session.commit()
    return items


async def process_outbox_item(
    session: AsyncSession,
    item: NotificationOutbox,
    sender: TelegramSender,
    *,
    max_attempts: int = 5,
) -> bool:
    item_in_session = await session.get(NotificationOutbox, item.id)
    if item_in_session is None:
        return False
    item = item_in_session

    # Check if parent is connected to Telegram
    telegram_id = item.telegram_id
    if telegram_id is None:
        parent = await session.get(Parent, item.parent_id)
        if parent is not None and parent.telegram_id is not None:
            telegram_id = parent.telegram_id
            item.telegram_id = telegram_id
        else:
            # Parent not linked to Telegram yet -> skip
            item.status = OutboxStatus.SKIPPED
            item.locked_by = None
            item.locked_until = None
            await session.commit()
            return False

    message = format_attendance_message(item.payload)
    try:
        await sender.send_message(telegram_id, message)
        item.status = OutboxStatus.DELIVERED
        item.delivered_at = datetime.now(UTC)
        item.locked_by = None
        item.locked_until = None
        item.last_error = None
        await session.commit()
        return True
    except Exception as err:
        now = datetime.now(UTC)
        logger.warning(
            "Failed delivering outbox item %s (attempt %d): %s",
            item.id,
            item.attempts,
            err,
        )
        if item.attempts >= max_attempts:
            item.status = OutboxStatus.FAILED
        else:
            item.status = OutboxStatus.PENDING
            backoff = min(2 ** item.attempts * 2, 300)
            item.available_at = now + timedelta(seconds=backoff)

        item.locked_by = None
        item.locked_until = None
        item.last_error = str(err)[:500]
        await session.commit()
        return False


async def dispatch_pending_outbox(
    database: Database,
    sender: TelegramSender | None = None,
    *,
    worker_id: uuid.UUID | None = None,
    batch_size: int = 50,
    lock_timeout_seconds: int = 30,
    max_attempts: int = 5,
    transport: httpx.AsyncBaseTransport | None = None,
) -> int:
    wid = worker_id or uuid.uuid4()
    delivered_count = 0
    settings = Settings()

    async with database.session() as session:
        items = await claim_pending_outbox_items(
            session, wid, limit=batch_size, lock_timeout_seconds=lock_timeout_seconds
        )
        item_ids = [it.id for it in items]

    if not item_ids:
        return 0

    for item_id in item_ids:
        async with database.session() as session:
            item = await session.get(NotificationOutbox, item_id)
            if item is None:
                continue
            active_sender = sender or DatabaseTelegramSender(
                session, settings, transport=transport
            )
            try:
                success = await process_outbox_item(
                    session, item, active_sender, max_attempts=max_attempts
                )
                if success:
                    delivered_count += 1
            except Exception as err:
                logger.exception("Error processing outbox item %s: %s", item.id, err)

    return delivered_count


class OutboxWorker:
    def __init__(
        self,
        database: Database,
        settings: Settings,
        *,
        sender: TelegramSender | None = None,
        poll_interval: float = 2.0,
        batch_size: int = 50,
        worker_id: uuid.UUID | None = None,
    ) -> None:
        self.database = database
        self.settings = settings
        self.sender = sender
        self.poll_interval = poll_interval
        self.batch_size = batch_size
        self.worker_id = worker_id or uuid.uuid4()
        self._stop_event = asyncio.Event()

    def stop(self) -> None:
        self._stop_event.set()

    @property
    def is_stopped(self) -> bool:
        return self._stop_event.is_set()

    async def run_single_iteration(self) -> int:
        return await dispatch_pending_outbox(
            self.database,
            sender=self.sender,
            worker_id=self.worker_id,
            batch_size=self.batch_size,
        )

    async def run_forever(self) -> None:
        logger.info("Outbox worker %s started", self.worker_id)
        while not self._stop_event.is_set():
            try:
                processed = await self.run_single_iteration()
                if processed == 0:
                    await asyncio.sleep(self.poll_interval)
            except asyncio.CancelledError:
                break
            except Exception as err:
                logger.exception("Outbox worker iteration failed: %s", err)
                await asyncio.sleep(self.poll_interval)
        logger.info("Outbox worker %s stopped cleanly", self.worker_id)
