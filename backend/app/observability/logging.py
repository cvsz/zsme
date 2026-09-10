from __future__ import annotations

import json
import logging
import sys
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

_SENSITIVE_PARTS = (
    "authorization",
    "cookie",
    "password",
    "secret",
    "token",
    "credential",
    "private_key",
    "privatekey",
    "api_key",
    "apikey",
)


def _is_sensitive(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return any(part in normalized for part in _SENSITIVE_PARTS)


def redact_context(value: Any, *, key: str | None = None) -> Any:
    if key is not None and _is_sensitive(key):
        return "[REDACTED]"
    if isinstance(value, Mapping):
        return {
            str(item_key): redact_context(item_value, key=str(item_key))
            for item_key, item_value in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact_context(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


class JsonFormatter(logging.Formatter):
    """Emit one redacted, machine-readable event per log line."""

    def format(self, record: logging.LogRecord) -> str:
        context = getattr(record, "zsme_context", {})
        event = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname.lower(),
            "logger": record.name,
            "event": getattr(record, "zsme_event", record.getMessage()),
            "message": record.getMessage(),
            **redact_context(context),
        }
        if record.exc_info:
            event["exception"] = self.formatException(record.exc_info)
        return json.dumps(event, separators=(",", ":"), ensure_ascii=False)


_logger = logging.getLogger("zsme")


def configure_logging() -> None:
    """Install the redacting formatter without duplicating handlers."""
    if not _logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        _logger.addHandler(handler)
        _logger.propagate = False
    _logger.setLevel(logging.INFO)


def log_request(
    *,
    method: str,
    path: str,
    status_code: int,
    duration_ms: float,
    correlation_id: str,
    tenant_id: str | None = None,
    user_id: str | None = None,
    outcome: str = "completed",
) -> None:
    configure_logging()
    level = (
        logging.ERROR
        if status_code >= 500
        else logging.WARNING
        if status_code >= 400
        else logging.INFO
    )
    _logger.log(
        level,
        "HTTP request completed",
        extra={
            "zsme_event": "http.request",
            "zsme_context": {
                "method": method,
                "path": path,
                "status_code": status_code,
                "duration_ms": round(duration_ms, 3),
                "correlation_id": correlation_id,
                "tenant_id": tenant_id,
                "user_id": user_id,
                "outcome": outcome,
            },
        },
    )


__all__ = ["JsonFormatter", "configure_logging", "log_request", "redact_context"]
