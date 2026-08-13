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

from app.core.config import settings
from app.core.database import Base, engine, run_with_retry
from app.models import AdminAccount, SocialAccount, User  # noqa: F401
from app.routers import admin_auth, auth, health, items, test_login, user, webhooks

logger = logging.getLogger("app.main")


# create_all은 이미 있는 테이블은 ALTER하지 않는다 — users에 새 컬럼을 추가할 때마다
# 여기 직접 추가해야 운영 DB에도 반영된다 (meal_logs에서 겪은 것과 같은 패턴).
# 주의: diet-service/recipe-service 모델은 __table_args__로 schema="service"를 명시하지만
# login-service의 User/SocialAccount/AdminAccount는 스키마를 명시한 적이 없다 — 연결의
# 기본 search_path를 그대로 따른다. 여기 스키마 접두사를 붙이면 실제 테이블 위치와
# 어긋나 "relation does not exist"로 기동이 통째로 실패한다 (2026-07-21 장애 원인).
_USER_COLUMN_MIGRATIONS = [
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS display_name VARCHAR(100)",
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    # DB_AUTO_MIGRATE=false면 DDL을 통째로 건너뛴다 — RDS 최소권한 app role에서는
    # create_all이 InsufficientPrivilege로 죽으면서 기동 자체가 실패한다(계획서
    # A-01). 그 환경에서는 db/migrations/login-service.sql을 DBA가 먼저 적용한다.
    # 아래 컬럼 마이그레이션과 달리 create_all은 예외를 삼키지 않으므로(테이블이
    # 없는 채로 뜨면 첫 로그인부터 실패) 이 게이트가 유일한 안전장치다.
    if settings.db_auto_migrate:
        await run_with_retry(lambda conn: conn.run_sync(Base.metadata.create_all))
        # 컬럼 마이그레이션은 create_all과 별도 트랜잭션으로 분리 — 여기서 하나라도 실패해도
        # 로그인 자체(가장 중요한 기능)는 계속 뜨게 한다. 2026-07-21 장애: 스키마 접두사
        # 오류로 이 블록이 죽으면서 로그인 서비스 전체가 기동 불가 상태가 됐었다.
        try:
            async with engine.begin() as conn:
                for statement in _USER_COLUMN_MIGRATIONS:
                    await conn.execute(text(statement))
        except Exception:
            logger.exception("user column migration failed — continuing startup without it")
    else:
        logger.info("DB_AUTO_MIGRATE=false — startup DDL skipped")
    yield


# /docs, /redoc, /openapi.json은 settings.enable_api_docs(기본 False)로 게이트한다
# - 자세한 이유는 app/core/config.py 주석 참고.
app = FastAPI(
    title="Final Team Alpha API",
    lifespan=lifespan,
    docs_url="/docs" if settings.enable_api_docs else None,
    redoc_url="/redoc" if settings.enable_api_docs else None,
    openapi_url="/openapi.json" if settings.enable_api_docs else None,
)

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

# 부하테스트 전용 — settings.enable_test_login(기본 False)로 게이트한다.
# 운영에 켜지면 user_id만 알면 누구든 그 계정으로 로그인할 수 있으므로
# 스테이징에서만 켠다 - 자세한 이유는 app/core/config.py 주석 참고.
if settings.enable_test_login:
    app.include_router(test_login.router)
