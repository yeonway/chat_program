"""청크 업로드(init/chunk/complete) 및 권한 있는 다운로드."""

import math
import os
import uuid
from typing import Annotated

import aiofiles
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.file_validation import FileContentValidationError, validate_merged_file
from app.core.rate_limit import limiter
from app.core.deps import CurrentUser
from app.database import get_db
from app.models.conversation import ConversationParticipant
from app.models.file import StoredFile
from app.models.message import Message
from app.schemas.file import UploadCompleteOut, UploadInitIn, UploadInitOut

router = APIRouter(prefix="/files", tags=["files"])

# 일반 첨부 허용 확장자 (필요 시 확장)
_ALLOWED_EXT = {
    ".pdf",
    ".zip",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".txt",
    ".mp4",
    ".mp3",
    ".doc",
    ".docx",
}


def _temp_dir(file_id: int) -> str:
    return os.path.join(settings.upload_dir, "temp", str(file_id))


def _safe_ext(filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    if ext not in _ALLOWED_EXT:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="허용되지 않은 파일 형식입니다.")
    return ext


async def _can_access_file(db: AsyncSession, user_id: int, sf: StoredFile) -> bool:
    if sf.uploader_id == user_id:
        return True
    r = await db.execute(select(Message.id).where(Message.file_id == sf.id).limit(1))
    mid = r.scalar_one_or_none()
    if mid is None:
        return False
    m = await db.get(Message, mid)
    if m is None:
        return False
    part = await db.execute(
        select(ConversationParticipant.id).where(
            ConversationParticipant.conversation_id == m.conversation_id,
            ConversationParticipant.user_id == user_id,
        )
    )
    return part.scalar_one_or_none() is not None


@router.post("/upload/init", response_model=UploadInitOut)
@limiter.limit("40/minute")
async def upload_init(
    request: Request,
    body: UploadInitIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: CurrentUser,
) -> UploadInitOut:
    """대용량 업로드: 파일 레코드 생성 및 임시 디렉터리 준비."""
    if body.size > settings.max_upload_bytes:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="파일 크기 제한을 초과했습니다.")
    _safe_ext(body.filename)
    chunk = min(settings.chunk_size_bytes, body.size)
    expected = max(1, math.ceil(body.size / chunk))
    storage_key_placeholder = f"pending:{uuid.uuid4().hex}"
    sf = StoredFile(
        uploader_id=current.id,
        storage_key=storage_key_placeholder,
        original_name=body.filename[:512],
        mime_type=body.mime_type[:128],
        size_bytes=body.size,
        chunk_count=expected,
        status="pending",
    )
    db.add(sf)
    await db.flush()
    os.makedirs(_temp_dir(sf.id), exist_ok=True)
    await db.commit()
    await db.refresh(sf)
    return UploadInitOut(file_id=sf.id, chunk_size=chunk, expected_chunks=expected)


@router.put("/upload/{file_id}/chunk")
@limiter.limit("600/minute")
async def upload_chunk(
    file_id: int,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: CurrentUser,
    index: int = Query(..., ge=0),
) -> dict:
    """index 번째 청크 저장 (0 기반). 본문은 raw bytes (클라이언트에서 application/octet-stream)."""
    sf = await db.get(StoredFile, file_id)
    if sf is None or sf.uploader_id != current.id or sf.status != "pending":
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="업로드 세션을 찾을 수 없습니다.")
    if index >= sf.chunk_count:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="잘못된 청크 인덱스입니다.")
    data = await request.body()
    path = os.path.join(_temp_dir(file_id), f"part_{index:06d}")
    async with aiofiles.open(path, "wb") as f:
        await f.write(data)
    return {"ok": True, "index": index, "bytes": len(data)}


@router.post("/upload/{file_id}/complete", response_model=UploadCompleteOut)
async def upload_complete(
    file_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: CurrentUser,
) -> UploadCompleteOut:
    """모든 청크를 순서대로 병합하고 최종 파일로 저장합니다."""
    sf = await db.get(StoredFile, file_id)
    if sf is None or sf.uploader_id != current.id or sf.status != "pending":
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="업로드 세션을 찾을 수 없습니다.")
    td = _temp_dir(file_id)
    final_name = f"{uuid.uuid4().hex}{_safe_ext(sf.original_name)}"
    final_dir = os.path.join(settings.upload_dir, "final")
    os.makedirs(final_dir, exist_ok=True)
    final_path = os.path.join(final_dir, final_name)
    total = 0
    try:
        async with aiofiles.open(final_path, "wb") as out_f:
            for i in range(sf.chunk_count):
                part_path = os.path.join(td, f"part_{i:06d}")
                if not os.path.isfile(part_path):
                    raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=f"청크 {i} 가 없습니다.")
                async with aiofiles.open(part_path, "rb") as in_f:
                    while True:
                        buf = await in_f.read(1024 * 1024)
                        if not buf:
                            break
                        total += len(buf)
                        await out_f.write(buf)
        if total != sf.size_bytes:
            # 크기 불일치 시 실패 처리
            if os.path.isfile(final_path):
                os.remove(final_path)
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="병합 크기가 선언 크기와 일치하지 않습니다.")
        ext = _safe_ext(sf.original_name)
        try:
            validate_merged_file(
                final_path,
                ext,
                sf.mime_type or "application/octet-stream",
            )
        except FileContentValidationError as e:
            if os.path.isfile(final_path):
                os.remove(final_path)
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except HTTPException:
        raise
    except Exception:
        if os.path.isfile(final_path):
            os.remove(final_path)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail="병합 중 오류가 발생했습니다.")
    sf.storage_key = os.path.join("final", final_name)
    sf.status = "complete"
    await db.commit()
    # 임시 파일 정리
    for i in range(sf.chunk_count):
        p = os.path.join(td, f"part_{i:06d}")
        if os.path.isfile(p):
            os.remove(p)
    if os.path.isdir(td):
        try:
            os.rmdir(td)
        except OSError:
            pass
    return UploadCompleteOut(file_id=sf.id, status="complete")


@router.get("/{file_id}")
async def download_file(
    file_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current: CurrentUser,
) -> FileResponse:
    """업로더 또는 해당 파일이 첨부된 대화 참가자만 다운로드."""
    sf = await db.get(StoredFile, file_id)
    if sf is None or sf.status != "complete":
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="파일을 찾을 수 없습니다.")
    if not await _can_access_file(db, current.id, sf):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="다운로드 권한이 없습니다.")
    path = os.path.join(settings.upload_dir, sf.storage_key)
    if not os.path.isfile(path):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="파일이 디스크에 없습니다.")
    return FileResponse(path, filename=sf.original_name, media_type=sf.mime_type or "application/octet-stream")
