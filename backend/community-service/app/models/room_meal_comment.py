import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class RoomMealComment(Base):
    __tablename__ = "room_meal_comments"
    __table_args__ = {"schema": "community"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    thread_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("community.room_meal_threads.id", ondelete="CASCADE")
    )
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    # §11 "160자 이하" — 여유를 두고 200으로 컬럼을 잡는다(trim/길이 검증 자체는
    # 라우터에서 먼저 막으므로 컬럼 길이는 최후 방어선).
    message: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # 삭제도 soft delete — 댓글이 사라져도 반응/알림 등 다른 곳에서 참조 중일
    # 수 있어 notice/room 패턴과 동일하게 흔적을 남긴다. 목록 조회는
    # deleted_at IS NULL로 필터링.
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
