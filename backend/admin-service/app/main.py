import logging
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Explicit UTC timestamps in every log line (ASVS V16.2.2).
logging.Formatter.converter = time.gmtime
logging.basicConfig(level=logging.INFO, format="%(asctime)sZ %(levelname)s %(name)s %(message)s")

from app.core.config import settings  # noqa: E402
from app.routers import admin, health  # noqa: E402

logger = logging.getLogger("admin_service")

# /docs, /redoc, /openapi.json은 settings.enable_api_docs(기본 False)로 게이트한다
# - 자세한 이유는 app/core/config.py 주석 참고.
app = FastAPI(
    title="Admin Service",
    docs_url="/docs" if settings.enable_api_docs else None,
    redoc_url="/redoc" if settings.enable_api_docs else None,
    openapi_url="/openapi.json" if settings.enable_api_docs else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # Never leak stack traces / internals to the client (A10) — log server-side, return a generic message.
    logger.exception("unhandled error handling %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "일시적인 오류가 발생했습니다. 잠시 후 다시 시도해주세요."})


app.include_router(health.router)
app.include_router(admin.router)
