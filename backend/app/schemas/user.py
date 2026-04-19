from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class UserPublic(BaseModel):
    id: int
    username: str
    nickname: str
    status_message: str
    avatar_url: str | None
    last_seen_at: datetime | None
    # 온라인: WebSocket 연결 중이면 True (별도 필드는 WS 이벤트로만 전달 가능; REST는 last_seen만)
    model_config = {"from_attributes": True}


class UserMeOut(UserPublic):
    email: EmailStr


class UserUpdateIn(BaseModel):
    nickname: str | None = Field(default=None, max_length=128)
    status_message: str | None = Field(default=None, max_length=512)
