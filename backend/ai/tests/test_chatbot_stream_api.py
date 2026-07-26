import json
import time

import jwt
import pytest
from httpx import ASGITransport, AsyncClient

from app.api import chatbot as chatbot_api
from app.core.config import settings
from app.handlers.general_qa import GeneralQAHandler
from app.main import app
from app.rag.retriever import RagChunk, Retriever
from app.context.dummy import DummyUserContextProvider
from app.router.dispatcher import Dispatcher
from app.router.intent import IntentClassifier
from app.schemas import Intent


class _StreamLLM:
    async def complete(self, system, user):
        return "테스트"

    async def complete_stream(self, system, user):
        for part in ["안녕", "하세요"]:
            yield part


class _FakeRetriever(Retriever):
    async def search_docs(self, query, k=4):
        return []

    async def search_products(self, query, k=4):
        return []


async def _cls(msg):
    return Intent.GENERAL_QA


def _deps():
    qa = GeneralQAHandler(llm=_StreamLLM(), retriever=_FakeRetriever())
    return chatbot_api.Dependencies(
        provider=DummyUserContextProvider(),
        classifier=IntentClassifier(llm_classify=_cls),
        dispatcher=Dispatcher({Intent.GENERAL_QA: qa}),
        qa_handler=qa,
    )


@pytest.fixture
def client():
    app.dependency_overrides[chatbot_api.get_dependencies] = _deps
    transport = ASGITransport(app=app)
    yield AsyncClient(transport=transport, base_url="http://test")
    app.dependency_overrides.clear()


def _token():
    now = int(time.time())
    return jwt.encode({"sub": "1", "nickname": "t", "iat": now, "exp": now + 3600},
                      settings.jwt_secret, algorithm="HS256")


async def test_stream_returns_sse_with_deltas_and_done(client):
    async with client as ac:
        async with ac.stream("POST", "/ai/chatbot/stream",
                             json={"usr": _token(), "msg": "탄수화물이 뭐야?"}) as resp:
            assert resp.status_code == 200
            assert "text/event-stream" in resp.headers["content-type"]
            body = ""
            async for chunk in resp.aiter_text():
                body += chunk
    # delta 조각과 done 이벤트가 있어야 함
    assert '"delta": "안녕"' in body or '"delta":"안녕"' in body
    assert '"done": true' in body or '"done":true' in body
    assert "cs-partner" in body


async def test_stream_invalid_token_401(client):
    async with client as ac:
        resp = await ac.post("/ai/chatbot/stream", json={"usr": "bad.token", "msg": "hi"})
    assert resp.status_code == 401
