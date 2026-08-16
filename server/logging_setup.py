"""结构化日志 · 请求级 request-id 透传。

日志统一携带 request_id，便于在分布式/容器环境中按请求串联；
log_json=True 时输出单行 JSON，可直接被 Loki/ELK 采集。
"""

from __future__ import annotations

import contextvars
import json
import logging
import sys
from logging.handlers import RotatingFileHandler

from .config import settings

request_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")

_LOGGER_NAME = "uzi"
_configured = False


class RequestIDFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx.get()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "request_id": getattr(record, "request_id", "-"),
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def _build_formatter() -> logging.Formatter:
    if settings.log_json:
        return JsonFormatter()
    fmt = "%(asctime)s | %(levelname)-7s | rid=%(request_id)s | %(name)s | %(message)s"
    return logging.Formatter(fmt, datefmt="%Y-%m-%d %H:%M:%S")


def setup_logging() -> logging.Logger:
    global _configured
    logger = logging.getLogger(_LOGGER_NAME)
    if _configured:
        return logger

    logger.setLevel(settings.log_level.upper())
    logger.handlers.clear()
    logger.propagate = False

    formatter = _build_formatter()
    rid_filter = RequestIDFilter()

    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(formatter)
    stream.addFilter(rid_filter)
    logger.addHandler(stream)

    if settings.log_file:
        fh = RotatingFileHandler(settings.log_file, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8")
        fh.setFormatter(formatter)
        fh.addFilter(rid_filter)
        logger.addHandler(fh)

    _configured = True
    return logger


def get_logger(name: str | None = None) -> logging.Logger:
    if name:
        return logging.getLogger(f"{_LOGGER_NAME}.{name}")
    return logging.getLogger(_LOGGER_NAME)
