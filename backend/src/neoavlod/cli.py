import argparse
import asyncio
import getpass
import json
import signal
import sys

import httpx
from sqlalchemy.exc import IntegrityError

from neoavlod.database import Database
from neoavlod.errors import DomainError
from neoavlod.services.bootstrap import BootstrapInput, bootstrap_superadmin
from neoavlod.services.bot_settings import update_bot_token
from neoavlod.services.bot_worker import BotWorker
from neoavlod.services.outbox import OutboxWorker
from neoavlod.settings import Settings


async def run_bootstrap(inputs: BootstrapInput, password: str) -> dict[str, object]:
    database = Database(Settings())
    try:
        async with database.session() as session, session.begin():
            result = await bootstrap_superadmin(session, inputs, password)
            return {
                "id": str(result.staff.id),
                "username": result.staff.username,
                "created": result.created,
                "onboarding_payload": f"staff_{result.staff.auth_uuid}",
                "telegram_connected": result.staff.telegram_id is not None,
            }
    finally:
        await database.close()


async def run_set_bot_token(
    token: str,
    *,
    database: Database | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> dict[str, object]:
    settings = Settings()
    db = database or Database(settings)
    should_close = database is None
    try:
        async with db.session() as session:
            result = await update_bot_token(session, settings, token, transport=transport)
            return {
                "bot_username": result.bot_username,
                "version": result.version,
                "configured": True,
            }
    finally:
        if should_close:
            await db.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="NeoAvlod server administration")
    commands = parser.add_subparsers(dest="command", required=True)
    bootstrap = commands.add_parser(
        "bootstrap", help="Create the first superadmin without defaults"
    )
    for name in ("username", "phone", "first-name", "last-name"):
        bootstrap.add_argument(f"--{name}", required=True)
    bootstrap.add_argument(
        "--password-stdin", action="store_true", help="Read a secret from stdin"
    )

    bot_cmd = commands.add_parser("set-bot-token", help="Set Telegram bot token securely")
    bot_cmd.add_argument(
        "--token-stdin", action="store_true", help="Read bot token from stdin"
    )

    worker_cmd = commands.add_parser("bot-worker", help="Run Telegram bot background worker")
    worker_cmd.add_argument(
        "--once", action="store_true", help="Process available updates once and exit"
    )

    outbox_cmd = commands.add_parser(
        "outbox-worker", help="Run attendance notification outbox worker"
    )
    outbox_cmd.add_argument(
        "--once", action="store_true", help="Process pending notifications once and exit"
    )

    worker_unified = commands.add_parser(
        "worker", help="Run unified background worker singleton (bot polling and outbox)"
    )
    worker_unified.add_argument(
        "--once", action="store_true", help="Process available items once and exit"
    )

    args = parser.parse_args()

    if args.command == "worker":
        async def _run_worker_all() -> int:
            settings = Settings()
            database = Database(settings)
            try:
                bot_worker = BotWorker(database, settings)
                outbox_worker = OutboxWorker(database, settings)
                if args.once:
                    bot_processed = await bot_worker.run_single_iteration()
                    outbox_processed = await outbox_worker.run_single_iteration()
                    print(
                        json.dumps(
                            {
                                "bot_processed": bot_processed,
                                "outbox_processed": outbox_processed,
                            }
                        )
                    )
                else:
                    def _handle_stop() -> None:
                        bot_worker.stop()
                        outbox_worker.stop()

                    loop = asyncio.get_running_loop()
                    for sig in (signal.SIGTERM, signal.SIGINT):
                        try:
                            loop.add_signal_handler(sig, _handle_stop)
                        except (NotImplementedError, RuntimeError):
                            pass
                    await asyncio.gather(
                        bot_worker.run_forever(),
                        outbox_worker.run_forever(),
                    )
                return 0
            finally:
                await database.close()

        return asyncio.run(_run_worker_all())

    if args.command == "outbox-worker":
        async def _run_outbox() -> int:
            settings = Settings()
            database = Database(settings)
            try:
                worker = OutboxWorker(database, settings)
                if args.once:
                    processed = await worker.run_single_iteration()
                    print(json.dumps({"processed": processed}))
                else:
                    await worker.run_forever()
                return 0
            finally:
                await database.close()

        return asyncio.run(_run_outbox())

    if args.command == "bot-worker":
        async def _run_worker() -> int:
            settings = Settings()
            database = Database(settings)
            try:
                worker = BotWorker(database, settings)
                if args.once:
                    processed = await worker.run_single_iteration()
                    print(json.dumps({"processed": processed}))
                else:
                    await worker.run_forever()
                return 0
            finally:
                await database.close()

        return asyncio.run(_run_worker())

    if args.command == "set-bot-token":
        try:
            token = (
                sys.stdin.readline().rstrip("\r\n")
                if args.token_stdin
                else getpass.getpass("Telegram bot tokeni: ")
            )
            print(json.dumps(asyncio.run(run_set_bot_token(token)), ensure_ascii=False))
            return 0
        except DomainError as error:
            print(f"Xato: {error.message}", file=sys.stderr)
            return 1
        except Exception as error:
            print(f"Xato: {error}", file=sys.stderr)
            return 1

    try:
        inputs = BootstrapInput(
            username=args.username,
            phone=args.phone,
            first_name=args.first_name,
            last_name=args.last_name,
        )
        password = (
            sys.stdin.readline().rstrip("\r\n")
            if args.password_stdin
            else getpass.getpass("Yangi parol: ")
        )
        print(json.dumps(asyncio.run(run_bootstrap(inputs, password)), ensure_ascii=False))
        return 0
    except ValueError as error:
        print(f"Xato: {error}", file=sys.stderr)
        return 1
    except IntegrityError:
        print("Xato: username yoki telefon band", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
