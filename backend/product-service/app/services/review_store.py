import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product_review import ProductReview, ProductReviewSentiment


async def list_product_reviews(
    db: AsyncSession,
    product_id: uuid.UUID,
    page: int,
    page_size: int,
) -> tuple[list[ProductReview], int]:
    stmt = (
        select(ProductReview, func.count().over().label("total_count"))
        .where(ProductReview.product_id == product_id)
        .order_by(ProductReview.created_at.desc(), ProductReview.review_id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await db.execute(stmt)).all()
    if rows:
        return [row[0] for row in rows], int(rows[0][1])
    if page > 1:
        count_stmt = select(func.count()).select_from(ProductReview).where(
            ProductReview.product_id == product_id
        )
        return [], int((await db.execute(count_stmt)).scalar_one())
    return [], 0


async def get_product_review_sentiment(
    db: AsyncSession,
    product_id: uuid.UUID,
) -> ProductReviewSentiment | None:
    return await db.get(ProductReviewSentiment, product_id)
