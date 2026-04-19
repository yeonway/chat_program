from pydantic import BaseModel, EmailStr, Field


class RegisterIn(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8, max_length=128)
    nickname: str = Field(min_length=1, max_length=128)


class LoginIn(BaseModel):
    """로그인: username 또는 email 중 하나 사용 가능 (서버에서 구분)."""

    login: str = Field(min_length=1, max_length=255, description="username 또는 email")
    password: str = Field(min_length=1, max_length=128)


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshIn(BaseModel):
    refresh_token: str


class MessageOut(BaseModel):
    detail: str
