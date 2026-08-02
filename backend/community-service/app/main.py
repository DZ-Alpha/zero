import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

# Explicit UTC timestamps in every log line (ASVS V16.2.2).
logging.Formatter.converter = time.gmtime
logging.basicConfig(level=logging.INFO, format="%(asctime)sZ %(levelname)s %(name)s %(message)s")

from app.core.config import settings  # noqa: E402
from app.core.database import Base, run_with_retry  # noqa: E402
from app.models import OWNED_TABLES  # noqa: E402, F401 (import registers Notice/NoticeLike/Tag on Base.metadata)
from app.routers import health, notice, rooms, sweetener  # noqa: E402

logger = logging.getLogger("community_service")

# create_all()은 없는 테이블만 만들고, 이미 있는 테이블에 컬럼을 추가해주지
# 않는다 - room_nudges는 이미 운영에 있던 테이블이라 새 컬럼(acknowledged_at,
# 받은 사람에게 콕 찌르기를 한 번 보여줬는지 추적용)이 실제 테이블엔 반영이
# 안 돼 있을 수 있다 - diet-service의 동일 패턴(_MEAL_LOG_COLUMN_MIGRATIONS) 참고.
_ROOM_NUDGE_COLUMN_MIGRATIONS = [
    "ALTER TABLE community.room_nudges ADD COLUMN IF NOT EXISTS acknowledged_at TIMESTAMPTZ",
]


async def _migrate(conn) -> None:
    # `community` is this service's own schema — created/migrated here.
    # `service` (where Tag/tags lives) is data-team managed and never
    # touched: create_all(tables=...) is scoped to OWNED_TABLES only.
    await conn.execute(text("CREATE SCHEMA IF NOT EXISTS community"))
    await conn.run_sync(lambda sync_conn: Base.metadata.create_all(sync_conn, tables=OWNED_TABLES))
    for statement in _ROOM_NUDGE_COLUMN_MIGRATIONS:
        await conn.execute(text(statement))


@asynccontextmanager
async def lifespan(app: FastAPI):
    await run_with_retry(_migrate)
    yield


# /docs, /redoc, /openapi.json은 settings.enable_api_docs(기본 False)로 게이트한다
# - 자세한 이유는 app/core/config.py 주석 참고.
app = FastAPI(
    title="Community Service",
    lifespan=lifespan,
    docs_url="/docs" if settings.enable_api_docs else None,
    redoc_url="/redoc" if settings.enable_api_docs else None,
    openapi_url="/openapi.json" if settings.enable_api_docs else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    # PATCH 추가 - 얌로그(rooms)의 방 설정 수정(PATCH /rooms/{id}, PATCH
    # /rooms/{id}/notifications)에 필요하다. 기존 notice 쪽엔 PATCH를 쓰는
    # 엔드포인트가 없어서 지금까지 빠져 있었다.
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # Never leak stack traces / internals to the client (A10) — log server-side, return a generic message.
    logger.exception("unhandled error handling %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "일시적인 오류가 발생했습니다. 잠시 후 다시 시도해주세요."})


app.include_router(health.router)
app.include_router(notice.router)
app.include_router(rooms.router)
app.include_router(sweetener.router)
