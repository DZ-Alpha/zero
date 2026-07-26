import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Room(Base):
    """얌로그 모임(방). 얌로그_백엔드_연동_최종_정리.md §7 스키마 그대로."""

    __tablename__ = "rooms"
    __table_args__ = {"schema": "community"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(24))
    emoji: Mapped[str] = mapped_column(String(16))
    # RESTRICT: 방장 계정이 실수로 삭제돼 모임 소유자가 붕 뜨는 걸 막는다
    # (Notice.author_user_id와 같은 이유).
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ranking_opt_in: Mapped[bool] = mapped_column(Boolean, default=True)
    # soft delete — §5 "soft delete 여부는 운영 정책으로 확정" 전까지는 항상
    # soft delete로 두고(deleted_at 세팅), 하드 삭제 정책이 나오면 그때 별도
    # batch job으로 뺀다. 목록/조회 쪽은 전부 deleted_at IS NULL로 필터링한다.
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
