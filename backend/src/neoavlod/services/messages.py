"""Audience preview, atomic enqueue and administrator campaign history.

The audience is frozen at enqueue. Retries never expand a campaign to new pupils.
"""

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, or_, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from neoavlod.errors import DomainError
from neoavlod.message_schemas import MessageAudience, MessageDraft, MessageSend, format_message
from neoavlod.models import Group, MessageCampaign, MessageDelivery, Parent, Student, SystemSettings
from neoavlod.models.common import Status
from neoavlod.security.sessions import Identity
from neoavlod.services.bot_settings import locked_bot_settings

QUEUE_LOCK = 0x4E454F092
STATUSES = ("pending", "delivered", "failed", "skipped", "cancelled")


async def queue_lock(session: AsyncSession) -> None:
    await session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": QUEUE_LOCK})


@dataclass(frozen=True)
class Candidate:
    id: uuid.UUID
    kind: str
    name: str
    group_names: list[str]
    student_names: list[str]
    telegram_id: int | None
    connected: bool
    reason: str | None

    def public(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "name": self.name,
            "group_names": self.group_names,
            "student_names": self.student_names,
            "connected": self.connected,
            "connection_reason": self.reason,
        }


def full_name(first: str, last: str | None) -> str:
    return f"{first} {last or ''}".strip()


async def candidates(
    session: AsyncSession, audience: MessageAudience | None = None
) -> list[Candidate]:
    query = (
        select(Student, Group.name)
        .join(Group, Student.group_id == Group.id)
        .where(
            Student.status == Status.ACTIVE,
            Group.status == Status.ACTIVE,
        )
    )
    if audience is not None and audience.scope == "groups":
        group_ids = set(
            (
                await session.scalars(
                    select(Group.id).where(
                        Group.id.in_(audience.group_ids), Group.status == Status.ACTIVE
                    )
                )
            ).all()
        )
        if group_ids != set(audience.group_ids):
            raise DomainError("Tanlangan guruh mavjud emas yoki faol emas", 422)
        query = query.where(Student.group_id.in_(audience.group_ids))
    rows = (await session.execute(query)).all()
    parent_groups: dict[uuid.UUID, set[str]] = {}
    parent_students: dict[uuid.UUID, set[str]] = {}
    result: list[Candidate] = []
    for pupil, group_name in rows:
        name = full_name(pupil.first_name, pupil.last_name)
        result.append(
            Candidate(
                pupil.id,
                "student",
                name,
                [group_name],
                [name],
                pupil.telegram_id,
                pupil.telegram_connected,
                connection_reason(pupil),
            )
        )
        if pupil.parent_id is not None:
            parent_groups.setdefault(pupil.parent_id, set()).add(group_name)
            parent_students.setdefault(pupil.parent_id, set()).add(name)
    parents = (await session.scalars(select(Parent).where(Parent.id.in_(parent_groups)))).all()
    result.extend(
        Candidate(
            p.id,
            "parent",
            full_name(p.first_name, p.last_name),
            sorted(parent_groups[p.id]),
            sorted(parent_students[p.id]),
            p.telegram_id,
            p.telegram_connected,
            connection_reason(p),
        )
        for p in parents
    )
    if audience is not None:
        if audience.kind != "both":
            kind = "parent" if audience.kind == "parents" else "student"
            result = [r for r in result if r.kind == kind]
        if audience.scope == "selected":
            expected = {("parent", key) for key in audience.parent_ids} | {
                ("student", key) for key in audience.student_ids
            }
            result = [r for r in result if (r.kind, r.id) in expected]
            if {(r.kind, r.id) for r in result} != expected:
                raise DomainError(
                    "Tanlangan qabul qiluvchi faol ro‘yxatda yo‘q; ro‘yxatni yangilang", 422
                )
    return sorted(result, key=lambda r: (r.kind, r.name.casefold(), str(r.id)))


def connection_reason(person: Parent | Student) -> str | None:
    if person.telegram_connected:
        return None
    return (
        "Yangi botga qayta ulanish kerak"
        if person.telegram_reconnect_required
        else "Telegram botga ulanmagan"
    )


