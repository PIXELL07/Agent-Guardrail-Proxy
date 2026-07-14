"""
Structured (JSON) logging.

Plain-text logs are fine for local dev but painful to query once you're
running in production behind something like Railway/Datadog/CloudWatch.
Emitting JSON means every log line is immediately queryable/filterable by
field (agent_id, decision, tier) without regex log-scraping.
"""

from __future__ import annotations

import json
import logging
import sys
import time


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": time.time(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Any extra fields passed via logger.info(msg, extra={...}) get
        # merged in, so callers can attach structured context
        # (agent_id, tool_name, decision, etc.) without string formatting.
        for key, value in record.__dict__.items():
            if key in (
                "name", "msg", "args", "levelname", "levelno", "pathname",
                "filename", "module", "exc_info", "exc_text", "stack_info",
                "lineno", "funcName", "created", "msecs", "relativeCreated",
                "thread", "threadName", "processName", "process", "message",
            ):
                continue
            payload[key] = value
        return json.dumps(payload)


def configure_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)


logger = logging.getLogger("guardrail")
