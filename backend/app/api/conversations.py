"""대화 목록, 1:1 생성, 메시지 목록/전송, 읽음 처리 + WebSocket 브로드캐스트."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.deps import CurrentUser
from app.database import get_db
from app.models.conversation import Conversation, ConversationParticipant
from app.models.message import Message, MessageRead
from app.models.user import User
from app.schemas.conversation import ConversationListItem, ConversationOut, DirectCreateIn
from app.schemas.message import MarkReadIn, MessageCreateIn, MessageOut
from app.schemas.user import UserPublic
from app.services.conversations import (
    get_or_create_direct,
    other_user_in_direct,
    participant_ids,
    user_in_conversation,
)
from app.services.ws_manager import connection_manager

router = APIRouter(prefix="/conversations", tags=["conversations"])


async def _last_message(db: AsyncSession, conversation_id: int) -> Message | None:
    r = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id, Message.deleted_at.is_(None))
        .order_by(Message.id.desc())
        .limit(1)
    )
    return r.scalar_one_or_none()


async def _unread_count(db: AsyncSession, conversation_id: int, me_id: int) -> int:
    """내가 아직 읽지 않은(상대가 보낸) 메시지 수."""
    r = await db.execute(
        select(func.count())
        .select_from(Message)
        .outerjoin(
            MessageRead,
            and_(MessageRead.message_id == Message.id, MessageRead.user_id == me_id),
        )
        .where(
            Message.conversation_id == conversation_id,
            Message.deleted_at.is_(None),
            Message.sender_id != me_id,
            MessageRead.id.is_(None),
        )
    )
    return int(r.scalar_one() or 0)


async def _message_to_out(
    db: AsyncSession,
    m: Message,
    me_id: int,
    peer_id: int | None,
) -> MessageOut:
    r_me = await db.execute(
        select(MessageRead.id).where(MessageRead.message_id == m.id, MessageRead.user_id == me_id).limit(1)
    )
    read_by_me = r_me.scalar_one_or_none() is not None
    read_by_peer = False
    if m.sender_id == me_id and peer_id is not None:
        r_peer = await db.execute(
            select(MessageRead.id).where(MessageRead.message_id == m.id, MessageRead.user_id == peer_id).limit(1)
        )
        read_by_peer = r_peer.scalar_one_or_none() is not None
    return MessageOut(
        id=m.id,
        conversation_id=m.conversation_id,
        sender_id=m.sender_id,
        body=m.body,
        file_id=m.file_id,
        created_at=m.created_at,
        edited_at=m.edited_at,
        deleted_at=m.deleted_at,
        read_by_me=read_by_me,
        read_by_peer=read_by_peer,
    )


@router.get("", response_model=list[ConversationListItem])
async def list_conversations(
    db: Annotated[AsyncSession, Depends(get_db)],
    current: CurrentUser,
) -> list[ConversationListItem]:
    """내가 참가한 대화 목록 + 상대 정보 + 마지막 메시지 + 안 읽은 수."""
    r = await db.execute(
        select(Conversation)
        .join(ConversationParticipant)
        .where(ConversationParticipant.user_id == current.id)
        .options(selectinload(Conversation.participants))
        .order_by(Conversation.id.desc())
    )
    convs = r.scalars().unique().all()
    items: list[ConversationListItem] = []
    for c in convs:
        other = await other_user_in_direct(db, c.id, current.id) if c.type == "direct" else None
        peer_id = other.id if other else None
        lm = await _last_message(db, c.id)
        last_out = await _message_to_out(db, lm, current.id, peer_id) if lm else None
        unread = await _unread_count(db, c.id, current.id)
        items.append(
            ConversationListItem(
                id=c.id,
                type=c.type,
                other_user=UserPublic.model_validate(other) if other else None,
                last_message=last_out,
                unread_count=unread,
            )
        )
    return items


@router.post("/direct", response_model=ConversationOut)
async def create_direct(
    body: DirectCreateIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: CurrentUser,
) -> ConversationOut:
    """상대와 1:1 대화를 찾거나 새로 만듭니다."""
    try:
        conv = await get_or_create_direct(db, current.id, body.other_user_id)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e))
    await db.commit()
    await db.refresh(conv)
    return ConversationOut.model_validate(conv)


@router.get("/{conversation_id}/messages", response_model=list[MessageOut])
async def list_messages(
    conversation_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: CurrentUser,
    before_id: int | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[MessageOut]:
    """페이지네이션: before_id 보다 이전 메시지."""
    if not await user_in_conversation(db, current.id, conversation_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="대화에 참가하지 않았습니다.")
    other = await other_user_in_direct(db, conversation_id, current.id)
    peer_id = other.id if other else None
    q = select(Message).where(Message.conversation_id == conversation_id, Message.deleted_at.is_(None))
    if before_id is not None:
        q = q.where(Message.id < before_id)
    q = q.order_by(Message.id.desc()).limit(limit)
    r = await db.execute(q)
    rows = list(r.scalars().all())
    rows.reverse()
    return [await _message_to_out(db, m, current.id, peer_id) for m in rows]


@router.post("/{conversation_id}/messages", response_model=MessageOut)
async def send_message(
    conversation_id: int,
    body: MessageCreateIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: CurrentUser,
) -> MessageOut:
    """메시지 저장 후 참가자에게 WebSocket으로 message.new 전달."""
    if not await user_in_conversation(db, current.id, conversation_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="대화에 참가하지 않았습니다.")
    if not body.body.strip() and body.file_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="내용 또는 파일이 필요합니다.")
    if body.file_id is not None:
        from app.models.file import StoredFile

        sf = await db.get(StoredFile, body.file_id)
        if sf is None or sf.uploader_id != current.id or sf.status != "complete":
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="유효한 파일이 아닙니다.")
    msg = Message(
        conversation_id=conversation_id,
        sender_id=current.id,
        body=body.body.strip(),
        file_id=body.file_id,
    )
    db.add(msg)
    await db.flush()
    other = await other_user_in_direct(db, conversation_id, current.id)
    peer_id = other.id if other else None
    out = await _message_to_out(db, msg, current.id, peer_id)
    await db.commit()
    # 실시간 푸시
    pids = await participant_ids(db, conversation_id)
    await connection_manager.broadcast_to_users(
        pids,
        {"type": "message.new", "payload": out.model_dump(mode="json")},
    )
    return out


@router.post("/{conversation_id}/read", response_model=dict)
async def mark_read(
    conversation_id: int,
    body: MarkReadIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: CurrentUser,
) -> dict:
    """상대가 보낸 메시지 중 id <= up_to_message_id 인 것에 읽음 기록."""
    if not await user_in_conversation(db, current.id, conversation_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="대화에 참가하지 않았습니다.")
    r = await db.execute(
        select(Message).where(
            Message.conversation_id == conversation_id,
            Message.id <= body.up_to_message_id,
            Message.sender_id != current.id,
            Message.deleted_at.is_(None),
        )
    )
    msgs = r.scalars().all()
    for m in msgs:
        await db.execute(
            pg_insert(MessageRead)
            .values(message_id=m.id, user_id=current.id)
            .on_conflict_do_nothing(constraint="uq_message_user_read")
        )
    await db.commit()
    pids = await participant_ids(db, conversation_id)
    await connection_manager.broadcast_to_users(
        pids,
        {
            "type": "message.read",
            "payload": {
                "conversation_id": conversation_id,
                "reader_id": current.id,
                "up_to_message_id": body.up_to_message_id,
            },
        },
    )
    return {"ok": True}
