"""회원가입, 로그인, JWT Refresh, 로그아웃."""

import hashlib
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from jose import JWTError
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
    verify_token_type,
)
from app.core.rate_limit import limiter
from app.database import get_db
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.schemas.auth import LoginIn, MessageOut, RefreshIn, RegisterIn, TokenOut

router = APIRouter()


def _refresh_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@router.post("/register", response_model=TokenOut)
@limiter.limit("5/minute")
async def register(request: Request, body: RegisterIn, db: AsyncSession = Depends(get_db)) -> TokenOut:
    """신규 사용자 등록 후 바로 토큰 발급."""
    exists = await db.execute(select(User.id).where(or_(User.email == body.email, User.username == body.username)))
    if exists.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="이메일 또는 사용자명이 이미 사용 중입니다.")
    user = User(
        email=body.email,
        username=body.username,
        password_hash=hash_password(body.password),
        nickname=body.nickname,
    )
    db.add(user)
    await db.flush()
    access = create_access_token(user.id)
    refresh = create_refresh_token(user.id)
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=_refresh_hash(refresh),
            expires_at=datetime.fromtimestamp(decode_token(refresh)["exp"], tz=timezone.utc),
        )
    )
    await db.commit()
    return TokenOut(access_token=access, refresh_token=refresh)


@router.post("/login", response_model=TokenOut)
@limiter.limit("15/minute")
async def login(request: Request, body: LoginIn, db: AsyncSession = Depends(get_db)) -> TokenOut:
    """username 또는 email + 비밀번호 로그인."""
    q = select(User).where(or_(User.username == body.login, User.email == body.login))
    result = await db.execute(q)
    user = result.scalar_one_or_none()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="로그인 정보가 올바르지 않습니다.")
    access = create_access_token(user.id)
    refresh = create_refresh_token(user.id)
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=_refresh_hash(refresh),
            expires_at=datetime.fromtimestamp(decode_token(refresh)["exp"], tz=timezone.utc),
        )
    )
    await db.commit()
    return TokenOut(access_token=access, refresh_token=refresh)


@router.post("/refresh", response_model=TokenOut)
@limiter.limit("60/minute")
async def refresh_token(request: Request, body: RefreshIn, db: AsyncSession = Depends(get_db)) -> TokenOut:
    """Refresh JWT로 새 Access(+선택적 Refresh) 발급. DB에 저장된 해시와 대조."""
    try:
        payload = decode_token(body.refresh_token)
        if not verify_token_type(payload, "refresh"):
            raise HTTPException(status_code=401, detail="Refresh 토큰이 아닙니다.")
        user_id = int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise HTTPException(status_code=401, detail="Refresh 토큰이 유효하지 않습니다.")
    th = _refresh_hash(body.refresh_token)
    r = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == th,
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None),
        )
    )
    row = r.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=401, detail="Refresh 토큰이 폐기되었거나 없습니다.")
    if row.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Refresh 토큰이 만료되었습니다.")
    access = create_access_token(user_id)
    new_refresh = create_refresh_token(user_id)
    row.revoked_at = datetime.now(timezone.utc)
    db.add(
        RefreshToken(
            user_id=user_id,
            token_hash=_refresh_hash(new_refresh),
            expires_at=datetime.fromtimestamp(decode_token(new_refresh)["exp"], tz=timezone.utc),
        )
    )
    await db.commit()
    return TokenOut(access_token=access, refresh_token=new_refresh)


@router.post("/logout", response_model=MessageOut)
@limiter.limit("60/minute")
async def logout(request: Request, body: RefreshIn, db: AsyncSession = Depends(get_db)) -> MessageOut:
    """해당 Refresh 토큰을 서버에서 폐기."""
    th = _refresh_hash(body.refresh_token)
    r = await db.execute(select(RefreshToken).where(RefreshToken.token_hash == th))
    row = r.scalar_one_or_none()
    if row and row.revoked_at is None:
        row.revoked_at = datetime.now(timezone.utc)
        await db.commit()
    return MessageOut(detail="로그아웃되었습니다.")
