from typing import Literal

from pydantic import SecretStr, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


class ConfigError(Exception):
    """Invalid or missing configuration; the message is safe to show to the user."""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    telegram_bot_token: SecretStr
    database_url: SecretStr
    opendota_api_key: SecretStr | None = None

    llm_base_url: str = "http://localhost:1234/v1"
    llm_model: str | None = None  # the LLM is optional: commands work without it
    llm_api_key: SecretStr = SecretStr("lm-studio")
    llm_timeout: float = 120

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    log_format: Literal["text", "json"] = "text"


def load_settings() -> Settings:
    try:
        return Settings()
    except ValidationError as exc:
        lines = [
            f"  {'.'.join(str(p) for p in err['loc']).upper()}: {err['msg']}"
            for err in exc.errors()
        ]
        details = "\n".join(lines)
        raise ConfigError(f"Invalid configuration (see .env.example):\n{details}") from None
