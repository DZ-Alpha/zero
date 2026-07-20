import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, SmallInteger, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class EventOutbox(Base):
    """service.event_outbox — 데이터/인프라팀이 zero-db 이벤트 파이프라인용으로
    소유·생성한 테이블(2026-07-20). 이 서비스는 업무 트랜잭션과 같은 트랜잭션
    안에서 INSERT만 한다 — Kafka 발행은 zero-db의 별도 outbox publisher가
    이 테이블을 폴링해서 수행하므로, 여기서 Kafka 클라이언트를 직접 쓰지 않는다.
    app/services/outbox.py의 enqueue_outbox() 참고.
    """

    __tablename__ = "event_outbox"
    __table_args__ = {"schema": "service"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), default=uuid.uuid4, unique=True)
    event_type: Mapped[str] = mapped_column(String(100))
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    producer: Mapped[str] = mapped_column(String(50))
    # 2026-07-20 운영에서 IntegrityError로 실측 — NOT NULL이다 (모델에 nullable=True로
    # 잘못 적혀 있었음). enqueue_outbox 호출부는 항상 값을 넘겨야 한다.
    aggregate_type: Mapped[str] = mapped_column(String(50))
    aggregate_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    schema_version: Mapped[int] = mapped_column(SmallInteger, default=1)
    trace_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    publish_attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
