import base64
import time

import fakeredis.aioredis
import jwt
import pytest
from httpx import ASGITransport, AsyncClient

from app.api import chatbot as chatbot_api
from app.core.config import settings
from app.context.dummy import DummyUserContextProvider
from app.handlers.base import HandlerInput, HandlerResult, FeatureHandler
from app.main import app
from app.memory.conversation_store import ConversationStore
from app.router.dispatcher import Dispatcher
from app.router.intent import IntentClassifier
from app.schemas import Intent
import app.api.chatbot as chatbot_mod


class _PhotoHandler(FeatureHandler):
    async def handle(self, data: HandlerInput) -> HandlerResult:
        return HandlerResult(msg="케이크네요", is_img=True, image_key="7/abc.png")


async def _cls_photo(msg):
    return Intent.PRODUCT_ANALYSIS


def _make_deps(store):
    return chatbot_api.Dependencies(
        provider=DummyUserContextProvider(),
        classifier=IntentClassifier(llm_classify=_cls_photo),
        dispatcher=Dispatcher({Intent.PRODUCT_ANALYSIS: _PhotoHandler()}),
        qa_handler=None,
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


def _png():
    return "data:image/png;base64," + base64.b64encode(b"x").decode()


async def test_photo_turn_saves_image_key(client, store):
    async with client as ac:
        r = await ac.post("/ai/chatbot", json={"msg": "이거 당류?", "img": _png(), "session_id": "g1"})
        assert r.status_code == 200
    msgs = await store.load_all("chat:history:guest:g1")
    assert msgs[0]["image_key"] == "7/abc.png"


async def test_photo_only_turn_saved(client, store):
    async with client as ac:
        r = await ac.post("/ai/chatbot", json={"img": _png(), "session_id": "g2"})
        assert r.status_code == 200
    msgs = await store.load_all("chat:history:guest:g2")
    assert len(msgs) == 2  # msg 없어도 저장됨
    assert msgs[0]["image_key"] == "7/abc.png"


async def test_history_converts_image_key_to_url(client, store, monkeypatch):
    monkeypatch.setattr(chatbot_mod, "presign_chat_photo_url",
                        lambda key, **k: f"/b/chat-photos/{key}?sig=x")
    await store.append("chat:history:guest:g3", "이거 당류?", "케이크네요", image_key="7/abc.png")
    async with client as ac:
        resp = await ac.get("/ai/chatbot/history", params={"session_id": "g3"})
    body = resp.json()["messages"]
    assert body[0]["imageUrl"] == "/b/chat-photos/7/abc.png?sig=x"
    assert "image_key" not in body[0]  # 내부 키는 노출 안 함


async def test_history_no_image_key_no_url(client, store):
    await store.append("chat:history:guest:g4", "안녕", "안녕하세요")
    async with client as ac:
        resp = await ac.get("/ai/chatbot/history", params={"session_id": "g4"})
    body = resp.json()["messages"]
    assert "imageUrl" not in body[0]
