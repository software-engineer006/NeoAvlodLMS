import asyncio

import pytest
from sqlalchemy import select
from test_rbac import actor, client_for

from neoavlod.attendance_messages import (
    DEFAULT_TEMPLATE,
    PREVIEW_VALUES,
    render_template,
    validate_template,
)
from neoavlod.database import Database
from neoavlod.errors import DomainError
from neoavlod.models import AttendanceMessageTemplate, AuditEvent, Role

BASE = "/api/v1/admin/attendance/message-template"


def test_templates_reject_attributes_format_specs_unknown_fields_and_unbounded_messages() -> None:
    assert "14.10.2026" in render_template(DEFAULT_TEMPLATE, PREVIEW_VALUES)
    assert "09:00–10:30" in render_template(DEFAULT_TEMPLATE, PREVIEW_VALUES)
    for value in [
        DEFAULT_TEMPLATE.replace("{student_name}", "{student_name.__class__}"),
        DEFAULT_TEMPLATE.replace("{student_name}", "{student_name!r}"),
        DEFAULT_TEMPLATE.replace("{student_name}", "{student_name:10000}"),
        DEFAULT_TEMPLATE.replace("{student_name}", "{token}"),
        DEFAULT_TEMPLATE.replace("{date}", ""),
        DEFAULT_TEMPLATE + "{feedback}" * 5,
    ]:
        with pytest.raises(DomainError):
            validate_template(value)
    with pytest.raises(DomainError):
        render_template(DEFAULT_TEMPLATE, PREVIEW_VALUES | {"feedback": "😀" * 3000})


@pytest.mark.anyio
async def test_template_permissions_actor_versions_conflicts_and_noop(
    model_database: Database,
) -> None:
    editor = await actor(model_database, permissions=["attendance:write"])
    reader = await actor(model_database, permissions=["attendance:read"])
    teacher = await actor(model_database, role=Role.TEACHER)
    for person in (reader, teacher):
        async with client_for(person) as client:
            assert (await client.get(BASE)).status_code == 403
            assert (
                await client.post(f"{BASE}/preview", json={"body": DEFAULT_TEMPLATE})
            ).status_code == 403
            assert (
                await client.put(BASE, json={"body": DEFAULT_TEMPLATE, "expected_version": 0})
            ).status_code == 403
    changed = DEFAULT_TEMPLATE.replace("NeoAvlod — Davomat", "NeoAvlod — Dars")
    async with client_for(editor) as client:
        initial = (await client.get(BASE)).json()
        assert initial["version"] == 0 and initial["changed_by"] is None
        assert (await client.post(f"{BASE}/preview", json={"body": changed})).status_code == 200
        response = await client.put(BASE, json={"body": changed, "expected_version": 0})
        assert response.status_code == 200, response.text
        assert response.json()["version"] == 1
        assert response.json()["changed_by"] == str(editor.staff_id)
        assert response.json()["editor_name"]
        assert (await client.put(BASE, json={"body": changed, "expected_version": 1})).json()[
            "version"
        ] == 1
        assert (
            await client.put(BASE, json={"body": changed, "expected_version": 0})
        ).status_code == 409
        assert (
            await client.put(BASE, json={"body": "invalid {token}", "expected_version": 1})
        ).status_code == 422
        responses = await asyncio.gather(
            client.put(BASE, json={"body": changed + "\nNamuna A", "expected_version": 1}),
            client.put(BASE, json={"body": changed + "\nNamuna B", "expected_version": 1}),
        )
        assert sorted(response.status_code for response in responses) == [200, 409]
    async with model_database.session() as session:
        current = await session.get(AttendanceMessageTemplate, 1)
        assert current is not None and current.version == 2
        records = (
            await session.scalars(
                select(AuditEvent)
                .where(AuditEvent.entity_type == "attendance_template")
                .order_by(AuditEvent.id)
            )
        ).all()
        assert len(records) == 2
        assert all(record.actor_id == editor.staff_id for record in records)
        assert records[-1].body["changes"]["version"] == {"before": 1, "after": 2}
        assert "body" in records[-1].body["changes"]
