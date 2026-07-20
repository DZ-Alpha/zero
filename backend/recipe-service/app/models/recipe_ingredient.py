from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class RecipeIngredient(Base):
    """읽기 전용 — 데이터팀 파이프라인 소유."""

    __tablename__ = "recipe_ingredients"
    __table_args__ = {"schema": "service"}

    id: Mapped[int] = mapped_column(primary_key=True)
    recipe_id: Mapped[int] = mapped_column(ForeignKey("service.recipes.id"))
    name: Mapped[str] = mapped_column(String(255))
    amount: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # 'common' | 'substituted' — substituted만 recipe_ingredient_products에
    # 대응 행이 있을 수 있다.
    ingredient_type: Mapped[str] = mapped_column(String(20))
    sugar_g: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    kcal: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    core_keyword: Mapped[str | None] = mapped_column(Text, nullable=True)
    # substituted 재료가 원래(비저당/저칼로리) 재료였다면의 당/칼로리 — common은
    # sugar_g/kcal과 동일값. recipe_base_comparisons 테이블이 대체된 자리
    # (data/receipe_spec_v0.4.xlsx 3.3 참고, 2026-07-17 폐기).
    base_sugar_g: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    base_kcal: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
