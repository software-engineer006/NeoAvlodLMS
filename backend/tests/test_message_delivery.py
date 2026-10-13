import asyncio
import json
import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from message_fixtures import World, world
from sqlalchemy import func, select, update
from test_messages import draft, send_request

from neoavlod.database import Database
from neoavlod.errors import DomainError
from neoavlod.message_schemas import MessageDraft
from neoavlod.models import MessageCampaign, MessageDelivery, Parent, Staff, Student
from neoavlod.models.common import Status
from neoavlod.services import messages
from neoavlod.services.bot_settings import update_bot_token
from neoavlod.services.message_delivery import DeliveryError, dispatch_pending_messages
from neoavlod.services.outbox import OutboxWorker
from neoavlod.settings import Settings

pytestmark = pytest.mark.anyio


class Sender:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.sent: list[tuple[int, str]] = []

    async def send_message(self, telegram_id: int, message: str) -> None:
        if self.error:
            raise self.error
        self.sent.append((telegram_id, message))


async def enqueue(database: Database, data: World, item: MessageDraft | None = None) -> uuid.UUID:
    request = await send_request(database, item or draft(scope="all", kind="parents"))
    async with database.session() as session, session.begin():
        return (await messages.enqueue(session, data.identity, request)).id


async def due(database: Database) -> None:
    async with database.session() as session, session.begin():
        past = datetime.now(UTC) - timedelta(seconds=2)
        await session.execute(update(MessageDelivery).values(available_at=past, attempted_at=past))


async def test_running_outbox_worker_delivers_plain_text_once_and_persists_history(
    model_database: Database,
) -> None:
    data = await world(model_database)
    key = await enqueue(model_database, data)
    sender = Sender()
    worker = OutboxWorker(model_database, Settings(), sender=sender)
    assert await worker.run_single_iteration() == 1
    assert sender.sent == [
        (100, "NeoAvlod LMS\n\nCentre notice\n\nHello <b>families</b>!\nA new lesson.")
    ]
    assert await worker.run_single_iteration() == 0
    async with model_database.session() as session:
        detail = await messages.campaign_detail(session, key)
        assert detail["campaign"]["status"] == "completed"
        assert detail["campaign"]["counts"]["delivered"] == 1
        delivered = next(row for row in detail["recipients"] if row["status"] == "delivered")
        assert delivered["attempts"] == 1 and delivered["delivered_at"] is not None


async def test_transient_retry_permanent_failure_and_only_failed_manual_retry(
    model_database: Database,
) -> None:
    data = await world(model_database)
    key = await enqueue(model_database, data)
    failing = Sender(DeliveryError("Network unavailable"))
    assert await dispatch_pending_messages(model_database, sender=failing, pace_seconds=0) == 0
    async with model_database.session() as session:
        item = await session.scalar(
            select(MessageDelivery).where(MessageDelivery.status == "pending")
        )
        assert item and item.attempts == 1 and item.available_at > datetime.now(UTC)
    await due(model_database)
    blocked = Sender(DeliveryError("Bot blocked", permanent=True))
    assert await dispatch_pending_messages(model_database, sender=blocked, pace_seconds=0) == 0
    async with model_database.session() as session, session.begin():
        assert await messages.retry_failed(session, key, data.identity) == 1
        assert await messages.retry_failed(session, key, data.identity) == 0
    await due(model_database)
    sender = Sender()
    assert await dispatch_pending_messages(model_database, sender=sender, pace_seconds=0) == 1
    async with model_database.session() as session, session.begin():
        assert await messages.retry_failed(session, key, data.identity) == 0
        saved = await session.scalar(
            select(MessageDelivery).where(MessageDelivery.status == "delivered")
        )
        assert saved and saved.attempts == 3 and saved.retried_by == data.identity.staff.id
        assert saved.retried_at and saved.last_error is None
        with pytest.raises(DomainError) as completed:
            await messages.cancel(session, key, data.identity)
        assert getattr(completed.value, "status_code", None) == 409
    assert len(sender.sent) == 1


async def test_five_failed_attempts_end_retry_cycle(model_database: Database) -> None:
    data = await world(model_database)
    key = await enqueue(model_database, data)
    sender = Sender(DeliveryError("Offline"))
    for _ in range(5):
        await due(model_database)
        await dispatch_pending_messages(model_database, sender=sender, pace_seconds=0)
    async with model_database.session() as session:
        detail = await messages.campaign_detail(session, key)
        assert detail["campaign"]["counts"]["failed"] == 1
        saved = await session.scalar(
            select(MessageDelivery).where(MessageDelivery.status == "failed")
        )
        assert saved and saved.attempts == saved.retry_attempts == 5


