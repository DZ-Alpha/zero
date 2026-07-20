import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.product import Product
from app.models.tag import Tag
from app.services.product_store import (
    PAGE_SIZE,
    autocomplete_products,
    count_search_products,
    get_product_tags_bulk,
    search_products,
)

logger = logging.getLogger("product_service.search")

router = APIRouter()


def _search_item(p: Product, tags: list[Tag]) -> dict[str, object]:
    category_tags = [t for t in tags if t.tag_type == "CATEGORY"]
    serving = f"{p.serving_value}{p.serving_unit}" if p.serving_value is not None and p.serving_unit else None
    return {
        "id": str(p.product_id),
        "name": p.product_name,
        "desc": p.brand_name or "",
        "url": p.image_url or "",
        # PRODUCTION_HANDOFF.md P1-1 — 카드 렌더링에 필요한 필드
        "brand": p.brand_name,
        "category": category_tags[0].tag_name if category_tags else None,
        "serving": serving,
        "sugar": float(p.sugars) if p.sugars is not None else None,
        "calories": float(p.calories) if p.calories is not None else None,
        "image": p.image_url,
        "tags": [t.tag_name for t in tags],
    }


def _autocomplete_item(p: Product) -> dict[str, object]:
    return {
        "id": str(p.product_id),
        "name": p.product_name,
    }


@router.get("/search")
async def search(
    query: str | None = Query(None, description="검색어 (제품명/브랜드)"),
    category: str | None = Query(None, description="카테고리 코드, 콤마 구분 (PR-0103)"),
    warning: str | None = Query(None, description="주의 성분(알레르기) 코드, 콤마 구분 (PR-0104)"),
    sort: str | None = Query(None, description="정렬: rank(기본) | abc (PR-0105)"),
    page: int = Query(1, ge=1, description="페이지 번호"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    """PR-0101~0105 / MN-0102: 키워드 검색, 카테고리/주의성분 필터, 정렬."""
    category_codes = [c.strip() for c in category.split(",") if c.strip()] if category else None
    warning_codes = [w.strip() for w in warning.split(",") if w.strip()] if warning else None

    products = await search_products(
        db,
        query=query,
        category_codes=category_codes,
        warning_codes=warning_codes,
        sort=sort,
        page=page,
    )
    total = await count_search_products(db, query=query, category_codes=category_codes, warning_codes=warning_codes)
    tags_by_product = await get_product_tags_bulk(db, [p.product_id for p in products])
    logger.info(
        "search query=%r category=%r warning=%r sort=%r page=%d results=%d total=%d",
        query, category, warning, sort, page, len(products), total,
    )
    return {
        "items": [_search_item(p, tags_by_product.get(p.product_id, [])) for p in products],
        "page": page,
        # PRODUCTION_HANDOFF.md P1-1
        "total": total,
        "pageSize": PAGE_SIZE,
        "hasNext": page * PAGE_SIZE < total,
    }


@router.get("/search/recommend")
async def autocomplete(
    query: str = Query(..., min_length=1, description="검색어 앞글자"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    """PR-0102: 검색어 자동완성."""
    products = await autocomplete_products(db, query)
    return {"items": [_autocomplete_item(p) for p in products]}
