"""WebSocket 연결 관리: 사용자별 다중 연결(멀티 디바이스 MVP 대비)."""

from __future__ import annotations

from typing import Any

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        # user_id -> 연결된 WebSocket 목록
        self._by_user: dict[int, list[WebSocket]] = {}

    def register(self, user_id: int, websocket: WebSocket) -> None:
        """WebSocket은 라우터에서 이미 accept 한 뒤 등록."""
        self._by_user.setdefault(user_id, []).append(websocket)

    def disconnect(self, user_id: int, websocket: WebSocket) -> None:
        conns = self._by_user.get(user_id, [])
        if websocket in conns:
            conns.remove(websocket)
        if not conns:
            self._by_user.pop(user_id, None)

    def is_online(self, user_id: int) -> bool:
        return bool(self._by_user.get(user_id))

    async def send_json_to_user(self, user_id: int, payload: dict[str, Any]) -> None:
        dead: list[WebSocket] = []
        for ws in self._by_user.get(user_id, []):
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(user_id, ws)

    async def broadcast_to_users(self, user_ids: list[int], payload: dict[str, Any]) -> None:
        for uid in set(user_ids):
            await self.send_json_to_user(uid, payload)


# 앱 전역 싱글톤 (단일 프로세스 MVP)
connection_manager = ConnectionManager()
