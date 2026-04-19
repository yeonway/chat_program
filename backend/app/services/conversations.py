"""1:1 대화 조회/생성 헬퍼."""

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation, ConversationParticipant
from app.models.message import Message
from app.models.user import User


async def find_direct_conversation(db: AsyncSession, a_id: int, b_id: int) -> Conversation | None:
    """두 사용자만 참가한 direct 대화가 있으면 반환 (그룹 채팅과 혼동 없음)."""
    if a_id == b_id:
        return None
    result = await db.execute(
        select(Conversation)
        .join(ConversationParticipant, ConversationParticipant.conversation_id == Conversation.id)
        .where(Conversation.type == "direct", ConversationParticipant.user_id == a_id)
    )
    for conv in result.scalars().unique().all():
        uids = set(await participant_ids(db, conv.id))
        if uids == {a_id, b_id}:
            return conv
    return None


async def create_direct_conversation(db: AsyncSession, a_id: int, b_id: int) -> Conversation:
    conv = Conversation(type="direct")
    db.add(conv)
    await db.flush()
    db.add_all(
        [
            ConversationParticipant(conversation_id=conv.id, user_id=a_id),
            ConversationParticipant(conversation_id=conv.id, user_id=b_id),
        ]
    )
    return conv


async def get_or_create_direct(db: AsyncSession, current_id: int, other_id: int) -> Conversation:
    if other_id == current_id:
        raise ValueError("자기 자신과는 대화할 수 없습니다.")
    existing = await find_direct_conversation(db, current_id, other_id)
    if existing:
        return existing
    other = await db.get(User, other_id)
    if other is None:
        raise ValueError("상대 사용자를 찾을 수 없습니다.")
    return await create_direct_conversation(db, current_id, other_id)


async def user_in_conversation(db: AsyncSession, user_id: int, conversation_id: int) -> bool:
    r = await db.execute(
        select(ConversationParticipant.id).where(
            and_(
                ConversationParticipant.conversation_id == conversation_id,
                ConversationParticipant.user_id == user_id,
            )
        )
    )
    return r.scalar_one_or_none() is not None


async def participant_ids(db: AsyncSession, conversation_id: int) -> list[int]:
    r = await db.execute(
        select(ConversationParticipant.user_id).where(ConversationParticipant.conversation_id == conversation_id)
    )
    return list(r.scalars().all())


async def peer_user_ids(db: AsyncSession, user_id: int) -> list[int]:
    """같은 대화방에 있는 다른 사용자 ID 목록 (중복 제거)."""
    sub = select(ConversationParticipant.conversation_id).where(ConversationParticipant.user_id == user_id)
    r = await db.execute(
        select(ConversationParticipant.user_id).where(
            ConversationParticipant.conversation_id.in_(sub),
            ConversationParticipant.user_id != user_id,
        )
    )
    return list({x for x in r.scalars().all()})


async def other_user_in_direct(db: AsyncSession, conversation_id: int, me_id: int) -> User | None:
    r = await db.execute(
        select(User)
        .join(ConversationParticipant, ConversationParticipant.user_id == User.id)
        .where(
            ConversationParticipant.conversation_id == conversation_id,
            User.id != me_id,
        )
    )
    return r.scalar_one_or_none()
