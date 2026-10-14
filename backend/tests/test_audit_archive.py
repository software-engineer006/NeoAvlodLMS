import asyncio
import base64
import errno
import gzip
import json
import os
import tracemalloc
import uuid
from datetime import date
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from pydantic import SecretStr
from sqlalchemy import func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError

from neoavlod.audit_archiver import LOCK_ID, AuditArchiver
from neoavlod.audit_context import emit
from neoavlod.audit_store import MAX_PLAIN, AuditStore, SegmentProof, json_line, sha256
from neoavlod.database import Database
from neoavlod.models import AuditEvent, AuditSegment, Subject
from neoavlod.settings import Settings

pytestmark = pytest.mark.anyio


@pytest.fixture
def store(tmp_path: Path) -> AuditStore:
    return AuditStore(
        Settings(
            audit_dir=tmp_path / "audit-logs",
            audit_encryption_key=SecretStr(Fernet.generate_key().decode()),
        ),
        create=True,
    )


def record(ident: int, *, message: str = "Namuna log") -> dict[str, object]:
    return {
        "schema": 1,
        "id": str(ident),
        "day": "2026-10-14",
        "at": "2026-10-14T07:00:01.123456Z",
        "action": "subject.insert",
        "actor": {"name": "Namuna", "role": "superadmin"},
        "message": message,
    }


async def seed(database: Database, count: int = 3) -> list[int]:
    async with database.session() as session:
        for number in range(count):
            await emit(session, "test.archive", details={"number": number})
        await session.commit()
        return list((await session.scalars(select(AuditEvent.id).order_by(AuditEvent.id))).all())


async def counts(database: Database) -> tuple[int, int]:
    async with database.session() as session:
        return (
            await session.scalar(select(func.count()).select_from(AuditEvent)) or 0,
            await session.scalar(select(func.count()).select_from(AuditSegment)) or 0,
        )


async def test_immutable_file_compression_retry_and_key_rotation(store: AuditStore) -> None:
    records = [record(n, message="Namuna log " * 100) for n in range(1, 129)]
    proof = store.persist(date(2026, 10, 14), records)
    path = store.directory / proof.object_name
    original = path.read_bytes()
    assert len(original) < len(b"".join(json_line(r) for r in records)) // 8
    assert b"Namuna" not in original
    assert path.stat().st_mode & 0o777 == 0o400
    assert store.read(proof) == records
    assert store.persist(proof.day, records) == proof and path.read_bytes() == original
    old_key = store.keys["v1"]
    encoded = old_key._signing_key + old_key._encryption_key
    rotated = AuditStore(
        Settings(
            audit_dir=store.directory,
            audit_key_id="v2",
            audit_encryption_key=SecretStr(Fernet.generate_key().decode()),
            audit_previous_keys=SecretStr(
                json.dumps({"v1": base64.urlsafe_b64encode(encoded).decode()})
            ),
        )
    )
    assert rotated.read(proof) == records
    assert store.read(proof) == records


async def test_file_traversal_symlink_corruption_manifest_and_missing_key(
    store: AuditStore,
) -> None:
    proof = store.persist(date(2026, 10, 14), [record(1)])
    from dataclasses import replace

    for name in ("../outside", "/tmp/outside", "2026-10-14.jsonl.gz", "a" * 500):
        with pytest.raises(ValueError, match="object name"):
            store.read(replace(proof, object_name=name))
    for bad in (
        replace(proof, cipher_hash="0" * 64),
        replace(proof, plain_hash="0" * 64),
        replace(proof, ids=[99]),
        replace(proof, key_id="missing"),
        replace(proof, day=date(2026, 10, 15)),
    ):
        with pytest.raises(ValueError):
            store.read(bad)
    linked = "2026-10-14-" + "a" * 64 + ".jsonl.gz.fernet"
    (store.directory / linked).symlink_to(store.directory / proof.object_name)
    with pytest.raises(OSError):
        store.read(replace(proof, object_name=linked))
    path = store.directory / proof.object_name
    path.chmod(0o600)
    path.write_bytes(b"corrupt")
    with pytest.raises(ValueError):
        store.read(proof)
    with pytest.raises(ValueError):
        store.persist(proof.day, [record(1)])
    assert path.read_bytes() == b"corrupt"


