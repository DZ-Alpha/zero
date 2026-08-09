import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, JSON, SmallInteger, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ContentArticle(Base):
    __tablename__ = "articles"
    __table_args__ = {"schema": "content"}

    slug: Mapped[str] = mapped_column(Text, primary_key=True)
    category: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    body_md: Mapped[str | None] = mapped_column(Text, nullable=True)
    read_minutes: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    source_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(SmallInteger)
    is_published: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ContentCollection(Base):
    __tablename__ = "collections"
    __table_args__ = {"schema": "content"}

    slug: Mapped[str] = mapped_column(Text, primary_key=True)
    title: Mapped[str] = mapped_column(Text)
    subtitle: Mapped[str | None] = mapped_column(Text, nullable=True)
    rule_json: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    sort_order: Mapped[int] = mapped_column(SmallInteger)
    is_published: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ContentCollectionProduct(Base):
    __tablename__ = "collection_products"
    __table_args__ = {"schema": "content"}

    slug: Mapped[str] = mapped_column(Text, primary_key=True)
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    position: Mapped[int] = mapped_column(SmallInteger)
