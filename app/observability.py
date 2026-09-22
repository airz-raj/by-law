"""Structured logging set up so Cloud Logging can parse it.

One JSON object per line, with the request id and route where a request is
in flight. Document text and model output never reach a log record.
"""

from __future__ import annotations

import json
import logging
import sys
from typing import Any

#: Attributes LogRecord always carries, which are not ours to emit.
_STANDARD_ATTRS = frozenset(
    vars(logging.LogRecord("", 0, "", 0, "", None, None)).keys()
    | {"message", "asctime", "taskName"}
)

#: Cloud Logging reads this key as the severity of the entry.
_SEVERITY_KEY = "severity"


class JsonFormatter(logging.Formatter):
    """Render a log record as one JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        """Return *record* as a single-line JSON object."""
        payload: dict[str, Any] = {
            _SEVERITY_KEY: record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
        }
        for key, value in vars(record).items():
            if key not in _STANDARD_ATTRS and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["error_type"] = getattr(record.exc_info[0], "__name__", "error")
        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(level: str = "INFO") -> None:
    """Send structured logs to stdout, replacing any existing handlers."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)


def get_logger(name: str) -> logging.Logger:
    """Return the logger for *name*."""
    return logging.getLogger(name)
