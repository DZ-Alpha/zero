import uuid
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models.product_alternative import CategorySugarStats, ProductAlternative
from app.models.product_display import ProductDisplay, ProductSwapPick
from app.models.product_tag import ProductTag


@dataclass(frozen=True)
class AlternativeRead:
    product: ProductSwapPick
    rank: int
    similarity: Decimal
    sugar_delta_g: Decimal
    sugar_delta_pct: Decimal | None
    kcal_delta: Decimal | None


async def get_product_alternatives(
    db: AsyncSession,
    product_id: uuid.UUID,
    limit: int = 3,
) -> list[AlternativeRead]:
    """Read precomputed candidates and map duplicate variants to one card.

    ``product_alternatives`` points at base product ids while the public swap
    view exposes one representative per report number. Candidates without a
    report number remain distinct by product id (migration 013). Old rows can
    remain in production until the batch is rerun, so the public query repeats
    the food type, comparison unit, similarity and reduction checks.
    """
    source_display = aliased(ProductDisplay)
    alt_display = aliased(ProductDisplay)
    has_report_no = and_(
        alt_display.report_no.is_not(None),
        func.btrim(alt_display.report_no) != "",
    )
    representative_match = or_(
        and_(has_report_no, ProductSwapPick.report_no == alt_display.report_no),
        and_(~has_report_no, ProductSwapPick.product_id == alt_display.product_id),
    )
    stmt = (
        select(ProductAlternative, ProductSwapPick)
        .join(source_display, source_display.product_id == ProductAlternative.product_id)
        .join(alt_display, alt_display.product_id == ProductAlternative.alt_product_id)
        .join(ProductSwapPick, representative_match)
        .where(
            ProductAlternative.product_id == product_id,
            source_display.food_type.is_not(None),
            alt_display.food_type == source_display.food_type,
            ProductSwapPick.food_type == source_display.food_type,
            source_display.serving_value.is_not(None),
            alt_display.serving_value == source_display.serving_value,
            ProductSwapPick.serving_value == source_display.serving_value,
            source_display.serving_unit.is_not(None),
            func.lower(func.btrim(alt_display.serving_unit))
            == func.lower(func.btrim(source_display.serving_unit)),
            func.lower(func.btrim(ProductSwapPick.serving_unit))
            == func.lower(func.btrim(source_display.serving_unit)),
            ProductAlternative.similarity >= Decimal("0.70"),
            ProductAlternative.sugar_delta_g <= Decimal("-0.50"),
            or_(
                ProductAlternative.sugar_delta_g <= Decimal("-2.00"),
                ProductAlternative.sugar_delta_pct <= Decimal("-20.00"),
            ),
            ProductSwapPick.sugars < source_display.sugars,
        )
        .order_by(ProductAlternative.rank)
    )
    rows = (await db.execute(stmt)).all()

    candidates: list[AlternativeRead] = []
    seen: set[uuid.UUID] = set()
    for alternative, product in rows:
        if product.product_id in seen:
            continue
        seen.add(product.product_id)
        candidates.append(
            AlternativeRead(
                product=product,
                rank=alternative.rank,
                similarity=alternative.similarity,
                sugar_delta_g=alternative.sugar_delta_g,
                sugar_delta_pct=alternative.sugar_delta_pct,
                kcal_delta=alternative.kcal_delta,
            )
        )
        if len(candidates) == limit:
            break
    return candidates


async def get_category_sugar_stats(
    db: AsyncSession,
    product_id: uuid.UUID,
) -> CategorySugarStats | None:
    stmt = (
        select(CategorySugarStats)
        .join(ProductTag, ProductTag.tag_id == CategorySugarStats.tag_id)
        .where(ProductTag.product_id == product_id)
        .limit(1)
    )
    return (await db.execute(stmt)).scalar_one_or_none()
