import json
import logging
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

chat_id: ContextVar[int | None] = ContextVar("chat_id", default=None)
user_id: ContextVar[int | None] = ContextVar("user_id", default=None)
request_id: ContextVar[str | None] = ContextVar("request_id", default=None)

_CONTEXT_FIELDS: dict[str, ContextVar[Any]] = {
    "chat_id": chat_id,
    "user_id": user_id,
    "request_id": request_id,
}


def _context() -> dict[str, int | str]:
    values = {name: var.get() for name, var in _CONTEXT_FIELDS.items()}
    return {name: value for name, value in values.items() if value is not None}


class TextFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        parts = [
            self.formatTime(record),
            record.levelname,
            record.name,
            record.getMessage(),
            *(f"{k}={v}" for k, v in _context().items()),
        ]
        line = " ".join(parts)
        if record.exc_info:
            line += "\n" + self.formatException(record.exc_info)
        return line


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        data: dict[str, object] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            **_context(),
        }
        if record.exc_info:
            data["exc"] = self.formatException(record.exc_info)
        return json.dumps(data, ensure_ascii=False)


def setup_logging(level: str = "INFO", fmt: str = "text") -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter() if fmt == "json" else TextFormatter())
    logging.basicConfig(level=level, handlers=[handler], force=True)
    # httpx logs full request URLs at INFO, which would include the OpenDota api_key query param.
    logging.getLogger("httpx").setLevel(logging.WARNING)
