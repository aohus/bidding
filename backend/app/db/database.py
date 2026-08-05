from app.core.config import settings
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

# Create async engine
engine = create_async_engine(
    settings.DATABASE_URL,
    # echo=True 는 모든 SQL 과 바인드 파라미터(JSONB 전문 포함)를 로그로 남긴다.
    # 운영에서는 로그 볼륨과 성능 부담이 커서 개발 환경에서만 켠다.
    echo=settings.SQL_ECHO,
    future=True
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Create base class for models
Base = declarative_base()


async def get_db() -> AsyncSession:
    """Dependency for getting async database sessions."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()