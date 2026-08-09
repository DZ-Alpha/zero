import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, SmallInteger, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ProductReview(Base):
    """Read mapping for product reviews managed by migration 006."""

    __tablename__ = "product_reviews"
    __table_args__ = {"schema": "product"}

    review_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    user_id: Mapped[int] = mapped_column(Integer)
    rating: Mapped[int] = mapped_column(SmallInteger)
    content: Mapped[str] = mapped_column(Text)
    is_seed: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ProductReviewSentiment(Base):
    """Read-only, asynchronously calculated review sentiment summary."""

    __tablename__ = "product_review_sentiment"
    __table_args__ = {"schema": "product"}

    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    review_count: Mapped[int] = mapped_column(Integer)
    positive_count: Mapped[int] = mapped_column(Integer)
    neutral_count: Mapped[int] = mapped_column(Integer)
    negative_count: Mapped[int] = mapped_column(Integer)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    includes_seed: Mapped[bool] = mapped_column(Boolean)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
