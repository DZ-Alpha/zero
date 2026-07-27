import json

import fakeredis.aioredis
import pytest
from httpx import ASGITransport, AsyncClient

from app.api import chatbot as chatbot_api
from app.context.dummy import DummyUserContextProvider
from app.handlers.base import FeatureHandler, HandlerInput, HandlerResult
from app.main import app
from app.memory.conversation_store import ConversationStore
from app.router.dispatcher import Dispatcher
from app.router.intent import IntentClassifier
from app.schemas import Intent

_ANSWER = "초코케이크네요! 당류 약 45g이에요."


class _PhotoHandler(FeatureHandler):
    async def handle(self, data: HandlerInput) -> HandlerResult:
        return HandlerResult(msg=_ANSWER, is_img=True, image_key="7/abc.png")


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


def _deltas(body: str) -> list[str]:
    out = []
    for line in body.split("\n\n"):
        line = line.strip()
        if not line.startswith("data: "):
            continue
        evt = json.loads(line[len("data: "):])
        if "delta" in evt:
            out.append(evt["delta"])
    return out


async def test_photo_answer_is_split_into_many_deltas(client):
    # else 분기(사진분석)도 글자 단위로 쪼개 타이핑되게 흘려야 한다.
    async with client as ac:
        async with ac.stream("POST", "/ai/chatbot/stream",
                             json={"msg": "이거 당류?", "img": "data:image/png;base64,AAAA",
                                   "session_id": "g1"}) as resp:
            assert resp.status_code == 200
            body = ""
            async for chunk in resp.aiter_text():
                body += chunk
    deltas = _deltas(body)
    # 통째 1개가 아니라 여러 조각으로 쪼개져야 한다(글자 단위).
    assert len(deltas) > 1
    # 이어붙이면 원문과 같아야 한다(내용 손실 없음).
    assert "".join(deltas) == _ANSWER
