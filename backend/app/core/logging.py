import json
import logging
import logging.config
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

LOG_FORMAT_JSON = "json"
LOG_FORMAT_TEXT = "text"
DEFAULT_LOG_FILE_PATH = "logs/backend.log"
DEFAULT_LOG_FILE_MAX_BYTES = 10 * 1024 * 1024
DEFAULT_LOG_FILE_BACKUP_COUNT = 5


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        for field in (
            "request_id",
            "method",
            "path",
            "status_code",
            "duration_ms",
            "error_code",
        ):
            if hasattr(record, field):
                payload[field] = getattr(record, field)

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str)


def configure_logging() -> None:
    logging.config.dictConfig(build_logging_config())


def build_logging_config() -> dict[str, Any]:
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    log_format = os.getenv("LOG_FORMAT", LOG_FORMAT_JSON).lower()
    formatter_name = "json" if log_format == LOG_FORMAT_JSON else "text"

    handlers: dict[str, dict[str, Any]] = {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": formatter_name,
            "stream": "ext://sys.stdout",
        }
    }
    root_handlers = ["console"]

    if should_enable_file_logging():
        log_file_path = Path(os.getenv("LOG_FILE_PATH", DEFAULT_LOG_FILE_PATH))
        log_file_path.parent.mkdir(parents=True, exist_ok=True)
        handlers["file"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "formatter": formatter_name,
            "filename": str(log_file_path),
            "maxBytes": get_int_env("LOG_FILE_MAX_BYTES", DEFAULT_LOG_FILE_MAX_BYTES),
            "backupCount": get_int_env(
                "LOG_FILE_BACKUP_COUNT", DEFAULT_LOG_FILE_BACKUP_COUNT
            ),
            "encoding": "utf-8",
        }
        root_handlers.append("file")

    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {"()": JsonFormatter},
            "text": {
                "format": "%(asctime)s %(levelname)s [%(name)s] %(message)s"
            },
        },
        "handlers": handlers,
        "root": {
            "handlers": root_handlers,
            "level": log_level,
        },
        "loggers": {
            "backend": {
                "level": log_level,
                "propagate": True,
            },
            "uvicorn.access": {
                "level": "WARNING",
            },
        },
    }


def should_enable_file_logging() -> bool:
    log_to_file = os.getenv("LOG_TO_FILE")
    if log_to_file is not None:
        return parse_bool(log_to_file)

    app_env = os.getenv("APP_ENV") or os.getenv("ENVIRONMENT") or ""
    return app_env.lower() in {"dev", "development", "local"}


def parse_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def get_int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default

    try:
        return int(value)
    except ValueError:
        return default
