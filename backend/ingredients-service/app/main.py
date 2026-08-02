# CI: DAST 인증 active scan 게이트 실동작 검증용 트리거 (2026-07-31). 동작 영향 없음.
import logging
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

logging.Formatter.converter = time.gmtime
logging.basicConfig(level=logging.INFO, format="%(asctime)sZ %(levelname)s %(name)s %(message)s")

from app.core.config import settings  # noqa: E402
from app.core.database import Base, run_with_retry  # noqa: E402
from app.models.tag import Tag  # noqa: F401, E402
from app.routers import admin, health, tags  # noqa: E402

logger = logging.getLogger("ingredients_service")

# /docs, /redoc, /openapi.json은 settings.enable_api_docs(기본 False)로 게이트한다
# - 자세한 이유는 app/core/config.py 주석 참고.
app = FastAPI(
    title="Ingredients Service",
    docs_url="/docs" if settings.enable_api_docs else None,
    redoc_url="/redoc" if settings.enable_api_docs else None,
    openapi_url="/openapi.json" if settings.enable_api_docs else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


async def _migrate(conn) -> None:
    # ingredients-service 소유 테이블만 CREATE TABLE IF NOT EXISTS.
    OWNED_TABLES = [Tag.__table__]
    await conn.run_sync(
        lambda sync_conn: Base.metadata.create_all(sync_conn, tables=OWNED_TABLES)
    )


@app.on_event("startup")
async def on_startup() -> None:
    await run_with_retry(_migrate)
    logger.info("ingredients-service started, owned tables ensured")


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled error handling %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "일시적인 오류가 발생했습니다. 잠시 후 다시 시도해주세요."})


app.include_router(health.router)
app.include_router(tags.router)
app.include_router(admin.router)
