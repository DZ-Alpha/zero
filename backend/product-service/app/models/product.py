import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Product(Base):
    """Product Service 소유. 다른 서비스는 읽기 전용으로만 참조한다."""

    __tablename__ = "products"
    __table_args__ = {"schema": "service"}

    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    commerce_product_id: Mapped[str | None] = mapped_column(String(100), unique=True, nullable=True)
    product_name: Mapped[str] = mapped_column(String(255))
    brand_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    # 영양성분 (AD-0103 기준)
    calories: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    carbohydrate: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    sugars: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    protein: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    fat: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    sodium: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    # 원재료 (AD-0104 기준)
    ingredient_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 상품 정보
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    purchase_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 대용량 상품 추천용 (PR-0305)
    bulk_purchase_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    publish_status: Mapped[str] = mapped_column(String(20), default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
