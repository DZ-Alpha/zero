import logging
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

logging.Formatter.converter = time.gmtime
logging.basicConfig(level=logging.INFO, format="%(asctime)sZ %(levelname)s %(name)s %(message)s")

from app.core.config import settings  # noqa: E402
from app.core.database import Base, engine  # noqa: E402
from app.models.meal_item import MealItem  # noqa: F401, E402
from app.models.meal_log import MealLog  # noqa: F401, E402
from app.routers import diet, health, home, uploads  # noqa: E402
from app.services.vision_consumer import start_consumer, stop_consumer  # noqa: E402

logger = logging.getLogger("diet_service")

app = FastAPI(title="Diet Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def on_startup() -> None:
    # diet-service 소유 테이블만 CREATE TABLE IF NOT EXISTS.
    # ProductRef(Product 소유) / UserHealthProfileRef(Main 소유)는 DDL 대상 아님.
    # v_meal_totals 뷰는 DB 팀이 관리 — DDL 금지.
    OWNED_TABLES = [MealLog.__table__, MealItem.__table__]
    async with engine.begin() as conn:
        await conn.run_sync(
            lambda sync_conn: Base.metadata.create_all(sync_conn, tables=OWNED_TABLES)
        )
    logger.info("diet-service started, owned tables ensured")
    await start_consumer()


@app.on_event("shutdown")
async def on_shutdown() -> None:
    await stop_consumer()


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled error handling %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "일시적인 오류가 발생했습니다. 잠시 후 다시 시도해주세요."})


app.include_router(health.router)
app.include_router(home.router)
app.include_router(diet.router)
app.include_router(uploads.router)
