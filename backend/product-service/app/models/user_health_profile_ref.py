from decimal import Decimal

from sqlalchemy import Integer, Numeric, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class UserHealthProfileRef(Base):
    """Main Service 소유 테이블 읽기 전용 참조 (PR-0303 맞춤 설명용).
    create_all 대상이 아님 — product-service는 이 테이블을 절대 DDL하지 않는다."""

    __tablename__ = "user_health_profiles"
    __table_args__ = {"schema": "service"}

    user_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    birth_year: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    gender: Mapped[str | None] = mapped_column(String(20), nullable=True)
    daily_calorie_target: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    daily_sugar_target_g: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