async def test_crash_before_metadata_reuses_orphan_without_losing_events(
    model_database: Database,
    store: AuditStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ids = await seed(model_database)
    original = store.persist
    crashed = False

    def crash(day: date, records: list[dict[str, object]]) -> SegmentProof:
        nonlocal crashed
        original(day, records)
        crashed = True
        raise RuntimeError("crash after fsync")

    monkeypatch.setattr(store, "persist", crash)
    worker = AuditArchiver(model_database, store)
    with pytest.raises(RuntimeError):
        await worker.once(force=True)
    assert crashed and await counts(model_database) == (3, 0)
    files = list(store.directory.glob("*.fernet"))
    assert len(files) == 1
    before = files[0].read_bytes()
    monkeypatch.setattr(store, "persist", original)
    assert await worker.once(force=True) == 3
    assert await counts(model_database) == (0, 1)
    assert await worker.once(force=True) == 0 and files[0].read_bytes() == before
    async with model_database.session() as session:
        segment = await session.scalar(select(AuditSegment))
        assert segment and segment.event_ids == ids


async def test_disk_full_and_readback_failure_never_prune(
    model_database: Database,
    store: AuditStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await seed(model_database)
    worker = AuditArchiver(model_database, store)
    original = os.fsync
    calls = 0

    def full(_: int) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            original(_)
            return
        raise OSError(errno.ENOSPC, "fixture disk full")

    monkeypatch.setattr(os, "fsync", full)
    with pytest.raises(OSError):
        await worker.once(force=True)
    assert await counts(model_database) == (3, 0)
    monkeypatch.setattr(os, "fsync", original)
    original_read = store.read

    def bad_read(_: SegmentProof) -> list[dict[str, object]]:
        raise ValueError("fixture read-back failure")

    monkeypatch.setattr(store, "read", bad_read)
    with pytest.raises(ValueError):
        await worker.once(force=True)
    assert await counts(model_database) == (3, 0)
    monkeypatch.setattr(store, "read", original_read)
    assert await worker.once(force=True) == 3


async def test_singleton_and_late_lower_sequence_commit_no_loss(
    model_database: Database,
    store: AuditStore,
) -> None:
    async with model_database.session() as delayed:
        first = await emit(delayed, "test.delayed")
        await seed(model_database, 5)
        async with model_database.engine.connect() as lease:
            await lease.execute(text("SELECT pg_advisory_lock(:key)"), {"key": LOCK_ID})
            await lease.commit()
            assert await AuditArchiver(model_database, store).once(force=True) == 0
            await lease.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": LOCK_ID})
            await lease.commit()
        worker = AuditArchiver(model_database, store, batch_size=2)
        assert await worker.once(force=True) == 2
        await delayed.commit()
        while await worker.once(force=True):
            pass
    assert await counts(model_database) == (0, 3)
    async with model_database.session() as session:
        segments = list((await session.scalars(select(AuditSegment))).all())
        ids = [ident for segment in segments for ident in segment.event_ids]
        assert len(ids) == len(set(ids)) == 6 and first in ids


async def restricted_database(database: Database, role: str) -> Database:
    assert role in {"neoavlod_app", "neoavlod_archiver"}
    password = "fixture-" + uuid.uuid4().hex
    async with database.engine.begin() as connection:
        command = await connection.scalar(
            text(
                "SELECT format('ALTER ROLE %I LOGIN PASSWORD %L',"
                "CAST(:role AS text),CAST(:password AS text))"
            ),
            {"role": role, "password": password},
        )
        assert isinstance(command, str)
        await connection.execute(text(command))
    url = make_url(database.engine.url).set(username=role, password=password)
    return Database(
        Settings(
            database_url=SecretStr(url.render_as_string(hide_password=False)), environment="test"
        )
    )


async def test_actual_runtime_and_archiver_credentials_have_separate_authority(
    model_database: Database,
    store: AuditStore,
) -> None:
    ids = await seed(model_database)
    app = await restricted_database(model_database, "neoavlod_app")
    archive = await restricted_database(model_database, "neoavlod_archiver")
    try:
        for statement in (
            "UPDATE audit.events SET action='forged.action'",
            "DELETE FROM audit.events",
            "TRUNCATE audit.events",
            "DELETE FROM audit.segments",
            "INSERT INTO audit.segments(id) VALUES (gen_random_uuid())",
            "SELECT audit.archive_commit(gen_random_uuid(),CURRENT_DATE,'x',"
            "ARRAY[1::bigint], 'x','x','v1')",
            "DROP TABLE audit.events",
            "ALTER TABLE audit.events DISABLE TRIGGER ALL",
            "SET ROLE neoavlod_archiver",
        ):
            with pytest.raises(DBAPIError):
                async with app.session() as session:
                    await session.execute(text(statement))
                    await session.commit()
        async with app.session() as session:
            session.add(Subject(name="Runtime namuna subject"))
            await session.commit()
        with pytest.raises(DBAPIError):
            async with archive.session() as session:
                await session.execute(text("DELETE FROM public.subjects"))
        assert await AuditArchiver(archive, store).once(force=True) == 4
        assert await counts(model_database) == (0, 1)
        for statement in (
            "DELETE FROM audit.segments",
            "UPDATE audit.events SET action='forged.action'",
            "TRUNCATE audit.events",
            "DELETE FROM audit.events",
        ):
            with pytest.raises(DBAPIError):
                async with archive.session() as session:
                    await session.execute(text(statement))
                    await session.commit()
        assert await counts(model_database) == (0, 1)
        async with model_database.session() as session:
            segment = await session.scalar(select(AuditSegment))
            assert segment and set(ids) <= set(segment.event_ids)
    finally:
        await app.close()
        await archive.close()


async def test_batch_and_decompression_memory_bounded(store: AuditStore) -> None:
    records = [record(n, message="x" * 30000) for n in range(1, 129)]
    with pytest.raises(ValueError):
        store.persist(date(2026, 10, 14), records + [record(129)])
    tracemalloc.start()
    try:
        proof = store.persist(date(2026, 10, 14), records)
        assert store.read(proof) == records
        peak = tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()
    assert peak < 40 * 1024 * 1024


async def test_staging_cleanup_preserves_every_committed_file(store: AuditStore) -> None:
    proof = store.persist(date(2026, 10, 14), [record(1)])
    path = store.directory / (".pending-" + uuid.uuid4().hex)
    path.write_bytes(b"partial")
    store.clean_pending()
    assert not path.exists() and store.read(proof) == [record(1)]


async def test_fifo_is_rejected_without_blocking_archive_reader(store: AuditStore) -> None:
    name = "2026-10-14-" + "f" * 64 + ".jsonl.gz.fernet"
    os.mkfifo(store.directory / name, 0o600)
    proof = SegmentProof(name, date(2026, 10, 14), [1], "a" * 64, "b" * 64, "v1")
    with pytest.raises(ValueError, match="Invalid audit file"):
        await asyncio.wait_for(asyncio.to_thread(store.read, proof), timeout=1)


async def test_encrypted_gzip_bomb_is_bounded(store: AuditStore) -> None:
    raw = b"x" * (MAX_PLAIN + 1)
    manifest = {
        "schema": 1,
        "day": "2026-10-14",
        "ids": [1],
        "plain_sha256": sha256(raw),
        "key_id": "v1",
    }
    cipher = store.keys["v1"].encrypt(json_line(manifest) + gzip.compress(raw, mtime=0))
    name = "2026-10-14-" + "b" * 64 + ".jsonl.gz.fernet"
    path = store.directory / name
    path.write_bytes(cipher)
    proof = SegmentProof(name, date(2026, 10, 14), [1], sha256(raw), sha256(cipher), "v1")
    with pytest.raises(ValueError, match="plaintext integrity"):
        store.read(proof)


async def test_backup_restore_and_restart_keep_same_key_and_evidence(
    store: AuditStore,
    tmp_path: Path,
) -> None:
    import shutil

    proof = store.persist(date(2026, 10, 14), [record(1)])
    restored = tmp_path / "restored-audit-logs"
    shutil.copytree(store.directory, restored)
    cipher = store.keys["v1"]
    key = base64.urlsafe_b64encode(cipher._signing_key + cipher._encryption_key).decode()
    restarted = AuditStore(Settings(audit_dir=restored, audit_encryption_key=SecretStr(key)))
    assert restarted.read(proof) == store.read(proof)
    assert (restored / proof.object_name).read_bytes() == (
        store.directory / proof.object_name
    ).read_bytes()


async def test_manifest_mismatch_never_commits_metadata_or_prunes(
    model_database: Database,
    store: AuditStore,
) -> None:
    ids = await seed(model_database)
    for invalid in (ids + [ids[0]], ids + [99999999]):
        with pytest.raises(DBAPIError):
            async with model_database.session() as session:
                await session.execute(
                    text(
                        "SELECT audit.archive_commit(:id,CURRENT_DATE,:name,:ids,"
                        ":plain,:cipher,'v1')"
                    ),
                    {
                        "id": uuid.uuid4(),
                        "name": f"{date.today()}-{'c' * 64}.jsonl.gz.fernet",
                        "ids": invalid,
                        "plain": "d" * 64,
                        "cipher": "e" * 64,
                    },
                )
                await session.commit()
        assert await counts(model_database) == (3, 0)
    worker = AuditArchiver(model_database, store)
    outcomes = await asyncio.gather(worker.once(force=True), worker.once(force=True))
    assert sum(outcomes) == 3 and await counts(model_database) == (0, 1)
