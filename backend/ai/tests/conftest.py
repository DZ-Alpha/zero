import os

os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("USER_CONTEXT_SOURCE", "dummy")

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
