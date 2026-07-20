import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, SmallInteger, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class _ExternalBase(DeclarativeBase):
    """app.core.database.Base와 일부러 분리한 별도 Base.

    event_outbox는 데이터/인프라팀이 zero-db 이벤트 파이프라인용으로 소유·
    생성한 테이블(diet-service와 공유) — login-service의 app/main.py lifespan은
    화이트리스트 없이 Base.metadata.create_all()을 통째로 돌리므로, 같은
    Base를 쓰면 이 서비스가 소유하지 않은 테이블에 DDL을 날리게 된다.
    """


class EventOutbox(_ExternalBase):
    __tablename__ = "event_outbox"
    __table_args__ = {"schema": "service"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), default=uuid.uuid4, unique=True)
    event_type: Mapped[str] = mapped_column(String(100))
    user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    producer: Mapped[str] = mapped_column(String(50))
    aggregate_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    aggregate_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    schema_version: Mapped[int] = mapped_column(SmallInteger, default=1)
    trace_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    publish_attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
