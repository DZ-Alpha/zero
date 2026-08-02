import asyncio
import logging
from collections.abc import AsyncGenerator, Awaitable, Callable
from typing import TypeVar

from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

logger = logging.getLogger("diet_service.database")

_T = TypeVar("_T")

engine = create_async_engine(
    settings.database_url,
    # 이 Postgres 인스턴스는 8개 백엔드 서비스가 공유한다(app/core/config.py 주석
    # 참고). 기본값(pool_size=5+max_overflow=10=15/프로세스)은 서비스마다
    # 여러 워커/레플리카가 뜨면 순식간에 max_connections를 넘겨
    # TooManyConnectionsError가 난다(2026-07-31 실사용 중 재현). 서비스마다
    # 접속 상한을 보수적으로 고정하고, pool_recycle로 죽은 커넥션이 풀에
    # 남아있지 않게 한다.
    pool_size=5,
    max_overflow=3,
    pool_timeout=10,
    pool_recycle=1800,
    pool_pre_ping=True,
)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session


# 2026-08-02 부하테스트 인계 — 컨테이너 재시작 구간(배포/재시작 직후 DB가 아직
# 안 받는 순간)에 시작 시점 DB 연결이 한 번이라도 실패하면 그대로 죽어 fatal
# CrashLoopBackOff가 됐다. 지수 백오프(1→2→4→8→16초, 5회)로 재시도한다 - DB
# 자체는 병목이 아니었음이 실측으로 확인됐고(최대 부하에서도 CPU 11.96m,
# 연결 1/100), 문제는 순전히 타이밍이었다.
async def run_with_retry(
    fn: Callable[[AsyncConnection], Awaitable[_T]],
    *,
    max_attempts: int = 5,
    initial_delay_seconds: float = 1.0,
) -> _T:
    delay = initial_delay_seconds
    for attempt in range(1, max_attempts + 1):
        try:
            async with engine.begin() as conn:
                return await fn(conn)
        except OperationalError:
            if attempt == max_attempts:
                logger.exception("db connection failed after %d attempts, giving up", max_attempts)
                raise
            logger.warning(
                "db connection failed (attempt %d/%d), retrying in %.0fs",
                attempt, max_attempts, delay,
            )
            await asyncio.sleep(delay)
            delay *= 2
    raise AssertionError("unreachable")  # max_attempts >= 1 이면 루프가 return/raise로 항상 빠져나간다
