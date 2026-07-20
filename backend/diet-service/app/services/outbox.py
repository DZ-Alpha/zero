from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event_outbox import EventOutbox

# payload에 넣으면 안 되는 것들 — 개인정보/원본 미디어/자유문자열. 문서 지침
# (개발팀 요청서 "공통 outbox publisher" 절) 그대로. 여기서는 강제하지 않고
# 호출부 책임으로 둔다 — 호출부가 이미 job_id/image_key 같은 식별자만 넘기게
# 설계돼 있어서 별도 검증 계층은 과설계.


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
    한다 — 여기서는 Kafka client를 쓰지 않는다.
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
