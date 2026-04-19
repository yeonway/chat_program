from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.message import Message
    from app.models.user import User


class StoredFile(Base):
    """업로드 파일 메타데이터. 실제 바이트는 upload_dir 아래 storage_key 경로."""

    __tablename__ = "stored_files"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    uploader_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    storage_key: Mapped[str] = mapped_column(String(512), unique=True, index=True)
    original_name: Mapped[str] = mapped_column(String(512))
    mime_type: Mapped[str] = mapped_column(String(128), default="application/octet-stream")
    size_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)  # 완료 시 기대 청크 수
    status: Mapped[str] = mapped_column(String(32), default="pending")  # pending | complete | failed
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    uploader: Mapped["User"] = relationship()
    messages: Mapped[list["Message"]] = relationship(back_populates="file")