async def test_telegram_429_persists_global_pause_including_newly_enqueued_message(
    model_database: Database,
) -> None:
    data = await world(model_database)
    await enqueue(model_database, data)
    calls = 0

    def rate_limited(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            429, json={"ok": False, "error_code": 429, "parameters": {"retry_after": 17}}
        )

    transport = httpx.MockTransport(rate_limited)
    await dispatch_pending_messages(model_database, transport=transport, pace_seconds=0)
    # A fresh campaign must not bypass the pause after a worker restart.
    await enqueue(
        model_database,
        data,
        draft(scope="selected", kind="students", student_ids=[data.students[0].id]),
    )
    await dispatch_pending_messages(model_database, transport=transport, pace_seconds=0)
    assert calls == 1
    async with model_database.session() as session:
        pending = list(
            (
                await session.scalars(
                    select(MessageDelivery).where(MessageDelivery.status == "pending")
                )
            ).all()
        )
        assert len(pending) == 2
        assert all(
            item.available_at >= datetime.now(UTC) + timedelta(seconds=15) for item in pending
        )
        assert sum(item.retry_attempts for item in pending) == 0


@pytest.mark.parametrize("code", [400, 403])
async def test_telegram_permanent_error_is_safe_and_not_auto_retried(
    model_database: Database, code: int
) -> None:
    data = await world(model_database)
    key = await enqueue(model_database, data)

    def blocked(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            code,
            json={"ok": False, "error_code": code, "description": "secret token or recipient data"},
        )

    await dispatch_pending_messages(
        model_database, transport=httpx.MockTransport(blocked), pace_seconds=0
    )
    async with model_database.session() as session:
        detail = await messages.campaign_detail(session, key)
        assert detail["campaign"]["counts"]["failed"] == 1
        assert "secret" not in str(detail)


async def test_bot_switch_waits_for_reconnect_and_uses_new_token_and_current_chat(
    model_database: Database,
) -> None:
    data = await world(model_database)
    key = await enqueue(model_database, data)

    def bot_identity(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"ok": True, "result": {"id": 999, "is_bot": True, "username": "second_bot"}}
        )

    async with model_database.session() as session:
        await update_bot_token(
            session,
            Settings(),
            "456:SECOND_TEST_TOKEN",
            changed_by=data.identity.staff.id,
            transport=httpx.MockTransport(bot_identity),
        )
    sender = Sender()
    assert await dispatch_pending_messages(model_database, sender=sender, pace_seconds=0) == 0
    assert sender.sent == []
    async with model_database.session() as session, session.begin():
        parent = await session.get(Parent, data.parents[0].id)
        assert parent
        parent.telegram_reconnect_required = False  # State established by verified /start.
        parent.telegram_id = 101
        pending = await session.scalar(
            select(MessageDelivery).where(MessageDelivery.status == "pending")
        )
        assert pending and pending.attempts == 0
        pending.available_at = datetime.now(UTC)
    requests: list[httpx.Request] = []

    def delivered(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})

    assert (
        await dispatch_pending_messages(
            model_database, transport=httpx.MockTransport(delivered), pace_seconds=0
        )
        == 1
    )
    assert "456:SECOND_TEST_TOKEN" in str(requests[0].url)
    assert json.loads(requests[0].content)["chat_id"] == 101
    async with model_database.session() as session:
        assert (await messages.campaign_detail(session, key))["campaign"]["counts"][
            "delivered"
        ] == 1


async def test_group_transfer_after_enqueue_is_skipped(model_database: Database) -> None:
    data = await world(model_database)
    key = await enqueue(
        model_database, data, draft(scope="groups", kind="parents", group_ids=[data.groups[0].id])
    )
    async with model_database.session() as session, session.begin():
        pupil = await session.get(Student, data.students[0].id)
        assert pupil
        pupil.group_id = data.groups[1].id
    sender = Sender()
    assert await dispatch_pending_messages(model_database, sender=sender, pace_seconds=0) == 0
    assert sender.sent == []
    async with model_database.session() as session:
        counts = (await messages.campaign_detail(session, key))["campaign"]["counts"]
        assert counts["pending"] == 0 and counts["skipped"] == 2


async def test_cancel_during_send_keeps_acknowledged_delivery_and_stops_remainder(
    model_database: Database,
) -> None:
    data = await world(model_database)
    key = await enqueue(model_database, data, draft())
    started, release, cancelling = asyncio.Event(), asyncio.Event(), asyncio.Event()

    class WaitingSender(Sender):
        async def send_message(self, telegram_id: int, message: str) -> None:
            started.set()
            await release.wait()
            self.sent.append((telegram_id, message))

    sender = WaitingSender()
    sending = asyncio.create_task(
        dispatch_pending_messages(model_database, sender=sender, batch_size=1, pace_seconds=0)
    )
    await asyncio.wait_for(started.wait(), 2)

    async def cancel() -> None:
        async with model_database.session() as session, session.begin():
            cancelling.set()
            await messages.cancel(session, key, data.identity)

    cancel_task = asyncio.create_task(cancel())
    await cancelling.wait()
    await asyncio.sleep(0)
    assert not cancel_task.done()
    release.set()
    assert await sending == 1
    await cancel_task
    assert await dispatch_pending_messages(model_database, sender=sender, pace_seconds=0) == 0
    async with model_database.session() as session:
        counts = (await messages.campaign_detail(session, key))["campaign"]["counts"]
        assert counts["delivered"] == 1 and counts["cancelled"] == 3
    assert len(sender.sent) == 1


