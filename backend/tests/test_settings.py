from pathlib import Path

import pytest
from pydantic import ValidationError

from neoavlod.settings import Settings


def test_environment_variables_are_loaded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEOAVLOD_ENVIRONMENT", "test")
    monkeypatch.setenv("NEOAVLOD_APP_NAME", "Custom LMS")
    assert Settings().environment == "test"
    assert Settings().app_name == "Custom LMS"


def test_dotenv_is_loaded_and_environment_overrides_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".env").write_text("NEOAVLOD_APP_NAME=Dotenv LMS\n", encoding="utf-8")
    assert Settings().app_name == "Dotenv LMS"
    monkeypatch.setenv("NEOAVLOD_APP_NAME", "Environment LMS")
    assert Settings().app_name == "Environment LMS"


def test_invalid_environment_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NEOAVLOD_ENVIRONMENT", "invalid")
    with pytest.raises(ValidationError):
        Settings()


def test_production_debug_is_rejected() -> None:
    with pytest.raises(ValidationError, match="debug"):
        Settings(environment="production", debug=True)


def test_empty_name_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(app_name="")
