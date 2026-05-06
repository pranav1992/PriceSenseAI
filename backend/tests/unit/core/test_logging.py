import json
import logging

import pytest

from backend.app.core.logging import (
    DEFAULT_LOG_FILE_BACKUP_COUNT,
    DEFAULT_LOG_FILE_MAX_BYTES,
    JsonFormatter,
    build_logging_config,
)

pytestmark = pytest.mark.unit


def test_json_formatter_outputs_expected_log_contract():
    record = logging.LogRecord(
        name="backend.access",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="HTTP request completed",
        args=(),
        exc_info=None,
    )
    record.request_id = "request-id"
    record.method = "GET"
    record.path = "/"
    record.status_code = 200
    record.duration_ms = 1.23

    payload = json.loads(JsonFormatter().format(record))

    assert payload["level"] == "INFO"
    assert payload["logger"] == "backend.access"
    assert payload["message"] == "HTTP request completed"
    assert payload["request_id"] == "request-id"
    assert payload["method"] == "GET"
    assert payload["path"] == "/"
    assert payload["status_code"] == 200
    assert payload["duration_ms"] == 1.23
    assert "timestamp" in payload


def test_file_logging_is_disabled_without_development_env(monkeypatch):
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("LOG_TO_FILE", raising=False)

    config = build_logging_config()

    assert "file" not in config["handlers"]
    assert config["root"]["handlers"] == ["console"]


def test_file_logging_is_enabled_for_development_env(monkeypatch, tmp_path):
    log_file_path = tmp_path / "backend.log"
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("LOG_FILE_PATH", str(log_file_path))
    monkeypatch.delenv("LOG_TO_FILE", raising=False)

    config = build_logging_config()

    assert config["root"]["handlers"] == ["console", "file"]
    assert config["handlers"]["file"] == {
        "class": "logging.handlers.RotatingFileHandler",
        "formatter": "json",
        "filename": str(log_file_path),
        "maxBytes": DEFAULT_LOG_FILE_MAX_BYTES,
        "backupCount": DEFAULT_LOG_FILE_BACKUP_COUNT,
        "encoding": "utf-8",
    }


def test_file_logging_can_be_enabled_explicitly(monkeypatch, tmp_path):
    log_file_path = tmp_path / "backend.log"
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.setenv("LOG_TO_FILE", "true")
    monkeypatch.setenv("LOG_FILE_PATH", str(log_file_path))
    monkeypatch.setenv("LOG_FILE_MAX_BYTES", "1024")
    monkeypatch.setenv("LOG_FILE_BACKUP_COUNT", "2")

    config = build_logging_config()

    assert config["root"]["handlers"] == ["console", "file"]
    assert config["handlers"]["file"]["filename"] == str(log_file_path)
    assert config["handlers"]["file"]["maxBytes"] == 1024
    assert config["handlers"]["file"]["backupCount"] == 2


def test_file_logging_can_be_disabled_explicitly_in_development(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("LOG_TO_FILE", "false")

    config = build_logging_config()

    assert "file" not in config["handlers"]
    assert config["root"]["handlers"] == ["console"]
