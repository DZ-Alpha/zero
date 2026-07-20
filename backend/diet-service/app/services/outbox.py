import os
import time
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event_outbox import EventOutbox

# payload에 넣으면 안 되는 것들 — 개인정보/원본 미디어/자유문자열. 문서 지침
# (개발팀 요청서 "공통 outbox publisher" 절) 그대로. 여기서는 강제하지 않고
# 호출부 책임으로 둔다 — 호출부가 이미 job_id/image_key 같은 식별자만 넘기게
# 설계돼 있어서 별도 검증 계층은 과설계.


def uuid7() -> uuid.UUID:
    """RFC 9562 UUIDv7 (시간순 정렬) — 표준 라이브러리에 아직 없어 직접 생성.

    event.activity.raw payload의 event_id로 쓴다 (개발팀 요청서 지정).
    """
    ms = int(time.time() * 1000)
    rand = bytearray(os.urandom(10))
    b = bytearray(ms.to_bytes(6, "big")) + rand
    b[6] = (b[6] & 0x0F) | 0x70
    b[8] = (b[8] & 0x3F) | 0x80
    return uuid.UUID(bytes=bytes(b))


async def enqueue_outbox(
    session: AsyncSession,
    *,
    event_type: str,
    producer: str,
    payload: dict,
    user_id: int | None = None,
    aggregate_type: str | None = None,
    aggregate_id: str | None = None,
    trace_id: str | None = None,
    schema_version: int = 1,
) -> EventOutbox:
    """호출자의 트랜잭션 안에서 outbox row를 추가한다 (commit은 호출자 책임).

    Kafka로의 실제 발행은 zero-db 쪽 outbox publisher가 이 테이블을 폴링해서
    한다 — 여기서는 Kafka client를 쓰지 않는다. 업무 이벤트(diet.* 등, worker가
    구독)에 쓴다 — 사용자 행동 분석 이벤트는 enqueue_activity()를 쓴다.
    """
    entry = EventOutbox(
        event_type=event_type,
        producer=producer,
        payload=payload,
        user_id=user_id,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        trace_id=trace_id,
        schema_version=schema_version,
    )
    session.add(entry)
    await session.flush()
    return entry


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
    요청서 "사용자 행동 이벤트 흐름" 절 — 공통 outbox 헬퍼 그대로 이식).

    Mongo analytics 파이프라인(dangdang_analytics.user_activity_events)이
    소비한다 — 업무 로직 subscriber는 없다. event_type은 반드시 "user."로
    시작해야 한다. properties에 JWT, email, 생년월일, 신체정보, 이미지
    byte/key/URL, 검색어 원문을 넣지 않는다 — user_id는 반드시 JWT
    payload["user_id"]에서 온 정수 public.users.id.
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
    await session.flush()
    return entry
