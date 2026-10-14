"""Serialized durable broadcast dispatch, with Telegram pacing and retry_after.

The PostgreSQL transaction lock prevents concurrent sends and is released on crash.
An acknowledgement lost to a network/process failure can still be retried: Telegram
sendMessage has no idempotency key, so delivery is at-least-once.
"""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from neoavlod.database import Database
from neoavlod.errors import DomainError
from neoavlod.message_schemas import format_message
from neoavlod.models import (
    Group,
    MessageCampaign,
    MessageDelivery,
    NotificationOutbox,
    Parent,
    Staff,
    Student,
    StudentGroupEnrollment,
)
from neoavlod.models.common import Status
from neoavlod.security.rbac import Permission, has_permission
from neoavlod.security.secrets import decrypt_token
from neoavlod.services.bot_settings import locked_bot_settings
from neoavlod.services.messages import QUEUE_LOCK
from neoavlod.services.telegram import TelegramSender
from neoavlod.settings import Settings


class DeliveryError(DomainError):
    def __init__(
        self, message: str, *, permanent: bool = False, retry_after: int | None = None
    ) -> None:
        super().__init__(message, 503)
        self.permanent = permanent
        self.retry_after = retry_after


class BroadcastSender:
    def __init__(self, token: str, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.token = token
        self.transport = transport

    async def send_message(self, telegram_id: int, message: str) -> None:
        try:
            async with httpx.AsyncClient(
                transport=self.transport, timeout=10, trust_env=False
            ) as client:
                response = await client.post(
                    f"https://api.telegram.org/bot{self.token}/sendMessage",
                    json={
                        "chat_id": telegram_id,
                        "text": message,
                        "link_preview_options": {"is_disabled": True},
                    },
                )
            try:
                data = response.json()
            except ValueError:
                data = {}
            error_code = (
                data.get("error_code", response.status_code)
                if isinstance(data, dict)
                else response.status_code
            )
            if error_code == 429:
                parameters = data.get("parameters", {}) if isinstance(data, dict) else {}
                delay = parameters.get("retry_after", 1) if isinstance(parameters, dict) else 1
                delay = (
                    max(1, min(86400, int(delay)))
                    if isinstance(delay, (int, float)) and not isinstance(delay, bool)
                    else 1
                )
                raise DeliveryError("Telegram limiti; navbat kutmoqda", retry_after=delay)
            if error_code == 403:
                raise DeliveryError(
                    "Qabul qiluvchi botni bloklagan yoki xabarga ruxsat bermagan", permanent=True
                )
            if error_code == 400:
                raise DeliveryError("Telegram manzili yoki xabar qabul qilinmadi", permanent=True)
            if (
                response.status_code != 200
                or not isinstance(data, dict)
                or data.get("ok") is not True
            ):
                raise DeliveryError("Telegram xizmati xabarni qabul qilmadi")
        except httpx.HTTPError:
            raise DeliveryError(
                "Telegram bilan bog‘lanib bo‘lmadi; qayta urinish kutilmoqda"
            ) from None


async def recipient(
    session: AsyncSession, item: MessageDelivery, group_ids: list[uuid.UUID] | None = None
) -> Parent | Student | None:
    if item.kind == "parent":
        if item.parent_id is None:
            return None
        query = (
            select(Student.id)
            .join(
                StudentGroupEnrollment,
                (StudentGroupEnrollment.student_id == Student.id)
                & StudentGroupEnrollment.is_active.is_(True),
            )
            .join(Group, StudentGroupEnrollment.group_id == Group.id)
            .where(
                Student.parent_id == item.parent_id,
                Student.status == Status.ACTIVE,
                Group.status == Status.ACTIVE,
            )
        )
        if group_ids is not None:
            query = query.where(Group.id.in_(group_ids))
        active = await session.scalar(query.limit(1))
        return await session.get(Parent, item.parent_id) if active else None
    if item.student_id is None:
        return None
    query_pupil = (
        select(Student)
        .join(
            StudentGroupEnrollment,
            (StudentGroupEnrollment.student_id == Student.id)
            & StudentGroupEnrollment.is_active.is_(True),
        )
        .join(Group, StudentGroupEnrollment.group_id == Group.id)
        .where(
            Student.id == item.student_id,
            Student.status == Status.ACTIVE,
            Group.status == Status.ACTIVE,
        )
    )
    if group_ids is not None:
        query_pupil = query_pupil.where(Group.id.in_(group_ids))
    pupil: Student | None = await session.scalar(query_pupil)
    return pupil


async def dispatch_one(
    database: Database,
    settings: Settings,
    *,
    sender: TelegramSender | None,
    transport: httpx.AsyncBaseTransport | None,
) -> str:
    async with database.session() as session, session.begin():
        # Check without a mutation/config lock when the queue is empty.
        now = datetime.now(UTC)
        if (
            await session.scalar(
                select(MessageDelivery.id)
                .where(MessageDelivery.status == "pending", MessageDelivery.available_at <= now)
                .limit(1)
            )
            is None
        ):
            return "idle"
        # Fixed lock order: bot configuration before broadcast queue. A token change
        # cannot interleave between the recipient check and its sendMessage request.
        config = await locked_bot_settings(session)
        if not await session.scalar(
            text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": QUEUE_LOCK}
        ):
            return "idle"
        item = await session.scalar(
            select(MessageDelivery)
            .where(
                MessageDelivery.status == "pending",
                MessageDelivery.available_at <= datetime.now(UTC),
            )
            .order_by(MessageDelivery.available_at, MessageDelivery.id)
            .limit(1)
            .with_for_update()
        )
        if item is None:
            return "idle"
        campaign = await session.get(MessageCampaign, item.campaign_id)
        assert campaign is not None
        author = await session.get(Staff, campaign.author_id)
        if (
            campaign.cancelled_at
            or author is None
            or not has_permission(author, Permission.MESSAGES_SEND)
        ):
            item.status = "cancelled"
            item.last_error = "Xabar navbati to‘xtatilgan yoki yuboruvchi ruxsati bekor qilingan"
            if campaign.cancelled_at is None:
                campaign.cancelled_at = now
                await session.execute(
                    update(MessageDelivery)
                    .where(
                        MessageDelivery.campaign_id == campaign.id,
                        MessageDelivery.status == "pending",
                    )
                    .values(status="cancelled", last_error=item.last_error)
                )
            return "changed"
        target_groups: list[uuid.UUID] | None = None
        if campaign.audience.get("scope") == "groups":
            group_keys = campaign.audience.get("group_ids")
            assert isinstance(group_keys, list)
            target_groups = [uuid.UUID(str(key)) for key in group_keys]
        person = await recipient(session, item, target_groups)
        if person is None:
            item.status, item.last_error = "skipped", "Qabul qiluvchi faol ro‘yxatda qolmagan"
            return "changed"
        if person.telegram_reconnect_required:
            item.available_at = now + timedelta(seconds=30)
            item.last_error = "Yangi botga qayta ulanish kutilmoqda"
            return "changed"
        if not person.telegram_connected or person.telegram_id is None:
            item.status, item.last_error = "skipped", "Qabul qiluvchining Telegram ulanishi uzilgan"
            return "changed"
        if not config.bot_token_encrypted:
            item.available_at = now + timedelta(seconds=30)
            item.last_error = "Telegram bot sozlanishi kutilmoqda"
            return "changed"
        telegram_id = person.telegram_id
        rate_identity = str(config.parameters.get("bot_id") or f"legacy:{config.version}")
        pause = config.parameters.get("message_pause_until")
        if (
            isinstance(pause, str)
            and config.parameters.get("message_pause_identity") == rate_identity
        ):
            try:
                pause_until = datetime.fromisoformat(pause)
                if pause_until > now:
                    item.available_at = pause_until
                    item.last_error = "Telegram limiti; navbat kutmoqda"
                    return "changed"
            except (ValueError, TypeError):
                pass
        if (
            await session.scalar(
                select(MessageDelivery.id)
                .where(
                    MessageDelivery.campaign_id == campaign.id,
                    MessageDelivery.status == "delivered",
                    MessageDelivery.telegram_id == telegram_id,
                )
                .limit(1)
            )
            is not None
        ):
            item.status, item.last_error = (
                "skipped",
                "Bir Telegram hisobiga takroriy xabar yuborilmaydi",
            )
            return "changed"
        # Across campaigns and attendance notifications, avoid >1 message/chat/sec.
        prior_message = await session.scalar(
            select(func.max(MessageDelivery.delivered_at)).where(
                MessageDelivery.telegram_id == telegram_id
            )
        )
        prior_attendance = await session.scalar(
            select(func.max(NotificationOutbox.delivered_at)).where(
                NotificationOutbox.telegram_id == telegram_id
            )
        )
        prior_attempt = await session.scalar(
            select(func.max(MessageDelivery.attempted_at)).where(
                MessageDelivery.telegram_id == telegram_id
            )
        )
        previous = max(
            (
                value
                for value in (prior_message, prior_attendance, prior_attempt)
                if value is not None
            ),
            default=None,
        )
        if previous is not None and previous + timedelta(seconds=1) > now:
            item.available_at = previous + timedelta(seconds=1)
            return "changed"
        # This timestamp is persisted, so concurrent background jobs and process
        # restarts share the same ten-per-second broadcast budget.
        global_attempt = await session.scalar(select(func.max(MessageDelivery.attempted_at)))
        if global_attempt is not None and global_attempt + timedelta(seconds=0.1) > now:
            item.available_at = global_attempt + timedelta(seconds=0.1)
            return "changed"
        active_sender = sender or BroadcastSender(
            decrypt_token(config.bot_token_encrypted, settings), transport
        )
        item.telegram_id = telegram_id
        item.attempts += 1
        item.retry_attempts += 1
        item.attempted_at = datetime.now(UTC)
        try:
            await active_sender.send_message(
                telegram_id, format_message(campaign.title, campaign.body)
            )
        except Exception as error:
            if isinstance(error, DeliveryError) and error.retry_after is not None:
                due = datetime.now(UTC) + timedelta(seconds=error.retry_after)
                item.retry_attempts = max(0, item.retry_attempts - 1)
                item.available_at = due
                item.last_error = error.message
                config.parameters = {
                    **config.parameters,
                    "message_pause_identity": rate_identity,
                    "message_pause_until": due.isoformat(),
                }
                # Persist a bot-wide broadcast pause; restart/another dispatcher cannot
                # bypass Telegram's retry_after with the next recipient.
                await session.execute(
                    update(MessageDelivery)
                    .where(MessageDelivery.status == "pending")
                    .values(available_at=func.greatest(MessageDelivery.available_at, due))
                )
            else:
                permanent = isinstance(error, DeliveryError) and error.permanent
                item.status = "failed" if permanent or item.retry_attempts >= 5 else "pending"
                item.available_at = datetime.now(UTC) + timedelta(
                    seconds=min(2**item.retry_attempts * 5, 300)
                )
                item.last_error = (
                    error.message
                    if isinstance(error, DeliveryError)
                    else "Xabar yuborilmadi; qayta urinish kutilmoqda"
                )
            return "changed"
        item.status, item.last_error = "delivered", None
        item.delivered_at = datetime.now(UTC)
        return "sent"


async def dispatch_pending_messages(
    database: Database,
    *,
    settings: Settings | None = None,
    sender: TelegramSender | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
    batch_size: int = 20,
    pace_seconds: float = 0.1,
) -> int:
    delivered = 0
    config = settings or Settings()
    for _ in range(batch_size):
        outcome = await dispatch_one(database, config, sender=sender, transport=transport)
        if outcome == "idle":
            break
        if outcome == "sent":
            delivered += 1
        if pace_seconds > 0:
            await asyncio.sleep(pace_seconds)
    return delivered
