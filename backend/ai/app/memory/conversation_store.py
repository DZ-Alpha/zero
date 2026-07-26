import json
import logging
from typing import TypedDict

logger = logging.getLogger("ai_chatbot")

Message = TypedDict("Message", {"role": str, "text": str})


class ConversationStore:
    """세션키별 대화를 Redis List에 저장/조회한다. Redis는 best-effort —
    어떤 실패도 예외를 밖으로 던지지 않고 빈 결과/무시로 폴백한다."""

    def __init__(self, redis, *, max_turns: int = 20, ttl_seconds: int = 86400) -> None:
        self._redis = redis
        self._max_msgs = max_turns * 2
        self._ttl = ttl_seconds

    async def load(self, session_key: str | None, turns: int = 6) -> list[Message]:
        if not session_key:
            return []
        try:
            raw = await self._redis.lrange(session_key, -turns * 2, -1)
        except Exception:
            logger.warning("conversation load failed (key=%s)", session_key, exc_info=True)
            return []
        return self._parse(raw)

    async def load_all(self, session_key: str | None) -> list[Message]:
        if not session_key:
            return []
        try:
            raw = await self._redis.lrange(session_key, 0, -1)
        except Exception:
            logger.warning("conversation load_all failed (key=%s)", session_key, exc_info=True)
            return []
        return self._parse(raw)

    async def append(self, session_key: str | None, user_text: str, assistant_text: str) -> None:
        if not session_key:
            return
        try:
            async with self._redis.pipeline(transaction=True) as pipe:
                pipe.rpush(session_key, json.dumps({"role": "user", "text": user_text}, ensure_ascii=False))
                pipe.rpush(session_key, json.dumps({"role": "assistant", "text": assistant_text}, ensure_ascii=False))
                pipe.ltrim(session_key, -self._max_msgs, -1)
                pipe.expire(session_key, self._ttl)
                await pipe.execute()
        except Exception:
            logger.warning("conversation append failed (key=%s)", session_key, exc_info=True)

    @staticmethod
    def _parse(raw: list[str]) -> list[Message]:
        out: list[Message] = []
        for item in raw:
            try:
                obj = json.loads(item)
                out.append({"role": obj["role"], "text": obj["text"]})
            except (ValueError, KeyError, TypeError):
                continue  # 손상 원소는 건너뛴다
        if out and out[-1]["role"] != "assistant":
            # Redis 부분쓰기(RPUSH user 성공, assistant 실패 등)로 오염된
            # trailing lone user 메시지는 self-heal로 제거한다.
            out.pop()
        return out
