"""헬스·레디니스 (오케스트레이션·LB 프로브)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db

router = APIRouter(tags=["health"])


@router.get("/health/live")
async def health_live() -> dict[str, str]:
    """프로세스 살아 있음 (DB 미검사)."""
    return {"status": "ok"}


@router.get("/health/ready")
async def health_ready(db: Annotated[AsyncSession, Depends(get_db)]) -> dict[str, str]:
    """DB 연결 가능 여부."""
    await db.execute(text("SELECT 1"))
    return {"status": "ok"}


@router.get("/health")
async def health_legacy() -> dict[str, str]:
    """하위 호환 단순 헬스."""
    return {"status": "ok"}
