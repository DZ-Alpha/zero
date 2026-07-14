import logging

from fastapi import FastAPI

from .config import settings
from .telemetry import health_check_counter, setup_telemetry

app = FastAPI()
setup_telemetry(app)
logger = logging.getLogger(__name__)


@app.get("/health")
def health():
    health_check_counter.add(1)
    logger.info("health check requested")
    return {"status": "ok", "environment": settings.environment, "version": "0.2.0"}