import io
import json
import sys
from typing import Any

import anyio
import pytest

from neoavlod.cli import main as cli_main
from neoavlod.database import Database
from neoavlod.services.telegram import TelegramClient

pytestmark = pytest.mark.anyio


async def test_cli_worker_once_clean(
    model_database: Database,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def mock_call(
        self: TelegramClient, method: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        return {"ok": True, "result": []}

    monkeypatch.setattr(TelegramClient, "call", mock_call)
    monkeypatch.setattr(sys, "argv", ["neoavlod", "worker", "--once"])

    captured_out = io.StringIO()
    captured_err = io.StringIO()
    monkeypatch.setattr(sys, "stdout", captured_out)
    monkeypatch.setattr(sys, "stderr", captured_err)

    code = await anyio.to_thread.run_sync(cli_main)
    stderr = captured_err.getvalue()
    stdout = captured_out.getvalue()
    assert code == 0, f"CLI error: {stderr}"

    data = json.loads(stdout)
    assert "bot_processed" in data
    assert "outbox_processed" in data
    assert isinstance(data["bot_processed"], int)
    assert isinstance(data["outbox_processed"], int)
