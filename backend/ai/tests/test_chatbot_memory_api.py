import time

import fakeredis.aioredis
import jwt
import pytest
from httpx import ASGITransport, AsyncClient

from app.api import chatbot as chatbot_api
from app.core.config import settings
from app.context.dummy import DummyUserContextProvider
from app.handlers.general_qa import GeneralQAHandler
from app.main import app
from app.memory.conversation_store import ConversationStore
from app.rag.retriever import Retriever
from app.router.dispatcher import Dispatcher
from app.router.intent import IntentClassifier
from app.schemas import Intent


class _LLM:
    async def complete(self, system, messages):
        return "답변"

    async def complete_stream(self, system, messages):
        yield "답"
        yield "변"


class _R(Retriever):
    async def search_docs(self, q, k=4):
        return []

    async def search_products(self, q, k=4):
        return []


async def _cls(msg):
    return Intent.GENERAL_QA


def _make_deps(store):
    qa = GeneralQAHandler(llm=_LLM(), retriever=_R())
    return chatbot_api.Dependencies(
        provider=DummyUserContextProvider(),
        classifier=IntentClassifier(llm_classify=_cls),
        dispatcher=Dispatcher({Intent.GENERAL_QA: qa}),
        qa_handler=qa,
        store=store,
    )


@pytest.fixture
def store():
    r = fakeredis.aioredis.FakeRedis(decode_responses=True)
    return ConversationStore(r, max_turns=20, ttl_seconds=100)


@pytest.fixture
def client(store):
    app.dependency_overrides[chatbot_api.get_dependencies] = lambda: _make_deps(store)
    transport = ASGITransport(app=app)
    yield AsyncClient(transport=transport, base_url="http://test")
    app.dependency_overrides.clear()


def _token():
    now = int(time.time())
    return jwt.encode({"sub": "7", "nickname": "t", "iat": now, "exp": now + 3600},
                      settings.jwt_secret, algorithm="HS256")


async def test_guest_conversation_persists_across_requests(client, store):
    async with client as ac:
        r1 = await ac.post("/ai/chatbot", json={"msg": "나 알레르기 있어", "session_id": "g1"})
        assert r1.status_code == 200
        # 저장 확인: 두 번째 요청 시 히스토리 로드됨
        r2 = await ac.post("/ai/chatbot", json={"msg": "땅콩", "session_id": "g1"})
        assert r2.status_code == 200
    all_msgs = await store.load_all("chat:history:guest:g1")
    assert [m["text"] for m in all_msgs] == ["나 알레르기 있어", "답변", "땅콩", "답변"]


async def test_history_endpoint_returns_messages(client, store):
    await store.append("chat:history:guest:g2", "안녕", "안녕하세요")
    async with client as ac:
        resp = await ac.get("/ai/chatbot/history", params={"session_id": "g2"})
    assert resp.status_code == 200
    assert resp.json()["messages"] == [
        {"role": "user", "text": "안녕"},
        {"role": "assistant", "text": "안녕하세요"},
    ]


async def test_history_empty_when_no_session(client):
    async with client as ac:
        resp = await ac.get("/ai/chatbot/history")
    assert resp.status_code == 200
    assert resp.json()["messages"] == []


async def test_logged_in_uses_user_key(client, store):
    async with client as ac:
        await ac.post("/ai/chatbot", json={"msg": "안녕", "usr": _token()})
    all_msgs = await store.load_all("chat:history:user:7")
    assert all_msgs[0]["text"] == "안녕"


async def test_redis_down_still_answers(client):
    # store가 None이어도(또는 장애) 200 응답
    app.dependency_overrides[chatbot_api.get_dependencies] = lambda: _make_deps(None)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post("/ai/chatbot", json={"msg": "안녕", "session_id": "g9"})
    assert resp.status_code == 200
    app.dependency_overrides.clear()
