from fastapi import FastAPI

from .config import settings

app = FastAPI()


@app.get("/health")
def health():
    return {"status": "ok", "environment": settings.environment}
