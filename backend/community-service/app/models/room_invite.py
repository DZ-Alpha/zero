import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class RoomInvite(Base):
    __tablename__ = "room_invites"
    __table_args__ = {"schema": "community"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    room_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("community.rooms.id", ondelete="CASCADE")
    )
    # 코드 자체는 저장하지 않는다 — 평문 초대코드가 DB 유출 시 그대로 쓰일 수
    # 있어서, 로그인 비밀번호처럼 해시만 저장하고 참여 시 들어온 코드를 같은
    # 방식으로 해시해 비교한다(services/room_store.py 참고).
    code_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
