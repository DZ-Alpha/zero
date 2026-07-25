import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class RoomMember(Base):
    __tablename__ = "room_members"
    __table_args__ = {"schema": "community"}

    room_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("community.rooms.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    # "owner" | "member" — RoomRole(frontend/lib/rooms/contracts.ts)와 일치.
    role: Mapped[str] = mapped_column(String(10), default="member")
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # 탈퇴/내보내기 시 row를 지우지 않고 left_at만 채운다 — §4 "가입일 이후
    # 과거 식단 표시" 판단과, 나간 뒤에도 남아있는 room_meal_comments/reactions
    # 작성자 이력(author_id FK)이 끊기지 않게 하기 위함. 활성 멤버 조건은
    # 어디서나 left_at IS NULL이다.
    left_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    nudge_notifications: Mapped[bool] = mapped_column(Boolean, default=True)
    activity_notifications: Mapped[bool] = mapped_column(Boolean, default=True)
