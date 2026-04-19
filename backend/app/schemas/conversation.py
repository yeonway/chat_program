from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.message import MessageOut
from app.schemas.user import UserPublic


class DirectCreateIn(BaseModel):
    """1:1 대화 상대 사용자 ID."""

    other_user_id: int = Field(ge=1)


class ConversationListItem(BaseModel):
    id: int
    type: str
    other_user: UserPublic | None = None
    last_message: MessageOut | None = None
    unread_count: int = 0
    model_config = {"from_attributes": True}


class ConversationOut(BaseModel):
    id: int
    type: str
    created_at: datetime
    model_config = {"from_attributes": True}
