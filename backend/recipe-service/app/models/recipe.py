from datetime import datetime
from decimal import Decimal

from sqlalchemy import JSON, DateTime, Numeric, SmallInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Recipe(Base):
    """데이터팀의 저당 레시피 유튜브 파이프라인이 소유/적재하는 테이블
    (레시피_데이터명세서_v0.2.xlsx) — 이 서비스는 읽기 전용."""

    __tablename__ = "recipes"
    __table_args__ = {"schema": "service"}

    id: Mapped[int] = mapped_column(primary_key=True)
    video_id: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(255))
    thumbnail_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    steps: Mapped[list] = mapped_column(JSON)
    total_sugar_g: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    total_kcal: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    base_sugar_g: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    base_kcal: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    sugar_reduction_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    comparison_status: Mapped[str] = mapped_column(String(20))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source: Mapped[str | None] = mapped_column(String(30), nullable=True)
    category: Mapped[str | None] = mapped_column(Text, nullable=True)
    cook_time_min: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
