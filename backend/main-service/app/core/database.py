from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

engine = create_async_engine(
    settings.database_url,
    # 이 Postgres 인스턴스는 8개 백엔드 서비스가 공유한다(app/core/config.py 주석
    # 참고). 기본값(pool_size=5+max_overflow=10=15/프로세스)은 서비스마다
    # 여러 워커/레플리카가 뜨면 순식간에 max_connections를 넘겨
    # TooManyConnectionsError가 난다(2026-07-31 실사용 중 재현 - "하루 목표
    # 바꾸기" 저장 실패). 서비스마다 접속 상한을 보수적으로 고정하고,
    # pool_pre_ping/recycle로 죽은 커넥션이 풀에 남아있지 않게 한다.
    pool_size=5,
    max_overflow=3,
    pool_timeout=10,
    pool_recycle=1800,
    pool_pre_ping=True,
)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncIterator[AsyncSession]:
    async with async_session_factory() as session:
        yield session
