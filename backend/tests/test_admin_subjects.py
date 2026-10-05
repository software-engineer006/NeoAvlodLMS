import uuid

import pytest
from factories import group
from test_rbac import actor, client_for

from neoavlod.database import Database
from neoavlod.models import Group, Role
from neoavlod.models.common import Status

pytestmark = pytest.mark.anyio
BASE = "/api/v1/admin/subjects"


async def test_only_subject_managers_reach_the_api(model_database: Database) -> None:
    teacher = await actor(model_database, role=Role.TEACHER)
    reader = await actor(model_database, permissions=["groups:read", "staff:manage"])
    for person in (teacher, reader):
        async with client_for(person) as client:
            assert (await client.get(BASE)).status_code == 403
            assert (await client.post(BASE, json={"name": "Fizika"})).status_code == 403
            assert (await client.delete(f"{BASE}/{uuid.uuid4()}")).status_code == 403
    boss = await actor(model_database, role=Role.SUPERADMIN)
    async with client_for(boss) as client:
        assert (await client.get(BASE)).status_code == 200


async def test_create_read_update_validation_and_duplicates(model_database: Database) -> None:
    who = await actor(model_database, permissions=["subjects:manage"])
    async with client_for(who) as client:
        created = await client.post(BASE, json={"name": "  Matematika  ", "description": "  "})
        assert created.status_code == 201
        data = created.json()
        assert data["name"] == "Matematika" and data["description"] is None
        assert data["is_active"] is True and data["active_groups"] == 0
        assert (await client.post(BASE, json={"name": "matematika"})).status_code == 409
        for bad in ({"name": "   "}, {"name": ""}, {"name": "x" * 151}, {}):
            assert (await client.post(BASE, json=bad)).status_code == 422
        assert (
            await client.post(BASE, json={"name": "A", "description": "d" * 2001})
        ).status_code == 422
        other = (await client.post(BASE, json={"name": "Fizika", "description": "Mexanika"})).json()
        fetched = await client.get(f"{BASE}/{other['id']}")
        assert fetched.json()["description"] == "Mexanika"
        assert (
            await client.patch(f"{BASE}/{other['id']}", json={"name": "MATEMATIKA"})
        ).status_code == 409
        same = await client.patch(f"{BASE}/{other['id']}", json={"name": "Fizika"})
        assert same.status_code == 200
        renamed = await client.patch(f"{BASE}/{other['id']}", json={"name": "Fizika 2"})
        assert renamed.json()["name"] == "Fizika 2" and renamed.json()["description"] == "Mexanika"
        cleared = await client.patch(f"{BASE}/{other['id']}", json={"description": None})
        assert cleared.json()["description"] is None
        assert (
            await client.patch(f"{BASE}/{other['id']}", json={"is_active": False})
        ).status_code == 422
        assert (await client.get(f"{BASE}/{uuid.uuid4()}")).status_code == 404
        assert (await client.patch(f"{BASE}/{uuid.uuid4()}", json={"name": "Q"})).status_code == 404


async def test_list_search_filter_and_pagination(model_database: Database) -> None:
    who = await actor(model_database, permissions=["subjects:manage"])
    async with client_for(who) as client:
        ids = []
        for index in range(5):
            response = await client.post(BASE, json={"name": f"Fan_{index}"})
            ids.append(response.json()["id"])
        await client.post(BASE, json={"name": "Tarix"})
        await client.post(f"{BASE}/{ids[0]}/deactivate")
        page = await client.get(BASE, params={"q": "fan_", "page_size": 2, "page": 3})
        assert page.json()["total"] == 5 and [i["name"] for i in page.json()["items"]] == ["Fan_4"]
        assert (await client.get(BASE, params={"q": "%"})).json()["total"] == 0
        assert (await client.get(BASE, params={"is_active": "false"})).json()["total"] == 1
        assert (await client.get(BASE, params={"is_active": "true"})).json()["total"] == 5
        names = [i["name"] for i in (await client.get(BASE)).json()["items"]]
        assert names == sorted(names, key=str.lower)
        assert (await client.get(BASE, params={"page_size": 101})).status_code == 422


async def test_deactivation_is_blocked_by_active_groups_and_delete_by_any_group(
    model_database: Database,
) -> None:
    who = await actor(model_database, permissions=["subjects:manage"])
    teacher = await actor(model_database, role=Role.TEACHER)
    async with client_for(who) as client:
        subject = (await client.post(BASE, json={"name": "Kimyo"})).json()
        free = (await client.post(BASE, json={"name": "Bo'sh fan"})).json()
        async with model_database.session() as session:
            linked = group(uuid.UUID(subject["id"]), teacher.staff_id)
            session.add(linked)
            await session.commit()
            group_id = linked.id
        info = (await client.get(f"{BASE}/{subject['id']}")).json()
        assert info["active_groups"] == 1 and info["total_groups"] == 1
        blocked = await client.post(f"{BASE}/{subject['id']}/deactivate")
        assert blocked.status_code == 409 and "1 ta faol guruh" in blocked.json()["detail"]
        assert (await client.delete(f"{BASE}/{subject['id']}")).status_code == 409
        async with model_database.session() as session:
            saved = await session.get(Group, group_id)
            assert saved
            saved.status = Status.INACTIVE
            await session.commit()
        off = await client.post(f"{BASE}/{subject['id']}/deactivate")
        assert off.status_code == 200 and off.json()["is_active"] is False
        assert off.json()["active_groups"] == 0 and off.json()["total_groups"] == 1
        assert (await client.delete(f"{BASE}/{subject['id']}")).status_code == 409
        on = await client.post(f"{BASE}/{subject['id']}/activate")
        assert on.json()["is_active"] is True
        assert (await client.delete(f"{BASE}/{free['id']}")).status_code == 204
        assert (await client.get(f"{BASE}/{free['id']}")).status_code == 404
