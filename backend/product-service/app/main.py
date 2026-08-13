import logging
import time

# Service entrypoint kept explicit so deployment health checks remain easy to audit.

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

logging.Formatter.converter = time.gmtime
logging.basicConfig(level=logging.INFO, format="%(asctime)sZ %(levelname)s %(name)s %(message)s")

from app.core.config import settings  # noqa: E402
from app.core.database import Base, run_with_retry  # noqa: E402
from app.models.product import Product  # noqa: F401, E402
from app.models.product_ai_summary import ProductAiSummary  # noqa: F401, E402
from app.models.product_favorite import ProductFavorite  # noqa: F401, E402
from app.models.product_tag import ProductTag  # noqa: F401, E402
from app.models.user_ref import UserRef  # noqa: F401, E402 (FK target stub for ProductFavorite.user_id)
from app.routers import admin, health, product, search  # noqa: E402

logger = logging.getLogger("product_service")

# /docs, /redoc, /openapi.json은 settings.enable_api_docs(기본 False)로 게이트한다
# - 자세한 이유는 app/core/config.py 주석 참고.
app = FastAPI(
    title="Product Service",
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
    # product-service 소유 테이블만 CREATE TABLE IF NOT EXISTS.
    # Tag(Ingredients 소유) / UserHealthProfileRef(Main 소유) 는 DDL 대상 아님.
    # `product` 스키마는 이 서비스 전용 신규 스키마(PR-0307/0308 찜 기능) —
    # `service` 스키마는 데이터팀 소유라 거기에 새 테이블을 추가하지 않는다.
    OWNED_TABLES = [Product.__table__, ProductTag.__table__, ProductFavorite.__table__, ProductAiSummary.__table__]
    await conn.execute(text("CREATE SCHEMA IF NOT EXISTS product"))
    await conn.run_sync(
        lambda sync_conn: Base.metadata.create_all(
            sync_conn, tables=OWNED_TABLES
        )
    )


@app.on_event("startup")
async def on_startup() -> None:
    # DB_AUTO_MIGRATE=false면 DDL을 건너뛴다 — RDS 최소권한 app role에서는
    # 여기서 InsufficientPrivilege가 나면서 기동 자체가 실패한다(계획서 A-01).
    # 그 환경에서는 db/migrations/product-service.sql을 DBA가 먼저 적용한다.
    if settings.db_auto_migrate:
        await run_with_retry(_migrate)
        logger.info("product-service started, owned tables ensured")
    else:
        logger.info("product-service started, DB_AUTO_MIGRATE=false — startup DDL skipped")


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled error handling %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "일시적인 오류가 발생했습니다. 잠시 후 다시 시도해주세요."})


app.include_router(health.router)
app.include_router(search.router)
app.include_router(product.router)
app.include_router(admin.router)
