from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content import ContentArticle, ContentCollection, ContentCollectionProduct
from app.models.product_display import ProductDisplay
from app.models.product_tag import ProductTag
from app.models.tag import Tag


async def list_published_articles(db: AsyncSession, limit: int) -> list[ContentArticle]:
    stmt = (
        select(ContentArticle)
        .where(
            ContentArticle.is_published.is_(True),
            ContentArticle.body_md.is_not(None),
            func.length(func.btrim(ContentArticle.body_md)) > 0,
        )
        .order_by(ContentArticle.sort_order, ContentArticle.created_at.desc())
        .limit(limit)
    )
    return list((await db.execute(stmt)).scalars().all())


async def get_published_article(
    db: AsyncSession,
    slug: str,
) -> ContentArticle | None:
    stmt = select(ContentArticle).where(
        ContentArticle.slug == slug,
        ContentArticle.is_published.is_(True),
        ContentArticle.body_md.is_not(None),
        func.length(func.btrim(ContentArticle.body_md)) > 0,
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def list_published_collections(db: AsyncSession) -> list[ContentCollection]:
    stmt = (
        select(ContentCollection)
        .where(ContentCollection.is_published.is_(True))
        .order_by(ContentCollection.sort_order, ContentCollection.slug)
    )
    return list((await db.execute(stmt)).scalars().all())


def _rule_limit(rule: dict[str, object]) -> int:
    value = rule.get("limit", 20)
    if isinstance(value, bool) or not isinstance(value, int):
        return 20
    return min(max(value, 1), 50)


async def resolve_collection_products(
    db: AsyncSession,
    collection: ContentCollection,
) -> list[ProductDisplay]:
    rule = collection.rule_json
    if rule is None:
        stmt = (
            select(ProductDisplay)
            .join(
                ContentCollectionProduct,
                ContentCollectionProduct.product_id == ProductDisplay.product_id,
            )
            .where(ContentCollectionProduct.slug == collection.slug)
            .order_by(ContentCollectionProduct.position, ProductDisplay.display_name)
            .limit(50)
        )
        return list((await db.execute(stmt)).scalars().all())

    stmt = select(ProductDisplay)
    category = rule.get("category")
    if isinstance(category, str) and category:
        stmt = (
            stmt.join(ProductTag, ProductTag.product_id == ProductDisplay.product_id)
            .join(Tag, Tag.tag_id == ProductTag.tag_id)
            .where(Tag.tag_type == "CATEGORY", Tag.tag_code == category)
        )

    max_sugar = rule.get("max_sugar")
    if isinstance(max_sugar, (int, float)) and not isinstance(max_sugar, bool):
        stmt = stmt.where(ProductDisplay.sugars <= max_sugar)

    sort = rule.get("sort")
    if sort == "sugar_desc":
        stmt = stmt.order_by(ProductDisplay.sugars.desc(), ProductDisplay.display_name)
    else:
        stmt = stmt.order_by(ProductDisplay.sugars.asc(), ProductDisplay.display_name)
    stmt = stmt.limit(_rule_limit(rule))
    return list((await db.execute(stmt)).scalars().all())
