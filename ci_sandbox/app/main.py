from fastapi import FastAPI

from .config import settings
from .telemetry import health_check_counter, setup_telemetry

app = FastAPI()
setup_telemetry(app)


@app.get("/health")
def health():
    health_check_counter.add(1)
    return {"status": "ok", "environment": settings.environment}
