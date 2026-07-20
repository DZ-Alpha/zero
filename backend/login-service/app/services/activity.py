import os
import time
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event_outbox import EventOutbox


def uuid7() -> uuid.UUID:
    """RFC 9562 UUIDv7 (시간순 정렬) — 표준 라이브러리에 아직 없어 직접 생성."""
    ms = int(time.time() * 1000)
    rand = bytearray(os.urandom(10))
    b = bytearray(ms.to_bytes(6, "big")) + rand
    b[6] = (b[6] & 0x0F) | 0x70
    b[8] = (b[8] & 0x3F) | 0x80
    return uuid.UUID(bytes=bytes(b))


async def enqueue_activity(
    session: AsyncSession,
    *,
    event_type: str,
    user_id: int,
    producer: str,
    properties: dict,
    trace_id: str | None = None,
) -> EventOutbox:
    """service.event_outbox에 user.activity.raw용 이벤트를 넣는다 (개발팀
    요청서 "사용자 행동 이벤트 흐름" 절 — diet-service의 동명 헬퍼와 동일 계약).

    Mongo analytics 파이프라인이 소비한다. event_type은 반드시 "user."로
    시작해야 한다. properties에 JWT, email, 생년월일, 신체정보, 이미지
    byte/key/URL, 검색어 원문을 넣지 않는다. user_id는 반드시 인증된
    public.users.id 정수.

    호출자가 commit해야 한다 — login-service의 user_store.get_or_create_user()가
    이미 자체 트랜잭션을 커밋해버리는 구조라, 로그인 성공과 완전히 같은
    트랜잭션으로 묶지는 못한다(별도 커밋). 개발팀 요청서 예시는 단일
    트랜잭션을 전제하지만, 이 서비스 기존 구조를 지금 크게 리팩터링하는 건
    범위 밖이라 감안하고 남긴다.
    """
    if not event_type.startswith("user."):
        raise ValueError(f'activity event_type은 "user."로 시작해야 합니다: {event_type}')

    event_id = uuid7()
    payload = {
        "event_id": str(event_id),
        "event_type": event_type,
        "user_id": int(user_id),
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "producer": producer,
        "schema_version": 1,
        "trace_id": trace_id,
        "properties": properties,
    }
    entry = EventOutbox(
        event_id=event_id,
        event_type=event_type,
        producer=producer,
        user_id=int(user_id),
        trace_id=trace_id,
        payload=payload,
        schema_version=1,
    )
    session.add(entry)
    await session.commit()
    return entry
