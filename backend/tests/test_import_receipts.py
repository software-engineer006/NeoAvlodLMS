import argparse
import asyncio
import json
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import delete, func, select
from test_educenter_import import sources as python_sources
from test_educenter_import import teachers
from test_english_import import sources

from neoavlod.database import Database
from neoavlod.educenter_import import apply_educenter
from neoavlod.educenter_import import build_plan as python_plan
from neoavlod.english_import import build_plan, reviewed_digest, run
from neoavlod.models import (
    Attendance,
    AttendanceBatch,
    AttendanceStatus,
    Group,
    ImportReceipt,
    Staff,
)
from neoavlod.services.import_receipts import deployment_import


@pytest.mark.anyio
async def test_english_deploy_preserves_admin_edits_and_does_not_reissue_credentials(
    model_database: Database, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = sources(tmp_path / "csv")
    args = argparse.Namespace(
        source=root,
        capacity=30,
        report=tmp_path / "private/plan.json",
        credentials=tmp_path / "private/accounts.json",
        apply=True,
        expected_plan=reviewed_digest(build_plan(root)),
        deployment_receipt=True,
    )
    await run(args)
    assert json.loads(capsys.readouterr().out)["result"]["deployment_status"] == "applied"
    async with model_database.session() as session, session.begin():
        teacher = await session.scalar(select(Staff))
        group = await session.scalar(select(Group))
        record = await session.scalar(select(Attendance))
        assert teacher and group and record
        teacher.first_name = "Edited teacher"
        password, auth_uuid = teacher.hashed_password, teacher.auth_uuid
        teacher_id, group_id, record_id = teacher.id, group.id, record.id
        group.name = "Administrator renamed"
        group.days_of_week = [1, 3]
        record.status = AttendanceStatus.ABSENT
        record.note = "Administrator checked"
    args.credentials.unlink()
    args.credentials.with_name("links.json").unlink()
    await run(args)
    assert json.loads(capsys.readouterr().out)["result"]["deployment_status"] == "already_applied"
    assert not args.credentials.exists() and not args.credentials.with_name("links.json").exists()
    async with model_database.session() as session:
        teacher = await session.get(Staff, teacher_id)
        group = await session.get(Group, group_id)
        record = await session.get(Attendance, record_id)
        assert teacher and (teacher.hashed_password, teacher.auth_uuid) == (password, auth_uuid)
        assert teacher.first_name == "Edited teacher"
        assert group and group.name == "Administrator renamed" and group.days_of_week == [1, 3]
        assert record and record.status == AttendanceStatus.ABSENT
        assert record.note == "Administrator checked"


@pytest.mark.anyio
@pytest.mark.parametrize("broken", [None, "partial", "provenance", "history", "batch"])
async def test_legacy_python_adoption_is_readonly_and_requires_complete_provenance(
    model_database: Database, tmp_path: Path, broken: str | None
) -> None:
    plan = python_plan(python_sources(tmp_path / "csv"))
    await teachers(model_database)
    async with model_database.session() as session, session.begin():
        await apply_educenter(session, plan)
        group = await session.scalar(select(Group))
        record = await session.scalar(select(Attendance))
        assert group and record
        group.name = "Admin edited"
        record.note = "Manual correction"
        if broken == "partial":
            group.source_key = "different-source"
        elif broken == "provenance":
            group.source_data = {"changed": True}
        elif broken == "history":
            await session.delete(record)
        elif broken == "batch":
            batch = await session.scalar(select(AttendanceBatch))
            assert batch
            batch.date += timedelta(days=90)

    async def forbidden() -> dict[str, int]:
        pytest.fail("Legacy adoption must not overwrite admin edits")

    async def adopt(digest: str = "a" * 64) -> dict[str, Any]:
        async with model_database.session() as session, session.begin():
            return await deployment_import(
                session,
                key="python",
                digest=digest,
                roster=plan.roster,
                attendance=plan.attendance,
                lessons=plan.lessons,
                apply=forbidden,
            )

    if broken:
        with pytest.raises(ValueError, match="explicit review"):
            await adopt()
        async with model_database.session() as session:
            assert await session.scalar(select(func.count()).select_from(ImportReceipt)) == 0
        return
    assert (await adopt())["deployment_status"] == "adopted"
    assert (await adopt())["deployment_status"] == "already_applied"
    with pytest.raises(ValueError, match="digest changed"):
        await adopt("b" * 64)
    async with model_database.session() as session:
        assert await session.scalar(select(Group.name).where(Group.name == "Admin edited"))
        assert await session.scalar(
            select(Attendance.note).where(Attendance.note == "Manual correction")
        )


@pytest.mark.anyio
async def test_concurrent_first_deployment_once_and_atomic_receipt_rollback(
    model_database: Database, tmp_path: Path
) -> None:
    plan = build_plan(sources(tmp_path / "csv"))
    calls = 0

    async def apply() -> dict[str, int]:
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.02)
        return {"created": 1}

    async def invoke(fail: bool = False) -> dict[str, Any]:
        async with model_database.session() as session, session.begin():
            result = await deployment_import(
                session,
                key="english",
                digest="c" * 64,
                roster=plan,
                attendance=plan.attendance,
                apply=apply,
            )
            if fail:
                raise RuntimeError("transaction aborted")
            return result

    with pytest.raises(RuntimeError):
        await invoke(True)
    async with model_database.session() as session:
        assert await session.get(ImportReceipt, "english") is None
    results = await asyncio.gather(invoke(), invoke())
    assert calls == 2  # One rolled back attempt, one committed application.
    assert {r["deployment_status"] for r in results} == {"applied", "already_applied"}
    async with model_database.session() as session, session.begin():
        await session.execute(delete(ImportReceipt))
