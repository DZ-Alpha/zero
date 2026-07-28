from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Integer, Numeric, SmallInteger, String
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
    # main-service의 health_profile_store.upsert_health_profile이 건강정보
    # 필드가 하나라도 채워질 때 이 값도 같이 세팅되도록 강제한다(DB CHECK
    # ck_health_consent까지 걸려있어 "건강정보는 있는데 동의는 없음" 상태 자체가
    # 불가능하다) — 즉 NULL이 아니면 곧 동의한 것이다. PR-0303이 이 값 없이
    # 건강정보를 AI(제3자 API)로 보내고 있던 걸 여기 참조에 컬럼을 추가해 막는다.
    health_data_consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
