import asyncio
import uuid
from typing import Any

import pytest
from message_fixtures import world
from pydantic import ValidationError
from sqlalchemy import func, select
from test_rbac import actor, client_for

from neoavlod.api import admin_messages
from neoavlod.database import Database
from neoavlod.errors import DomainError
from neoavlod.message_schemas import MessageAudience, MessageDraft, MessageSend
from neoavlod.models import MessageCampaign, MessageDelivery, Role, SystemSettings
from neoavlod.services import messages

pytestmark = pytest.mark.anyio
BASE = "/api/v1/admin/messages"


@pytest.fixture(autouse=True)
def disable_real_delivery(monkeypatch: pytest.MonkeyPatch) -> None:
    async def no_delivery(*args: object, **kwargs: object) -> int:
        return 0

    monkeypatch.setattr(admin_messages, "dispatch_pending_messages", no_delivery)


def draft(**audience: Any) -> MessageDraft:
    return MessageDraft(
        title="Centre notice",
        body="Hello <b>families</b>!\nA new lesson.",
        audience=MessageAudience(scope="all", kind="both")
        if not audience
        else MessageAudience(**audience),
    )


async def send_request(database: Database, item: MessageDraft) -> MessageSend:
    async with database.session() as session:
        preview, _ = await messages.preview(session, item)
    return MessageSend(
        **item.model_dump(), request_id=uuid.uuid4(), preview_digest=preview["digest"]
    )


async def test_audience_all_group_selected_dedup_and_read_only_preview(
    model_database: Database,
) -> None:
    data = await world(model_database)
    async with model_database.session() as session:
        result, rows = await messages.preview(session, draft())
        assert (result["total"], result["eligible"], result["unlinked"]) == (7, 4, 3)
        assert len(rows) == 7 and result["parents"] == 3 and result["students"] == 4
        one = next(row for row in rows if row.id == data.parents[0].id)
        assert one.group_names == ["Group A", "Group B"] and len(one.student_names) == 2
        assert "telegram_id" not in one.public() and "auth_uuid" not in one.public()
        grouped, _ = await messages.preview(
            session, draft(scope="groups", kind="parents", group_ids=[data.groups[0].id])
        )
        assert (grouped["total"], grouped["eligible"]) == (2, 1)
        selected, _ = await messages.preview(
            session,
            draft(
                scope="selected",
                kind="both",
                parent_ids=[data.parents[0].id],
                student_ids=[data.students[1].id],
            ),
        )
        assert selected["total"] == selected["eligible"] == 2
        assert await session.scalar(select(func.count()).select_from(MessageCampaign)) == 0
    async with model_database.session() as session, session.begin():
        pupil = await session.get(type(data.students[0]), data.students[0].id)
        assert pupil
        pupil.telegram_id = data.parents[0].telegram_id
    async with model_database.session() as session:
        result, _ = await messages.preview(session, draft())
        assert result["duplicates"] == 1 and result["eligible"] == 3
        with pytest.raises(DomainError, match="faol emas"):
            await messages.preview(
                session, draft(scope="groups", kind="both", group_ids=[data.groups[2].id])
            )
        with pytest.raises(DomainError, match="faol ro‘yxatda"):
            await messages.preview(
                session, draft(scope="selected", kind="parents", parent_ids=[data.parents[3].id])
            )


async def test_atomic_idempotent_concurrent_enqueue_stale_preview_and_frozen_history(
    model_database: Database,
) -> None:
    data = await world(model_database)
    request = await send_request(model_database, draft())

    async def enqueue_once() -> uuid.UUID:
        async with model_database.session() as session, session.begin():
            return (await messages.enqueue(session, data.identity, request)).id

    keys = await asyncio.gather(enqueue_once(), enqueue_once())
    assert keys[0] == keys[1]
    async with model_database.session() as session:
        assert await session.scalar(select(func.count()).select_from(MessageCampaign)) == 1
        assert await session.scalar(select(func.count()).select_from(MessageDelivery)) == 7
        detail = await messages.campaign_detail(session, keys[0], page_size=2)
        assert detail["total"] == 7 and len(detail["recipients"]) == 2
        assert detail["campaign"]["counts"]["pending"] == 4
        assert detail["campaign"]["counts"]["skipped"] == 3
        assert detail["campaign"]["body"] == request.body
        altered = request.model_copy(update={"body": "Other content"})
        with pytest.raises(DomainError) as conflict:
            await messages.enqueue(session, data.identity, altered)
        assert conflict.value.status_code == 409
    stale = await send_request(model_database, draft(scope="all", kind="parents"))
    async with model_database.session() as session, session.begin():
        parent = await session.get(type(data.parents[0]), data.parents[0].id)
        assert parent
        parent.telegram_reconnect_required = True
    with pytest.raises(DomainError, match="o‘zgardi"):
        async with model_database.session() as session, session.begin():
            await messages.enqueue(session, data.identity, stale)
    async with model_database.session() as session:
        assert await session.scalar(select(func.count()).select_from(MessageCampaign)) == 1


