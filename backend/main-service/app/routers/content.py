from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.content_store import (
    get_published_article,
    list_published_articles,
    list_published_collections,
    resolve_collection_products,
)

router = APIRouter(prefix="/home/content")
PUBLIC_CACHE_CONTROL = "public, max-age=300, stale-while-revalidate=900"


def _article_summary(article) -> dict[str, object]:
    return {
        "slug": article.slug,
        "category": article.category,
        "title": article.title,
        "summary": article.summary,
        "readMinutes": article.read_minutes,
        "sourceNote": article.source_note,
    }


@router.get("/articles")
async def get_articles(
    response: Response,
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    articles = await list_published_articles(db, limit)
    response.headers["Cache-Control"] = PUBLIC_CACHE_CONTROL
    return {"articles": [_article_summary(article) for article in articles]}


@router.get("/articles/{slug}")
async def get_article(
    slug: str,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    article = await get_published_article(db, slug)
    if article is None:
        raise HTTPException(status_code=404, detail="공개된 읽을거리를 찾을 수 없습니다.")
    response.headers["Cache-Control"] = PUBLIC_CACHE_CONTROL
    return {**_article_summary(article), "bodyMarkdown": article.body_md}


@router.get("/collections")
async def get_collections(
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    collections = await list_published_collections(db)
    payload = []
    for collection in collections:
        products = await resolve_collection_products(db, collection)
        payload.append(
            {
                "slug": collection.slug,
                "title": collection.title,
                "subtitle": collection.subtitle,
                "products": [
                    {
                        "id": str(product.product_id),
                        "name": product.display_name,
                        "brand": product.brand_name,
                        "image": product.image_url,
                        "sugar": float(product.sugars),
                        "calories": float(product.calories),
                    }
                    for product in products
                ],
            }
        )
    response.headers["Cache-Control"] = PUBLIC_CACHE_CONTROL
    return {"collections": payload}
