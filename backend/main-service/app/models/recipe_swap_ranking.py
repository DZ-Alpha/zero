from decimal import Decimal

from sqlalchemy import BigInteger, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class RecipeSwapRanking(Base):
    """Read-only projection of the precomputed recipe sugar ranking."""

    __tablename__ = "v_recipe_swap_ranking"
    __table_args__ = {"schema": "service"}

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    thumbnail_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str | None] = mapped_column(String(30), nullable=True)
    base_sugar_g: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    total_sugar_g: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    sugar_saved_g: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    sugar_reduction_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    total_kcal: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    base_kcal: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    kcal_reduction_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    rnk: Mapped[int] = mapped_column(BigInteger)