@pytest.mark.parametrize("mutation", ["inactive", "disconnected", "revoked"])
async def test_delivery_rechecks_current_recipient_and_sender_permission(
    model_database: Database, mutation: str
) -> None:
    data = await world(model_database)
    key = await enqueue(model_database, data)
    async with model_database.session() as session, session.begin():
        if mutation == "inactive":
            await session.execute(
                update(Student)
                .where(Student.parent_id == data.parents[0].id)
                .values(status=Status.INACTIVE)
            )
        elif mutation == "disconnected":
            person = await session.get(Parent, data.parents[0].id)
            assert person
            person.telegram_id = None
        else:
            author = await session.get(Staff, data.identity.staff.id)
            assert author
            author.status = Status.INACTIVE
    sender = Sender()
    assert await dispatch_pending_messages(model_database, sender=sender, pace_seconds=0) == 0
    assert sender.sent == []
    async with model_database.session() as session:
        counts = (await messages.campaign_detail(session, key))["campaign"]["counts"]
        assert counts["pending"] == 0
        assert counts["cancelled" if mutation == "revoked" else "skipped"] >= 1


async def test_crash_recovery_and_concurrent_dispatch_no_double_send(
    model_database: Database,
) -> None:
    data = await world(model_database)
    await enqueue(model_database, data)

    class Crashed(Sender):
        async def send_message(self, telegram_id: int, message: str) -> None:
            raise asyncio.CancelledError

    with pytest.raises(asyncio.CancelledError):
        await dispatch_pending_messages(model_database, sender=Crashed(), pace_seconds=0)
    async with model_database.session() as session:
        pending = await session.scalar(
            select(MessageDelivery).where(MessageDelivery.status == "pending")
        )
        assert pending and pending.attempts == 0
    sender = Sender()
    values = await asyncio.gather(
        *[
            dispatch_pending_messages(model_database, sender=sender, pace_seconds=0)
            for _ in range(2)
        ]
    )
    assert sum(values) == 1 and len(sender.sent) == 1


async def test_token_change_cannot_interleave_with_send_and_next_send_uses_new_token(
    model_database: Database,
) -> None:
    data = await world(model_database)
    await enqueue(model_database, data)
    sending, release, identity_checked = asyncio.Event(), asyncio.Event(), asyncio.Event()
    posted: list[str] = []

    async def transport_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("getMe"):
            identity_checked.set()
            return httpx.Response(
                200,
                json={
                    "ok": True,
                    "result": {
                        "id": 500,
                        "is_bot": True,
                        "username": "renamed_bot",
                    },
                },
            )
        posted.append(str(request.url))
        sending.set()
        await release.wait()
        return httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})

    transport = httpx.MockTransport(transport_handler)
    sending_task = asyncio.create_task(
        dispatch_pending_messages(model_database, transport=transport, pace_seconds=0)
    )
    await asyncio.wait_for(sending.wait(), 2)

    async def rotate() -> None:
        async with model_database.session() as session:
            await update_bot_token(
                session,
                Settings(),
                "456:ROTATED_TEST_TOKEN",
                changed_by=data.identity.staff.id,
                transport=transport,
            )

    rotation_task = asyncio.create_task(rotate())
    await asyncio.wait_for(identity_checked.wait(), 2)
    await asyncio.sleep(0)
    assert not rotation_task.done()
    release.set()
    assert await sending_task == 1
    await rotation_task
    await enqueue(
        model_database,
        data,
        draft(scope="selected", kind="students", student_ids=[data.students[0].id]),
    )
    await due(model_database)
    assert await dispatch_pending_messages(model_database, transport=transport, pace_seconds=0) == 1
    assert "123:MESSAGE_TEST_TOKEN" in posted[0]
    assert "456:ROTATED_TEST_TOKEN" in posted[1]


async def test_cancel_and_global_per_chat_pacing_survive_new_dispatcher(
    model_database: Database,
) -> None:
    data = await world(model_database)
    key = await enqueue(model_database, data)
    sender = Sender()
    assert await dispatch_pending_messages(model_database, sender=sender, pace_seconds=0) == 1
    second = await enqueue(model_database, data)
    assert await dispatch_pending_messages(model_database, sender=sender, pace_seconds=0) == 0
    async with model_database.session() as session, session.begin():
        detail = await messages.campaign_detail(session, second)
        assert detail["campaign"]["counts"]["pending"] == 1
        await messages.cancel(session, second, data.identity)
    await due(model_database)
    assert await dispatch_pending_messages(model_database, sender=sender, pace_seconds=0) == 0
    assert len(sender.sent) == 1
    async with model_database.session() as session:
        assert await session.scalar(select(func.count()).select_from(MessageCampaign)) == 2
        assert (await messages.campaign_detail(session, key))["campaign"]["counts"][
            "delivered"
        ] == 1
