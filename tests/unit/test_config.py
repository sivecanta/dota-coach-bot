import pytest

from dota_coach.config import ConfigError, Settings, load_settings

REQUIRED = {
    "TELEGRAM_BOT_TOKEN": "123:secret-token",
    "DATABASE_URL": "postgresql+asyncpg://u:p@localhost/db",
    "LLM_MODEL": "gemma",
}


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir("/")  # never pick up the developer's real .env
    for name in [*REQUIRED, "OPENDOTA_API_KEY", "LLM_BASE_URL", "LLM_TIMEOUT", "LOG_LEVEL"]:
        monkeypatch.delenv(name, raising=False)


def set_required(monkeypatch: pytest.MonkeyPatch) -> None:
    for name, value in REQUIRED.items():
        monkeypatch.setenv(name, value)


def test_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    set_required(monkeypatch)
    s = load_settings()
    assert s.llm_base_url == "http://localhost:1234/v1"
    assert s.llm_timeout == 120
    assert s.log_level == "INFO"
    assert s.log_format == "text"
    assert s.opendota_api_key is None


def test_parses_values(monkeypatch: pytest.MonkeyPatch) -> None:
    set_required(monkeypatch)
    monkeypatch.setenv("LLM_TIMEOUT", "30.5")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    s = load_settings()
    assert s.llm_timeout == 30.5
    assert s.log_level == "DEBUG"


def test_missing_token_is_a_readable_error(monkeypatch: pytest.MonkeyPatch) -> None:
    set_required(monkeypatch)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN")
    with pytest.raises(ConfigError, match="TELEGRAM_BOT_TOKEN"):
        load_settings()


def test_invalid_value_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    set_required(monkeypatch)
    monkeypatch.setenv("LOG_LEVEL", "LOUD")
    with pytest.raises(ConfigError, match="LOG_LEVEL"):
        load_settings()


def test_secrets_are_not_printed(monkeypatch: pytest.MonkeyPatch) -> None:
    set_required(monkeypatch)
    s = load_settings()
    assert "secret-token" not in repr(s)
    assert "secret-token" not in str(s)
    assert isinstance(s, Settings)