async def test_no_linked_recipient_or_unconfigured_bot_creates_no_campaign(
    model_database: Database,
) -> None:
    data = await world(model_database)
    no_link = await send_request(
        model_database, draft(scope="selected", kind="parents", parent_ids=[data.parents[1].id])
    )
    with pytest.raises(DomainError, match="ulangan qabul"):
        async with model_database.session() as session, session.begin():
            await messages.enqueue(session, data.identity, no_link)
    async with model_database.session() as session, session.begin():
        config = await session.get(SystemSettings, 1)
        assert config
        config.bot_token_encrypted = None
    request = await send_request(model_database, draft())
    with pytest.raises(DomainError, match="sozlanmagan"):
        async with model_database.session() as session, session.begin():
            await messages.enqueue(session, data.identity, request)
    async with model_database.session() as session:
        assert await session.scalar(select(func.count()).select_from(MessageCampaign)) == 0


async def test_admin_api_permission_csrf_preview_send_history_and_cancel(
    model_database: Database,
) -> None:
    data = await world(model_database)
    allowed = await actor(model_database, permissions=["messages:send"])
    teacher = await actor(model_database, role=Role.TEACHER)
    forbidden = await actor(model_database, permissions=["students:read"])
    for who in (teacher, forbidden):
        async with client_for(who) as client:
            assert (await client.get(BASE)).status_code == 403
            assert (await client.get(BASE + "/recipients")).status_code == 403
            assert (
                await client.post(BASE + "/preview", json=draft().model_dump(mode="json"))
            ).status_code == 403
    async with client_for(allowed) as client:
        group_rows = (await client.get(BASE + "/groups")).json()
        assert len(group_rows) == 2
        recipients = (
            await client.get(
                BASE + "/recipients", params={"kind": "parent", "q": "Child B", "page_size": 1}
            )
        ).json()
        assert recipients["total"] == 1 and recipients["items"][0]["id"] == str(data.parents[0].id)
        payload = draft().model_dump(mode="json")
        assert (
            await client.post(BASE + "/preview", json=payload, headers={"X-CSRF-Token": "bad"})
        ).status_code == 403
        assert (
            await client.post(
                BASE + "/preview", json=payload, headers={"Origin": "https://evil.example"}
            )
        ).status_code == 403
        preview = await client.post(BASE + "/preview", json=payload)
        assert preview.status_code == 200 and preview.json()["eligible"] == 4
        payload.update(request_id=str(uuid.uuid4()), preview_digest=preview.json()["digest"])
        sent = await client.post(BASE, json=payload)
        assert sent.status_code == 202
        key = sent.json()["campaign"]["id"]
        assert (await client.post(BASE, json=payload)).json()["campaign"]["id"] == key
        assert (await client.get(BASE)).json()["total"] == 1
        assert (await client.get(BASE + f"/{key}", params={"status": "pending"})).json()[
            "total"
        ] == 4
        cancelled = await client.post(BASE + f"/{key}/cancel")
        assert cancelled.status_code == 200
        assert cancelled.json()["campaign"]["counts"]["cancelled"] == 4
        assert (await client.post(BASE + f"/{key}/cancel")).status_code == 200
        assert (await client.post(BASE + f"/{key}/retry")).status_code == 409
        assert (await client.get(BASE + f"/{uuid.uuid4()}")).status_code == 404


@pytest.mark.parametrize(
    "values",
    [
        {"scope": "selected", "kind": "both"},
        {"scope": "all", "kind": "both", "student_ids": [uuid.uuid4()]},
        {"scope": "selected", "kind": "parents", "student_ids": [uuid.uuid4()]},
        {"scope": "groups", "kind": "both"},
    ],
)
def test_invalid_audiences_refused(values: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        MessageAudience.model_validate(values)


def test_telegram_text_limit_plain_unicode_and_no_null_characters() -> None:
    valid = MessageDraft(
        title="Notice", body="😀" * 2000, audience=MessageAudience(scope="all", kind="both")
    )
    assert valid.body.startswith("😀")
    for body in ("😀" * 2048, "a" * 4096, "bad\x00text", "bad\ud800text", "   "):
        with pytest.raises(ValidationError):
            MessageDraft(title="Notice", body=body, audience=valid.audience)
