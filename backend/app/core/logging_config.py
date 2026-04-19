"""JSON/텍스트 로깅 초기화."""

from __future__ import annotations

import logging
import sys

from pythonjsonlogger import jsonlogger

from app.core.config import settings
from app.core.request_context import request_id_ctx


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx.get()
        return True


def setup_logging() -> None:
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))

    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(RequestIdFilter())

    if settings.log_json:
        fmt = jsonlogger.JsonFormatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s %(request_id)s",
            rename_fields={"levelname": "level", "asctime": "timestamp"},
        )
    else:
        fmt = logging.Formatter(
            "%(asctime)s | %(levelname)s | %(request_id)s | %(name)s | %(message)s",
        )
    handler.setFormatter(fmt)
    root.addHandler(handler)

    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
