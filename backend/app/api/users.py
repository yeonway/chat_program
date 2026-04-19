"""사용자 검색, 내 프로필, 아바타 업로드."""

import os
import uuid
from typing import Annotated

import aiofiles
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import CurrentUser
from app.database import get_db
from app.models.user import User
from app.schemas.user import UserMeOut, UserPublic, UserUpdateIn

router = APIRouter(prefix="/users", tags=["users"])

# 아바타 허용 MIME (확장자 화이트리스트와 함께 사용)
_AVATAR_MIMES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
_AVATAR_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif"}


@router.get("/search", response_model=list[UserPublic])
async def search_users(
    q: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: CurrentUser,
) -> list[UserPublic]:
    """닉네임/사용자명 부분 검색. 본인은 제외."""
    if len(q.strip()) < 2:
        return []
    pattern = f"%{q.strip()}%"
    result = await db.execute(
        select(User)
        .where(User.id != current.id)
        .where(or_(User.username.ilike(pattern), User.nickname.ilike(pattern)))
        .limit(30)
    )
    users = result.scalars().all()
    return [UserPublic.model_validate(u) for u in users]


@router.get("/me", response_model=UserMeOut)
async def me(current: CurrentUser) -> UserMeOut:
    return UserMeOut.model_validate(current)


@router.patch("/me", response_model=UserMeOut)
async def update_me(
    body: UserUpdateIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: CurrentUser,
) -> UserMeOut:
    if body.nickname is not None:
        current.nickname = body.nickname
    if body.status_message is not None:
        current.status_message = body.status_message
    await db.commit()
    await db.refresh(current)
    return UserMeOut.model_validate(current)


@router.post("/me/avatar", response_model=UserMeOut)
async def upload_avatar(
    db: Annotated[AsyncSession, Depends(get_db)],
    current: CurrentUser,
    file: UploadFile = File(...),
) -> UserMeOut:
    """프로필 이미지: 크기·MIME 검사 후 로컬 저장. URL은 클라이언트가 API 베이스와 조합."""
    if not file.filename:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "파일명이 없습니다.")
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in _AVATAR_EXT:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "허용되지 않은 이미지 형식입니다.")
    content_type = file.content_type or "application/octet-stream"
    if content_type not in _AVATAR_MIMES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "허용되지 않은 MIME 타입입니다.")
    data = await file.read()
    if len(data) > 5 * 1024 * 1024:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "5MB 이하만 업로드 가능합니다.")
    av_dir = os.path.join(settings.upload_dir, "avatars")
    os.makedirs(av_dir, exist_ok=True)
    name = f"{current.id}_{uuid.uuid4().hex}{ext}"
    path = os.path.join(av_dir, name)
    async with aiofiles.open(path, "wb") as f:
        await f.write(data)
    # API 베이스 URL 뒤에 붙이면 되는 상대 경로
    current.avatar_url = f"/users/avatar/{name}"
    await db.commit()
    await db.refresh(current)
    return UserMeOut.model_validate(current)


@router.get("/avatar/{filename}")
async def download_avatar(filename: str) -> FileResponse:
    """저장된 프로필 이미지 반환 (경로 조작 방지)."""
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not found")
    path = os.path.join(settings.upload_dir, "avatars", filename)
    if not os.path.isfile(path):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Not found")
    return FileResponse(path)
