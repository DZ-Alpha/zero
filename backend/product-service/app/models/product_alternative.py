import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Integer, Numeric, SmallInteger, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ProductAlternative(Base):
    """Read-only mapping for the precomputed product swap candidates."""

    __tablename__ = "product_alternatives"
    __table_args__ = {"schema": "product"}

    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    alt_product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    rank: Mapped[int] = mapped_column(SmallInteger)
    similarity: Mapped[Decimal] = mapped_column(Numeric(6, 4))
    sugar_delta_g: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    sugar_delta_pct: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    kcal_delta: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CategorySugarStats(Base):
    """Read-only mapping for category-level sugar comparison copy."""

    __tablename__ = "mv_category_sugar_stats"
    __table_args__ = {"schema": "service"}

    tag_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    tag_code: Mapped[str] = mapped_column(String)
    tag_name: Mapped[str] = mapped_column(String)
    product_count: Mapped[int] = mapped_column(Integer)
    avg_sugar: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    median_sugar: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    min_sugar: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    max_sugar: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    zero_sugar_count: Mapped[int] = mapped_column(Integer)
    avg_calories: Mapped[Decimal | None] = mapped_column(Numeric(10, 1), nullable=True)
