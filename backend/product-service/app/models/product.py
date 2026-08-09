import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Product(Base):
    """Product Service 소유. 다른 서비스는 읽기 전용으로만 참조한다.

    2026-07-16 데이터팀 재설계 반영(레시피_상품_데이터명세서_v0.2) — 실제 DB
    재확인 완료. commerce_product_id/publish_status/created_at/updated_at
    컬럼은 더 이상 존재하지 않는다(운영 관리용으로 저희 쪽에서 임의로 추가했던
    컬럼들 — 데이터팀 재생성 시 빠짐). report_no/manufacturer_name/food_type/
    serving_value/serving_unit이 신규 추가됐다.
    """

    __tablename__ = "products"
    __table_args__ = {"schema": "service"}

    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    report_no: Mapped[str | None] = mapped_column(String(50), nullable=True)
    product_name: Mapped[str] = mapped_column(String(255))
    brand_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    manufacturer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    food_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    serving_value: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), nullable=True)
    serving_unit: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # 영양성분 — calories/sugars는 실제 DB에서 NOT NULL
    calories: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    carbohydrate: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    sugars: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    protein: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    fat: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    sodium: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    # 원재료
    ingredient_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 상품 정보 — image_url만 NOT NULL, purchase_url은 nullable
    image_url: Mapped[str] = mapped_column(Text)
    purchase_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 데이터 출처·검증 시각. 007_columns_recipes_products.sql에서 추가됐고
    # 기존 행은 NULL이 정상이다.
    source: Mapped[str | None] = mapped_column(String(30), nullable=True)
    last_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
