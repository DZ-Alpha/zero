import uuid
from dataclasses import dataclass

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models.product_display import ProductSwapPick
from app.models.product_tag import ProductTag
from app.models.user_preference import UserPreference

_RECOMMEND_LIMIT = 20


@dataclass(frozen=True)
class RecommendationResult:
    products: list[ProductSwapPick]
    personalized: bool
    matched_preference_ids: list[uuid.UUID]
    reason: str | None


def _without_allergens(stmt, allergen_tag_ids: list[uuid.UUID]):
    if not allergen_tag_ids:
        return stmt
    allergen_product_tag = aliased(ProductTag)
    return stmt.where(
        ~exists(
            select(1).where(
                allergen_product_tag.product_id == ProductSwapPick.product_id,
                allergen_product_tag.tag_id.in_(allergen_tag_ids),
            )
        )
    )


async def get_recommended_products(db: AsyncSession, user_id: int) -> RecommendationResult:
    preference_stmt = select(
        UserPreference.preference_id,
        UserPreference.preference_type,
        UserPreference.tag_id,
    ).where(UserPreference.user_id == user_id)
    preference_rows = (await db.execute(preference_stmt)).all()

    interest_rows = [
        row for row in preference_rows if row.preference_type == "INTEREST_CATEGORY" and row.tag_id
    ]
    interest_tag_ids = [row.tag_id for row in interest_rows]
    allergen_tag_ids = [
        row.tag_id
        for row in preference_rows
        if row.preference_type == "ALLERGEN" and row.tag_id
    ]

    if interest_tag_ids:
        personalized_stmt = (
            select(ProductSwapPick)
            .join(ProductTag, ProductTag.product_id == ProductSwapPick.product_id)
            .where(ProductTag.tag_id.in_(interest_tag_ids))
            .distinct()
            .order_by(ProductSwapPick.display_name)
            .limit(_RECOMMEND_LIMIT)
        )
        personalized_stmt = _without_allergens(personalized_stmt, allergen_tag_ids)
        products = list((await db.execute(personalized_stmt)).scalars().all())
        if products:
            matched_tag_stmt = select(ProductTag.tag_id).where(
                ProductTag.product_id.in_([product.product_id for product in products]),
                ProductTag.tag_id.in_(interest_tag_ids),
            ).distinct()
            matched_tag_ids = set((await db.execute(matched_tag_stmt)).scalars().all())
            return RecommendationResult(
                products=products,
                personalized=True,
                matched_preference_ids=[
                    row.preference_id for row in interest_rows if row.tag_id in matched_tag_ids
                ],
                reason=None,
            )

    fallback_stmt = select(ProductSwapPick).order_by(ProductSwapPick.display_name).limit(
        _RECOMMEND_LIMIT
    )
    fallback_stmt = _without_allergens(fallback_stmt, allergen_tag_ids)
    products = list((await db.execute(fallback_stmt)).scalars().all())
    return RecommendationResult(
        products=products,
        personalized=False,
        matched_preference_ids=[],
        reason="NO_MATCHING_PRODUCTS" if interest_tag_ids else "NO_PREFERENCES",
    )
