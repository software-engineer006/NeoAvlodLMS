"""Consistent archive+queue snapshots, with bounded RAM and private disk scratch."""

import gzip
import json
import os
import sqlite3
import tempfile
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Any

import anyio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from neoavlod.audit_store import AuditStore, SegmentProof, json_line
from neoavlod.database import Database
from neoavlod.errors import DomainError
from neoavlod.models import AuditEvent, AuditSegment


def segment_proof(segment: AuditSegment) -> SegmentProof:
    return SegmentProof(
        segment.object_name,
        segment.local_day,
        segment.event_ids,
        segment.plain_sha256,
        segment.cipher_sha256,
        segment.key_id,
    )


class DaySnapshot:
    def __init__(self) -> None:
        descriptor, filename = tempfile.mkstemp(prefix="neoavlod-audit-", suffix=".sqlite")
        os.close(descriptor)
        self.path = Path(filename)
        self.connection = sqlite3.connect(filename, check_same_thread=False)
        self.connection.executescript("""
            PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF;
            PRAGMA cache_size=-2048; PRAGMA temp_store=FILE;
            CREATE TABLE events(id INTEGER PRIMARY KEY,at TEXT NOT NULL,
                actor TEXT,action TEXT,entity TEXT,outcome TEXT,body TEXT NOT NULL);
            CREATE INDEX ordered_events ON events(at,id);
        """)

    def add(self, records: list[dict[str, Any]]) -> None:
        rows = []
        for entry in records:
            actor = entry.get("actor") or {}
            details = entry.get("details") or {}
            action = entry["action"]
            outcome = details.get("outcome") or (
                "rejected" if action.endswith(("rejected", "failed", "replay")) else "success"
            )
            rows.append(
                (
                    int(entry["id"]),
                    entry["at"],
                    actor.get("id"),
                    action,
                    (entry.get("entity") or {}).get("type"),
                    outcome,
                    json_line(entry).decode(),
                )
            )
        self.connection.executemany("INSERT INTO events VALUES (?,?,?,?,?,?,?)", rows)
        self.connection.commit()

    def page(
        self,
        *,
        cursor: str | None = None,
        actor: str | None = None,
        action: str | None = None,
        entity: str | None = None,
        outcome: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        clauses, values = [], []
        for key, value in (
            ("actor", actor),
            ("action", action),
            ("entity", entity),
            ("outcome", outcome),
        ):
            if value:
                clauses.append(f"{key}=?")
                values.append(value)
        conditions = " WHERE " + " AND ".join(clauses) if clauses else ""
        total = self.connection.execute(
            "SELECT count(*) FROM events" + conditions, values
        ).fetchone()[0]
        if cursor:
            try:
                timestamp, ident = cursor.rsplit("|", 1)
                if (
                    len(timestamp) != 27
                    or not timestamp.endswith("Z")
                    or len(ident) > 20
                    or not 1 <= int(ident) <= 2**63 - 1
                ):
                    raise ValueError
                datetime.fromisoformat(timestamp)
            except ValueError:
                raise DomainError("Log sahifasi kursori yaroqsiz", 422) from None
            clauses.append("(at<? OR (at=? AND id<?))")
            values.extend((timestamp, timestamp, str(int(ident))))
        conditions = " WHERE " + " AND ".join(clauses) if clauses else ""
        rows = self.connection.execute(
            "SELECT at,id,body FROM events" + conditions + " ORDER BY at DESC,id DESC LIMIT ?",
            [*values, limit + 1],
        ).fetchall()
        next_cursor = f"{rows[limit - 1][0]}|{rows[limit - 1][1]}" if len(rows) > limit else None
        return {
            "items": [json.loads(row[2]) for row in rows[:limit]],
            "actors": [
                json.loads(row[0])["actor"]
                for row in self.connection.execute(
                    "SELECT body FROM events WHERE id IN (SELECT max(id) FROM events "
                    "WHERE actor IS NOT NULL GROUP BY actor) ORDER BY actor LIMIT 1000"
                )
            ],
            "actions": [
                row[0]
                for row in self.connection.execute(
                    "SELECT DISTINCT action FROM events ORDER BY action LIMIT 100"
                )
            ],
            "total": total,
            "next_cursor": next_cursor,
            "page_size": limit,
        }

    def detail(self, ident: int) -> dict[str, Any]:
        row = self.connection.execute("SELECT body FROM events WHERE id=?", (ident,)).fetchone()
        if row is None:
            raise DomainError("Log yozuvi topilmadi", 404)
        return dict(json.loads(row[0]))

    def export(self) -> Path:
        descriptor, filename = tempfile.mkstemp(prefix="neoavlod-export-", suffix=".jsonl.gz")
        path = Path(filename)
        try:
            with os.fdopen(descriptor, "wb") as output:
                with gzip.GzipFile(fileobj=output, mode="wb", mtime=0, filename="") as zipped:
                    for row in self.connection.execute("SELECT body FROM events ORDER BY at,id"):
                        zipped.write(row[0].encode())
            return path
        except BaseException:
            path.unlink(missing_ok=True)
            raise

    def close(self) -> None:
        self.connection.close()
        self.path.unlink(missing_ok=True)


async def load_day(
    session: AsyncSession, store: AuditStore, day: date, snapshot: DaySnapshot
) -> None:
    segments = await session.stream_scalars(
        select(AuditSegment)
        .where(AuditSegment.local_day == day)
        .order_by(AuditSegment.first_at, AuditSegment.id)
        .execution_options(yield_per=16)
    )
    try:
        async for segment in segments:
            records = await anyio.to_thread.run_sync(store.read, segment_proof(segment))
            await anyio.to_thread.run_sync(snapshot.add, records)
    finally:
        await segments.close()
    pending = await session.stream_scalars(
        select(AuditEvent)
        .where(AuditEvent.local_day == day)
        .order_by(AuditEvent.id)
        .execution_options(yield_per=128)
    )
    try:
        async for rows in pending.partitions(128):
            await anyio.to_thread.run_sync(snapshot.add, [row.body for row in rows])
    finally:
        await pending.close()


@asynccontextmanager
async def day_snapshot(
    database: Database, store: AuditStore, day: date
) -> AsyncIterator[DaySnapshot]:
    snapshot: DaySnapshot | None = None
    try:
        snapshot = DaySnapshot()
        async with database.engine.connect() as connection:
            connection = await connection.execution_options(isolation_level="REPEATABLE READ")
            await connection.execute(text("SET TRANSACTION READ ONLY"))
            async with AsyncSession(bind=connection) as session:
                await load_day(session, store, day, snapshot)
        yield snapshot
    except (OSError, ValueError, sqlite3.DatabaseError, json.JSONDecodeError):
        raise DomainError("Log arxivi tekshiruvidan o‘tmadi; ma’lumot saqlangan", 503) from None
    finally:
        if snapshot is not None:
            await anyio.to_thread.run_sync(snapshot.close)