def draft_digest(draft: MessageDraft) -> str:
    data = {
        "title": draft.title,
        "body": draft.body,
        "audience": draft.audience.model_dump(mode="json"),
    }
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def recipient_states(rows: list[Candidate]) -> dict[tuple[str, uuid.UUID], str | None]:
    seen: set[int] = set()
    reasons: dict[tuple[str, uuid.UUID], str | None] = {}
    for row in rows:
        reason = row.reason
        if row.connected and row.telegram_id is not None:
            if row.telegram_id in seen:
                reason = "Bir Telegram hisobiga takroriy xabar yuborilmaydi"
            else:
                seen.add(row.telegram_id)
        reasons[(row.kind, row.id)] = reason
    return reasons


async def preview(
    session: AsyncSession, draft: MessageDraft
) -> tuple[dict[str, Any], list[Candidate]]:
    rows = await candidates(session, draft.audience)
    config = await session.get(SystemSettings, 1)
    configured = bool(config and config.bot_token_encrypted and config.bot_username)
    reasons = recipient_states(rows)
    unlinked = sum(not row.connected for row in rows)
    duplicates = sum(row.connected and reasons[(row.kind, row.id)] is not None for row in rows)
    snapshot = {
        "draft": draft_digest(draft),
        "bot_version": config.version if config else 0,
        "bot_configured": configured,
        "recipients": [
            [
                row.kind,
                str(row.id),
                row.name,
                row.telegram_id,
                row.connected,
                row.group_names,
                row.student_names,
            ]
            for row in rows
        ],
    }
    return {
        "digest": hashlib.sha256(
            json.dumps(snapshot, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest(),
        "message": format_message(draft.title, draft.body),
        "bot_configured": configured,
        "total": len(rows),
        "eligible": len(rows) - unlinked - duplicates,
        "unlinked": unlinked,
        "duplicates": duplicates,
        "parents": sum(r.kind == "parent" for r in rows),
        "students": sum(r.kind == "student" for r in rows),
        "sample": [r.public() for r in rows[:20]],
    }, rows


async def enqueue(session: AsyncSession, actor: Identity, request: MessageSend) -> MessageCampaign:
    # Match dispatch lock order so bot switching/onboarding cannot change the
    # reviewed addresses between final validation and atomic enqueue.
    await locked_bot_settings(session)
    await queue_lock(session)
    fingerprint = draft_digest(request)
    existing = await session.scalar(
        select(MessageCampaign).where(
            MessageCampaign.author_id == actor.staff.id,
            MessageCampaign.request_id == request.request_id,
        )
    )
    if existing is not None:
        if existing.request_digest != fingerprint:
            raise DomainError("Bu so‘rov identifikatori boshqa xabar uchun ishlatilgan", 409)
        return existing
    reviewed, rows = await preview(session, request)
    if reviewed["digest"] != request.preview_digest:
        raise DomainError(
            "Qabul qiluvchilar yoki bot holati o‘zgardi; xabarni qayta ko‘rib chiqing", 409
        )
    if not reviewed["bot_configured"]:
        raise DomainError("Telegram bot sozlanmagan; superadmin botni sozlashi kerak", 503)
    if reviewed["eligible"] == 0:
        raise DomainError("Telegramga ulangan qabul qiluvchi topilmadi", 422)
    campaign = MessageCampaign(
        author_id=actor.staff.id,
        author_name=full_name(actor.staff.first_name, actor.staff.last_name),
        request_id=request.request_id,
        request_digest=fingerprint,
        title=request.title,
        body=request.body,
        audience=request.audience.model_dump(mode="json"),
    )
    session.add(campaign)
    await session.flush()
    reasons = recipient_states(rows)
    for row in rows:
        reason = reasons[(row.kind, row.id)]
        session.add(
            MessageDelivery(
                campaign_id=campaign.id,
                kind=row.kind,
                parent_id=row.id if row.kind == "parent" else None,
                student_id=row.id if row.kind == "student" else None,
                recipient_name=row.name,
                group_names=row.group_names,
                telegram_id=row.telegram_id,
                status="skipped" if reason else "pending",
                last_error=reason,
            )
        )
    await session.flush()
    return campaign


async def delivery_counts(
    session: AsyncSession, ids: list[uuid.UUID]
) -> dict[uuid.UUID, dict[str, int]]:
    result = {key: dict.fromkeys(STATUSES, 0) for key in ids}
    for key, status, count in (
        await session.execute(
            select(
                MessageDelivery.campaign_id, MessageDelivery.status, func.count(MessageDelivery.id)
            )
            .where(MessageDelivery.campaign_id.in_(ids))
            .group_by(MessageDelivery.campaign_id, MessageDelivery.status)
        )
    ).all():
        result[key][status] = count
    return result


def campaign_public(campaign: MessageCampaign, counts: dict[str, int]) -> dict[str, Any]:
    status = (
        "cancelled"
        if campaign.cancelled_at
        else "queued"
        if counts["pending"]
        else "partial"
        if counts["failed"]
        else "completed"
    )
    return {
        "id": campaign.id,
        "title": campaign.title,
        "body": campaign.body,
        "author_name": campaign.author_name,
        "created_at": campaign.created_at,
        "cancelled_at": campaign.cancelled_at,
        "audience": campaign.audience,
        "status": status,
        "counts": counts,
        "total": sum(counts.values()),
    }


async def campaign(session: AsyncSession, key: uuid.UUID) -> MessageCampaign:
    item = await session.get(MessageCampaign, key)
    if item is None:
        raise DomainError("Xabar topilmadi", 404)
    return item


async def campaign_list(
    session: AsyncSession, page: int, page_size: int, search: str = ""
) -> dict[str, Any]:
    query = select(MessageCampaign)
    if search:
        query = query.where(
            or_(
                MessageCampaign.title.ilike(f"%{search}%"),
                MessageCampaign.author_name.ilike(f"%{search}%"),
            )
        )
    total = await session.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = list(
        (
            await session.scalars(
                query.order_by(MessageCampaign.created_at.desc(), MessageCampaign.id.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ).all()
    )
    counts = await delivery_counts(session, [item.id for item in items])
    summary = dict.fromkeys(STATUSES, 0)
    for status, count in (
        await session.execute(
            select(MessageDelivery.status, func.count(MessageDelivery.id)).group_by(
                MessageDelivery.status
            )
        )
    ).all():
        summary[status] = count
    return {
        "items": [campaign_public(item, counts[item.id]) for item in items],
        "total": total,
        "page": page,
        "page_size": page_size,
        "summary": summary,
    }


async def campaign_detail(
    session: AsyncSession,
    key: uuid.UUID,
    page: int = 1,
    page_size: int = 50,
    status: str | None = None,
) -> dict[str, Any]:
    item = await campaign(session, key)
    counts = (await delivery_counts(session, [key]))[key]
    query = select(MessageDelivery).where(MessageDelivery.campaign_id == key)
    if status:
        query = query.where(MessageDelivery.status == status)
    total = await session.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = (
        await session.scalars(
            query.order_by(MessageDelivery.kind, MessageDelivery.recipient_name, MessageDelivery.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    return {
        "campaign": campaign_public(item, counts),
        "recipients": [
            {
                "id": row.id,
                "kind": row.kind,
                "name": row.recipient_name,
                "group_names": row.group_names,
                "status": row.status,
                "attempts": row.attempts,
                "last_error": row.last_error,
                "delivered_at": row.delivered_at,
                "available_at": row.available_at,
                "retried_at": row.retried_at,
            }
            for row in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


async def cancel(session: AsyncSession, key: uuid.UUID, actor: Identity) -> None:
    await queue_lock(session)
    item = await campaign(session, key)
    if item.cancelled_at is None:
        pending = await session.scalar(
            select(MessageDelivery.id)
            .where(MessageDelivery.campaign_id == key, MessageDelivery.status == "pending")
            .limit(1)
        )
        if pending is None:
            raise DomainError("Navbatdagi xabar qolmagan", 409)
        item.cancelled_at = datetime.now(UTC)
        item.cancelled_by = actor.staff.id
        await session.execute(
            update(MessageDelivery)
            .where(MessageDelivery.campaign_id == key, MessageDelivery.status == "pending")
            .values(status="cancelled", last_error="Administrator navbatni to‘xtatdi")
        )
    await session.flush()


async def retry_failed(session: AsyncSession, key: uuid.UUID, actor: Identity) -> int:
    await queue_lock(session)
    item = await campaign(session, key)
    if item.cancelled_at:
        raise DomainError("To‘xtatilgan xabarni qayta yuborib bo‘lmaydi", 409)
    now = datetime.now(UTC)
    result = await session.scalars(
        update(MessageDelivery)
        .where(MessageDelivery.campaign_id == key, MessageDelivery.status == "failed")
        .values(
            status="pending",
            retry_attempts=0,
            last_error=None,
            available_at=now,
            retried_by=actor.staff.id,
            retried_at=now,
        )
        .returning(MessageDelivery.id)
    )
    await session.flush()
    return len(result.all())
