import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

# Explicit UTC timestamps in every log line (ASVS V16.2.2).
logging.Formatter.converter = time.gmtime
logging.basicConfig(level=logging.INFO, format="%(asctime)sZ %(levelname)s %(name)s %(message)s")
from fastapi.middleware.cors import CORSMiddleware

from app.core.database import Base, engine
from app.models import AdminAccount, SocialAccount, User  # noqa: F401
from app.routers import admin_auth, auth, health, items, user, webhooks

logger = logging.getLogger("app.main")


# create_all은 이미 있는 테이블은 ALTER하지 않는다 — users에 새 컬럼을 추가할 때마다
# 여기 직접 추가해야 운영 DB에도 반영된다 (meal_logs에서 겪은 것과 같은 패턴).
_USER_COLUMN_MIGRATIONS = [
    "ALTER TABLE service.users ADD COLUMN IF NOT EXISTS display_name VARCHAR(100)",
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        for statement in _USER_COLUMN_MIGRATIONS:
            await conn.execute(text(statement))
    yield


app = FastAPI(title="Final Team Alpha API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # Never leak stack traces / internals to the client (A10) — log server-side, return a generic message.
    logger.exception("unhandled error handling %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "일시적인 오류가 발생했습니다. 잠시 후 다시 시도해주세요."})


app.include_router(health.router)
app.include_router(items.router)
app.include_router(auth.router)
app.include_router(admin_auth.router)
app.include_router(user.router)
app.include_router(webhooks.router)
