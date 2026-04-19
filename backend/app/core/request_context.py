"""요청 단위 컨텍스트 (로깅용)."""

from __future__ import annotations

import contextvars

request_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")
