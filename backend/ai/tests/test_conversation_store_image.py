import fakeredis.aioredis
import pytest

from app.memory.conversation_store import ConversationStore

KEY = "chat:history:user:7"


@pytest.fixture
def store():
    r = fakeredis.aioredis.FakeRedis(decode_responses=True)
    return ConversationStore(r, max_turns=20, ttl_seconds=100)


async def test_append_with_image_key_roundtrip(store):
    await store.append(KEY, "이거 당류?", "케이크네요", image_key="7/abc.png")
    msgs = await store.load_all(KEY)
    assert msgs[0]["role"] == "user"
    assert msgs[0]["text"] == "이거 당류?"
    assert msgs[0]["image_key"] == "7/abc.png"
    assert msgs[1]["role"] == "assistant"
    assert "image_key" not in msgs[1]  # assistant엔 없음


async def test_append_without_image_key_has_no_field(store):
    await store.append(KEY, "안녕", "안녕하세요")
    msgs = await store.load_all(KEY)
    assert "image_key" not in msgs[0]  # 텍스트-only 하위호환


async def test_photo_only_turn_empty_user_text(store):
    await store.append(KEY, "", "케이크네요", image_key="7/abc.png")
    msgs = await store.load_all(KEY)
    assert msgs[0]["text"] == ""
    assert msgs[0]["image_key"] == "7/abc.png"
