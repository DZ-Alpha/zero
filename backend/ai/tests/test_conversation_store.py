import fakeredis.aioredis
import pytest

from app.memory.conversation_store import ConversationStore


@pytest.fixture
def store():
    r = fakeredis.aioredis.FakeRedis(decode_responses=True)
    return ConversationStore(r, max_turns=3, ttl_seconds=100)


KEY = "chat:history:user:1"


async def test_append_then_load_roundtrip(store):
    await store.append(KEY, "안녕", "안녕하세요")
    msgs = await store.load(KEY, turns=6)
    assert msgs == [
        {"role": "user", "text": "안녕"},
        {"role": "assistant", "text": "안녕하세요"},
    ]


async def test_load_respects_turn_window(store):
    for i in range(5):
        await store.append(KEY, f"q{i}", f"a{i}")
    msgs = await store.load(KEY, turns=2)  # 최근 2턴=4메시지
    assert [m["text"] for m in msgs] == ["q3", "a3", "q4", "a4"]


async def test_max_turns_trims_old(store):
    # max_turns=3 → 최대 6메시지만 남는다
    for i in range(5):
        await store.append(KEY, f"q{i}", f"a{i}")
    all_msgs = await store.load_all(KEY)
    assert len(all_msgs) == 6
    assert all_msgs[0]["text"] == "q2"  # q0,q1 턴은 밀려남


async def test_ttl_is_set(store):
    await store.append(KEY, "안녕", "안녕하세요")
    ttl = await store._redis.ttl(KEY)
    assert 0 < ttl <= 100


async def test_load_none_key_returns_empty(store):
    assert await store.load(None) == []
    assert await store.load_all(None) == []


async def test_append_none_key_is_noop(store):
    await store.append(None, "안녕", "안녕하세요")  # 예외 없이 무시


async def test_corrupt_element_skipped(store):
    await store._redis.rpush(KEY, "not-json")
    await store.append(KEY, "안녕", "안녕하세요")
    msgs = await store.load(KEY)
    assert {"role": "user", "text": "안녕"} in msgs
    # 손상 원소는 빠지고 정상 2개만
    assert len(msgs) == 2


async def test_trailing_user_message_is_healed(store):
    # Redis 부분쓰기(RPUSH user 성공, assistant 실패)로 오염된 키를 시뮬레이션:
    # trailing lone user 메시지만 남은 상태
    await store._redis.rpush(KEY, '{"role": "user", "text": "orphan"}')
    msgs = await store.load(KEY)
    assert not msgs or msgs[-1]["role"] == "assistant"

    msgs_all = await store.load_all(KEY)
    assert not msgs_all or msgs_all[-1]["role"] == "assistant"


class _BoomRedis:
    async def lrange(self, *a, **k):
        raise ConnectionError("down")

    async def rpush(self, *a, **k):
        raise ConnectionError("down")


async def test_load_swallows_redis_error():
    s = ConversationStore(_BoomRedis())
    assert await s.load(KEY) == []


async def test_append_swallows_redis_error():
    s = ConversationStore(_BoomRedis())
    await s.append(KEY, "a", "b")  # 예외 없이 무시
