"""실시간 WebSocket: 첫 메시지 JWT 인증, presence, ping."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from jose import JWTError
from sqlalchemy import select

from app.core.config import settings
from app.core.security import decode_token, verify_token_type
from app.database import AsyncSessionLocal
from app.models.user import User
from app.services.conversations import peer_user_ids
from app.services.ws_manager import connection_manager

router = APIRouter(tags=["websocket"])
log = logging.getLogger("app.ws")


def _access_user_id_from_token(token: str) -> int | None:
    try:
        payload = decode_token(token)
        if not verify_token_type(payload, "access"):
            return None
        return int(payload["sub"])
    except (JWTError, ValueError, KeyError, TypeError):
        return None


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """
    연결 후 첫 JSON 메시지로 인증 (쿼리스트링에 토큰을 넣지 않음).

    클라이언트: {"type":"auth","token":"<access_jwt>"}
    서버: {"type":"auth.ok"} 또는 {"type":"auth.error","detail":"..."} 후 종료.
    """
    await websocket.accept()
    try:
        raw = await asyncio.wait_for(websocket.receive_json(), timeout=settings.ws_auth_timeout_seconds)
    except asyncio.TimeoutError:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    except WebSocketDisconnect:
        return

    if not isinstance(raw, dict) or raw.get("type") != "auth":
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    token = raw.get("token")
    if not isinstance(token, str) or not token.strip():
        await websocket.send_json({"type": "auth.error", "detail": "missing_token"})
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    user_id = _access_user_id_from_token(token.strip())
    if user_id is None:
        await websocket.send_json({"type": "auth.error", "detail": "invalid_token"})
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    peers: list[int] = []
    async with AsyncSessionLocal() as db:
        r = await db.execute(select(User).where(User.id == user_id))
        row = r.scalar_one_or_none()
        if row is None:
            await websocket.send_json({"type": "auth.error", "detail": "user_not_found"})
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        peers = await peer_user_ids(db, user_id)
        row.last_seen_at = datetime.now(timezone.utc)
        await db.commit()

    try:
        await websocket.send_json({"type": "auth.ok"})
    except Exception:
        log.exception("ws_auth_ok_send_failed")
        return

    connection_manager.register(user_id, websocket)
    await connection_manager.broadcast_to_users(
        peers,
        {"type": "presence.update", "user_id": user_id, "online": True},
    )
    try:
        while True:
            raw2 = await websocket.receive_json()
            if raw2.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    finally:
        connection_manager.disconnect(user_id, websocket)
        peers_off: list[int] = []
        async with AsyncSessionLocal() as db:
            r = await db.execute(select(User).where(User.id == user_id))
            u = r.scalar_one_or_none()
            if u:
                u.last_seen_at = datetime.now(timezone.utc)
                await db.commit()
            peers_off = await peer_user_ids(db, user_id)
        if not connection_manager.is_online(user_id):
            await connection_manager.broadcast_to_users(
                peers_off,
                {"type": "presence.update", "user_id": user_id, "online": False},
            )
