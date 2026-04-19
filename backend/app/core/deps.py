"""FastAPI 의존성: 현재 사용자 로드."""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token, verify_token_type
from app.database import get_db
from app.models.user import User

security_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    db: Annotated[AsyncSession, Depends(get_db)],
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(security_scheme)],
) -> User:
    """Authorization: Bearer <access_token> 에서 사용자 조회."""
    if creds is None or not creds.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="인증이 필요합니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = creds.credentials
    try:
        payload = decode_token(token)
        if not verify_token_type(payload, "access"):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="액세스 토큰이 아닙니다.")
        user_id = int(payload.get("sub", 0))
    except (JWTError, ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="토큰이 유효하지 않습니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="사용자를 찾을 수 없습니다.")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
