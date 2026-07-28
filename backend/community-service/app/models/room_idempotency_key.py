from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class RoomIdempotencyKey(Base):
    """§9 "생성·참여·초대 재발급·댓글·콕 찌르기는 Idempotency-Key를 지원해야
    한다" 요구사항 지원용 — 얌로그_백엔드_연동_최종_정리.md §7의 스키마 목록에는
    없지만, 그 요구사항 자체를 구현하려면 재시도 요청과 원본 요청을 구분할
    상태 저장소가 필요해서 추가했다. 같은 (user_id, key)로 다시 오면 실제
    처리를 다시 하지 않고 저장된 응답을 그대로 반환한다(services/
    idempotency.py 참고)."""

    __tablename__ = "room_idempotency_keys"
    __table_args__ = {"schema": "community"}

    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    response_status: Mapped[int] = mapped_column(Integer)
    response_body: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
