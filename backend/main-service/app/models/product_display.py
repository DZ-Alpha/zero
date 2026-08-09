import uuid
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, Numeric, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ProductDisplay(Base):
    """Read-only public product view owned by the data pipeline."""

    __tablename__ = "v_product_display"
    __table_args__ = {"schema": "service"}

    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    display_name: Mapped[str] = mapped_column(Text)
    product_name: Mapped[str] = mapped_column(String(255))
    brand_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    report_no: Mapped[str | None] = mapped_column(String(50), nullable=True)
    food_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    sugars: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    calories: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    image_url: Mapped[str] = mapped_column(Text)
    brand_prefixed: Mapped[bool] = mapped_column(Boolean)


class ProductSwapPick(Base):
    """Deduplicated read-only candidates for recommendations and swaps."""

    __tablename__ = "v_product_swap_pick"
    __table_args__ = {"schema": "service"}

    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    display_name: Mapped[str] = mapped_column(Text)
    product_name: Mapped[str] = mapped_column(String(255))
    brand_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    report_no: Mapped[str | None] = mapped_column(String(50), nullable=True)
    food_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    sugars: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    calories: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    image_url: Mapped[str] = mapped_column(Text)
    variant_count: Mapped[int] = mapped_column(BigInteger)
    variant_brands: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
