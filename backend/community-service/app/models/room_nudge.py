import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class RoomNudge(Base):
    """콕 찌르기 발신 이력 — 중복/빈도 제한(§11)을 여기 최근 행 조회로 판단한다.
    (room_id, target_user_id, record_date, meal_type, sender_id) 조합으로 유일한
    DB 제약을 걸지는 않았다 — 그러면 하루에 한 번만 영구히 허용되는 셈이라
    "빈도 제한"(쿨다운) 요구와 안 맞는다. 대신 room_store.send_nudge가 같은
    조합의 가장 최근 created_at을 보고 쿨다운(NUDGE_COOLDOWN_SECONDS) 이내면
    429를 낸다."""

    __tablename__ = "room_nudges"
    __table_args__ = {"schema": "community"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    room_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("community.rooms.id", ondelete="CASCADE")
    )
    target_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    record_date: Mapped[date] = mapped_column(Date)
    meal_type: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
