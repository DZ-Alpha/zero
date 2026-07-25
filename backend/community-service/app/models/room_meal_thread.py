import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class RoomMealThread(Base):
    """댓글·반응이 매달리는 안정적인 대상. 식단 원본(Diet Service)은 여러
    meal_log로 쪼개질 수 있어(사진+레시피+저당픽 동시 등록) 그 자체를 FK로 못
    쓴다 — 대신 (room_id, user_id, record_date, meal_type) 조합마다 이 thread를
    하나씩 get-or-create해서 그 id를 API의 mealId로 쓴다."""

    __tablename__ = "room_meal_threads"
    __table_args__ = (
        UniqueConstraint("room_id", "user_id", "record_date", "meal_type", name="uq_room_meal_thread"),
        {"schema": "community"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    room_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("community.rooms.id", ondelete="CASCADE")
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    record_date: Mapped[date] = mapped_column(Date)
    # BREAKFAST | LUNCH | DINNER | SNACK — diet-service와 동일 표기(대문자)로
    # 저장하고, API 응답 직전에만 frontend contracts.ts의 소문자로 바꾼다
    # (services/room_store.py의 _to_frontend_meal_type 참고).
    meal_type: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
