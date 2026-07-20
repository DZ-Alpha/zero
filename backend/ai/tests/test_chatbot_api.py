import time

import jwt
import pytest
from httpx import ASGITransport, AsyncClient

from app.api import chatbot as chatbot_api
from app.core.config import settings
from app.handlers.general_qa import GeneralQAHandler
from app.main import app
from app.rag.retriever import RagChunk, Retriever
from app.router.dispatcher import Dispatcher
from app.router.intent import IntentClassifier
from app.schemas import Intent


class _FakeLLM:
    async def complete(self, system: str, user: str) -> str:
        return "테스트 답변"


class _FakeRetriever(Retriever):
    async def search_docs(self, query: str, k: int = 4):
        return [RagChunk(text="식약처 기준", source="식약처", score=0.9)]

    async def search_products(self, query: str, k: int = 4):
        return []


async def _fake_llm_classify(msg: str) -> Intent:
    return Intent.GENERAL_QA


def _deps_override():
    from app.context.dummy import DummyUserContextProvider
    provider = DummyUserContextProvider()
    classifier = IntentClassifier(llm_classify=_fake_llm_classify)
    qa = GeneralQAHandler(llm=_FakeLLM(), retriever=_FakeRetriever())
    dispatcher = Dispatcher({Intent.GENERAL_QA: qa})
    return chatbot_api.Dependencies(provider=provider, classifier=classifier, dispatcher=dispatcher)


@pytest.fixture
def client():
    app.dependency_overrides[chatbot_api.get_dependencies] = _deps_override
    transport = ASGITransport(app=app)
    yield AsyncClient(transport=transport, base_url="http://test")
    app.dependency_overrides.clear()


def _token(user_id="1"):
    now = int(time.time())
    return jwt.encode({"sub": user_id, "nickname": "지은", "iat": now, "exp": now + 3600},
                      settings.jwt_secret, algorithm="HS256")


async def test_chatbot_general_question_returns_answer(client):
    async with client as ac:
        resp = await ac.post("/ai/chatbot", json={"usr": _token(), "msg": "탄수화물이 뭐야?"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["msg"] == "테스트 답변"
    assert body["is-img"] is False
    assert "cs-partner" in body


async def test_chatbot_anonymous_without_usr_returns_answer(client):
    # 비로그인(usr 없음)도 일반 지식질문은 답한다(익명 맥락).
    async with client as ac:
        resp = await ac.post("/ai/chatbot", json={"msg": "탄수화물이 뭐야?"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["msg"] == "테스트 답변"
    assert "cs-partner" in body


async def test_chatbot_invalid_token_is_401(client):
    async with client as ac:
        resp = await ac.post("/ai/chatbot", json={"usr": "bad.token", "msg": "안녕"})
    assert resp.status_code == 401


async def test_chatbot_requires_msg_or_img(client):
    async with client as ac:
        resp = await ac.post("/ai/chatbot", json={"usr": _token()})
    assert resp.status_code == 422
