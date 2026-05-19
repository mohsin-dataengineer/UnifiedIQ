"""Structured JSON logging and the OpenTelemetry integration slot.

Logs are single-line JSON so the standard observability fields
(request_id, user_email, latency_ms, tokens_in, tokens_out) stay queryable.
"""

from __future__ import annotations

import json
import logging
import sys
from typing import Any

_STD_FIELDS = {
    "request_id",
    "user_email",
    "latency_ms",
    "tokens_in",
    "tokens_out",
}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field in _STD_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())


def setup_telemetry(app: Any) -> None:
    """OpenTelemetry slot.

    Intentionally a no-op until an exporter is provisioned. Instrument the
    FastAPI app and outbound httpx client here when OTel is wired.
    """
    return None
