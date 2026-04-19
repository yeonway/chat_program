"""SlowAPI 리미터 (프로세스 메모리 저장 — 다중 워커 시 Redis URL 권장)."""

from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request


def _client_key(request: Request) -> str:
    """프록시 뒤에서 X-Forwarded-For 첫 번째 IP 사용."""
    xff = request.headers.get("X-Forwarded-For")
    if xff:
        return xff.split(",")[0].strip() or get_remote_address(request)
    return get_remote_address(request)


limiter = Limiter(
    key_func=_client_key,
    default_limits=["600/minute"],
    storage_uri="memory://",
)
