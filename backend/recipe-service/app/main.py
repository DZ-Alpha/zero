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
from app.core.database import Base, engine  # noqa: E402
from app.models import OWNED_TABLES  # noqa: E402, F401 (import registers RecipeFavorite on Base.metadata)
from app.routers import health, recipe, substitute  # noqa: E402

logger = logging.getLogger("recipe_service")


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        # `recipe`는 이 서비스 전용 신규 스키마(RC-0111/0112 찜 기능) — `service`
        # 스키마(레시피 데이터팀 소유)는 여기서 절대 건드리지 않는다.
        await conn.execute(text("CREATE SCHEMA IF NOT EXISTS recipe"))
        await conn.run_sync(lambda sync_conn: Base.metadata.create_all(sync_conn, tables=OWNED_TABLES))
    logger.info("recipe-service started, owned tables ensured")
    yield


app = FastAPI(title="Recipe Service", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # Never leak stack traces / internals to the client (A10) — log server-side, return a generic message.
    logger.exception("unhandled error handling %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "일시적인 오류가 발생했습니다. 잠시 후 다시 시도해주세요."})


app.include_router(health.router)
app.include_router(recipe.router)
app.include_router(substitute.router)
