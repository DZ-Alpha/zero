import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class RoomReport(Base):
    __tablename__ = "room_reports"
    __table_args__ = {"schema": "community"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    room_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("community.rooms.id", ondelete="CASCADE")
    )
    reporter_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    # "meal" | "comment" — ReportRoomContentInput.targetType(contracts.ts)와 일치.
    target_type: Mapped[str] = mapped_column(String(10))
    # meal이면 room_meal_threads.id, comment면 room_meal_comments.id — 신고 후에도
    # 대상이 삭제될 수 있어 FK로 강제하지 않고 텍스트로 느슨하게 참조한다
    # (신고 이력은 원본이 지워져도 남아있어야 하므로).
    target_id: Mapped[str] = mapped_column(String(64))
    reason: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
