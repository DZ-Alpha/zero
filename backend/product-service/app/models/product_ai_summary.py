import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ProductAiSummary(Base):
    """Product Service 소유 — product.product_ai_summaries.

    AI 한줄요약(PR-0301)/감미료 설명(PR-0302)은 Claude 호출 비용이 들어서 한 번
    생성한 결과를 여기 캐싱하고 재사용한다 - 회의 결정(2026-07-27), 없는 상품만
    새로 생성한다. `service` 스키마는 데이터팀 소유라 product_favorites와 같은
    패턴으로 이 서비스 전용 `product` 스키마에 둔다.
    """

    __tablename__ = "product_ai_summaries"
    __table_args__ = {"schema": "product"}

    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("service.products.product_id", ondelete="CASCADE"), primary_key=True
    )
    ai_oneline: Mapped[str | None] = mapped_column(Text, nullable=True)
    gammi_info: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
