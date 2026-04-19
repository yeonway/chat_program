"""DB 세션 및 엔진 설정 (비동기 SQLAlchemy)."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings


class Base(DeclarativeBase):
    """모든 ORM 모델의 베이스."""


# asyncpg용 URL: postgresql+asyncpg://...
engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """요청 단위 DB 세션. 각 라우트에서 필요 시 commit 호출."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
