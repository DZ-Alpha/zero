import logging
import time
from contextlib import asynccontextmanager

# Service entrypoint kept explicit so deployment health checks remain easy to audit.

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Explicit UTC timestamps in every log line (ASVS V16.2.2).
logging.Formatter.converter = time.gmtime
logging.basicConfig(level=logging.INFO, format="%(asctime)sZ %(levelname)s %(name)s %(message)s")

from app.core.config import settings  # noqa: E402
from app.core.database import Base, run_with_retry  # noqa: E402
from app.models import OWNED_TABLES  # noqa: E402, F401 (import registers all models on Base.metadata)
from app.routers import content, gauge, health, health_profile, home, preferences, rank, recommend, search  # noqa: E402

logger = logging.getLogger("main_service")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # user_health_profiles/user_preferences는 이 서비스가 소유 — 나머지
    # (Product/Diet/Ingredients 소유 읽기전용 모델)는 OWNED_TABLES에서
    # 제외돼 있어 여기서 절대 건드리지 않는다.
    #
    # DB_AUTO_MIGRATE=false면 DDL을 건너뛴다 — RDS 최소권한 app role에서는
    # 여기서 InsufficientPrivilege가 나면서 기동 자체가 실패한다(계획서 A-01).
    # 그 환경에서는 db/migrations/main-service.sql을 DBA가 먼저 적용한다.
    if settings.db_auto_migrate:
        await run_with_retry(
            lambda conn: conn.run_sync(lambda sync_conn: Base.metadata.create_all(sync_conn, tables=OWNED_TABLES))
        )
        logger.info("main-service started, owned tables ensured")
    else:
        logger.info("main-service started, DB_AUTO_MIGRATE=false — startup DDL skipped")
    yield


# /docs, /redoc, /openapi.json은 settings.enable_api_docs(기본 False)로 게이트한다
# - 자세한 이유는 app/core/config.py 주석 참고.
app = FastAPI(
    title="Main Service",
    lifespan=lifespan,
    docs_url="/docs" if settings.enable_api_docs else None,
    redoc_url="/redoc" if settings.enable_api_docs else None,
    openapi_url="/openapi.json" if settings.enable_api_docs else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # Never leak stack traces / internals to the client (A10) — log server-side, return a generic message.
    logger.exception("unhandled error handling %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "일시적인 오류가 발생했습니다. 잠시 후 다시 시도해주세요."})


app.include_router(health.router)
app.include_router(home.router)
app.include_router(health_profile.router)
app.include_router(preferences.router)
app.include_router(gauge.router)
app.include_router(recommend.router)
app.include_router(search.router)
app.include_router(rank.router)
app.include_router(content.router)
