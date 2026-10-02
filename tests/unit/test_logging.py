import json
import logging

from dota_coach import logging as app_logging


def make_record(msg: str = "hello") -> logging.LogRecord:
    return logging.LogRecord("dota_coach", logging.INFO, __file__, 1, msg, None, None)


def test_text_format_includes_context() -> None:
    tokens = [app_logging.chat_id.set(-100), app_logging.request_id.set("r1")]
    try:
        line = app_logging.TextFormatter().format(make_record())
    finally:
        app_logging.chat_id.reset(tokens[0])
        app_logging.request_id.reset(tokens[1])
    assert "INFO dota_coach hello" in line
    assert "chat_id=-100" in line
    assert "request_id=r1" in line
    assert "user_id" not in line


def test_json_format() -> None:
    data = json.loads(app_logging.JsonFormatter().format(make_record("hi")))
    assert data["msg"] == "hi"
    assert data["level"] == "INFO"
    assert "chat_id" not in data
