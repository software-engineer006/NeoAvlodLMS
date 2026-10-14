"""Bounded singleton archiver: persist/read-back before exact transactional prune."""

import argparse
import asyncio
import logging
import signal
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import anyio
from sqlalchemy import select, text

from neoavlod.audit_store import MAX_BATCH, AuditStore
from neoavlod.database import Database
from neoavlod.models import AuditEvent
from neoavlod.settings import Settings

logger = logging.getLogger(__name__)
LOCK_ID = 1313165108


class AuditArchiver:
    def __init__(
        self, database: Database, store: AuditStore, *, batch_size: int = MAX_BATCH
    ) -> None:
        if not 1 <= batch_size <= MAX_BATCH:
            raise ValueError("Invalid archive batch size")
        self.database, self.store, self.batch_size = database, store, batch_size
        self.stopped = asyncio.Event()

    async def once(self, *, force: bool = False) -> int:
        async with self.database.engine.connect() as lease:
            locked = await lease.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": LOCK_ID})
            await lease.commit()
            if not locked:
                return 0
            try:
                await anyio.to_thread.run_sync(self.store.clean_pending)
                async with self.database.session() as session:
                    oldest = await session.scalar(
                        select(AuditEvent).order_by(AuditEvent.id).limit(1)
                    )
                    if oldest is None:
                        return 0
                    rows = list(
                        (
                            await session.scalars(
                                select(AuditEvent)
                                .where(AuditEvent.local_day == oldest.local_day)
                                .order_by(AuditEvent.id)
                                .limit(self.batch_size)
                            )
                        ).all()
                    )
                    if (
                        not force
                        and len(rows) < self.batch_size
                        and oldest.occurred_at > datetime.now(UTC) - timedelta(minutes=5)
                    ):
                        return 0
                    proof = await anyio.to_thread.run_sync(
                        self.store.persist, oldest.local_day, [row.body for row in rows]
                    )
                    count = await session.scalar(
                        text(
                            "SELECT audit.archive_commit(:id,:day,:name,:ids,:plain,:cipher,:key)"
                        ),
                        {
                            "id": uuid.uuid4(),
                            "day": proof.day,
                            "name": proof.object_name,
                            "ids": proof.ids,
                            "plain": proof.plain_hash,
                            "cipher": proof.cipher_hash,
                            "key": proof.key_id,
                        },
                    )
                    await session.commit()
                    assert isinstance(count, int)
                    return count
            finally:
                await lease.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": LOCK_ID})
                await lease.commit()

    async def run(self) -> None:
        while not self.stopped.is_set():
            try:
                count = await self.once()
                Path("/tmp/neoavlod-audit-heartbeat").touch()
                if count:
                    continue
            except Exception:
                # Do not print SQL, manifests, filenames, keys or personal details.
                logger.error("Audit archive failed; unarchived evidence retained")
            with anyio.move_on_after(15):
                await self.stopped.wait()


def main() -> None:
    parser = argparse.ArgumentParser(description="Immutable audit archival worker")
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()

    async def run() -> None:
        settings = Settings()
        database = Database(settings)
        worker = AuditArchiver(database, AuditStore(settings, create=True))
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, worker.stopped.set)
        try:
            if args.once:
                print(f"Archived events: {await worker.once(force=True)}")
            else:
                await worker.run()
        finally:
            await database.close()

    asyncio.run(run())


if __name__ == "__main__":
    main()
