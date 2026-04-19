from datetime import datetime

from pydantic import BaseModel, Field


class MessageCreateIn(BaseModel):
    body: str = Field(default="", max_length=32000)
    file_id: int | None = Field(default=None, ge=1)


class MessageOut(BaseModel):
    id: int
    conversation_id: int
    sender_id: int
    body: str
    file_id: int | None
    created_at: datetime
    edited_at: datetime | None
    deleted_at: datetime | None
    read_by_me: bool = False
    read_by_peer: bool = False
    model_config = {"from_attributes": True}


class MarkReadIn(BaseModel):
    """이 메시지까지(포함) 읽음 처리."""

    up_to_message_id: int = Field(ge=1)
