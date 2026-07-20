import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.product import Product
from app.models.user_health_profile_ref import UserHealthProfileRef
from app.services.ai_service import (
    generate_product_summary,
    generate_sweetener_description,
    generate_user_feature_info,
)
from app.services.product_store import (
    ProductNotFoundError,
    get_product,
    get_product_tags,
    get_sweetener_tags_for_product,
    list_favorites,
    toggle_favorite,
)

logger = logging.getLogger("product_service.product")

router = APIRouter(prefix="/product")


def _to_uuid(product_id: str) -> uuid.UUID:
    try:
        return uuid.UUID(product_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="유효하지 않은 상품 ID 형식입니다.")


def _product_detail(p: Product, tags: list) -> dict[str, object]:
    category_tags = [t for t in tags if t.tag_type == "CATEGORY"]
    allergen_tags = [t for t in tags if t.tag_type == "ALLERGEN"]
    return {
        # PR-0201
        "name": p.product_name,
        "brand": p.brand_name,
        "category": category_tags[0].tag_name if category_tags else None,
        # PR-0202
        "cal": float(p.calories) if p.calories is not None else None,
        "dang": float(p.sugars) if p.sugars is not None else None,
        "natu": float(p.sodium) if p.sodium is not None else None,
        "danb": float(p.protein) if p.protein is not None else None,
        "carb": float(p.carbohydrate) if p.carbohydrate is not None else None,
        "fat": float(p.fat) if p.fat is not None else None,
        # PR-0203
        "ingredi": p.ingredient_text,
        "allerg": [t.tag_name for t in allergen_tags],
        # 기본 정보
        "imageUrl": p.image_url,
        "purchaseUrl": p.purchase_url,
    }


@router.get("")
async def get_product_detail(
    id: str = Query(..., description="상품 UUID"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    """PR-0201~0203: 상품 기본정보 + 영양성분 + 원재료/알레르기."""
    pid = _to_uuid(id)
    try:
        product = await get_product(db, pid)
    except ProductNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    tags = await get_product_tags(db, pid)
    return _product_detail(product, tags)


@router.get("/ai")
async def get_ai_summary(
    id: str = Query(..., description="상품 UUID"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    """PR-0301: AI 한줄 요약 (런타임 생성, 저장 안 함)."""
    pid = _to_uuid(id)
    try:
        product = await get_product(db, pid)
    except ProductNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    tags = await get_product_tags(db, pid)
    summary = await generate_product_summary(product, tags)
    return {"ai-oneline": summary}


@router.get("/gammi-info")
async def get_sweetener_info(
    id: str = Query(..., description="상품 UUID"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    """PR-0302: 감미료(대체 당) 설명."""
    pid = _to_uuid(id)
    try:
        product = await get_product(db, pid)
    except ProductNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    sweetener_tags = await get_sweetener_tags_for_product(db, pid)
    description = await generate_sweetener_description(product, sweetener_tags)
    return {"gammi-info": description}


@router.get("/user-feature-info")
async def get_user_feature_info(
    id: str = Query(..., description="상품 UUID"),
    db: AsyncSession = Depends(get_db),
    payload: dict = Depends(get_current_user),
) -> dict[str, object]:
    """PR-0303: 사용자 맞춤 영양 설명 (연령/성별/일일 목표 기반)."""
    pid = _to_uuid(id)
    user_id: int = payload["user_id"]

    try:
        product = await get_product(db, pid)
    except ProductNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    tags = await get_product_tags(db, pid)

    # Main Service 소유 건강프로필 읽기 전용 조회
    profile_stmt = select(UserHealthProfileRef).where(UserHealthProfileRef.user_id == user_id)
    profile_result = await db.execute(profile_stmt)
    profile = profile_result.scalar_one_or_none()

    info = await generate_user_feature_info(
        product=product,
        tags=tags,
        birth_year=profile.birth_year if profile else None,
        gender=profile.gender if profile else None,
        daily_calorie_target=float(profile.daily_calorie_target) if profile and profile.daily_calorie_target else None,
        daily_sugar_target_g=float(profile.daily_sugar_target_g) if profile and profile.daily_sugar_target_g else None,
    )
    return {"user-feature-info": info}


@router.get("/user-group-info")
async def get_user_group_info(
    id: str = Query(..., description="상품 UUID"),
    db: AsyncSession = Depends(get_db),
    payload: dict = Depends(get_current_user),
) -> dict[str, object]:
    """PR-0304: 사용자 맞춤 그룹화 코멘트 (보류 - 기획 미확정)."""
    pid = _to_uuid(id)
    user_id: int = payload["user_id"]

    try:
        await get_product(db, pid)
    except ProductNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    profile_stmt = select(UserHealthProfileRef).where(UserHealthProfileRef.user_id == user_id)
    profile_result = await db.execute(profile_stmt)
    profile = profile_result.scalar_one_or_none()

    return {
        "status": "PREPARING",
        "message": "그룹화 코멘트 기능은 준비 중입니다.",
        "age": None,
        "gender": profile.gender if profile else None,
        "list-products": [],
    }


@router.get("/recommend/many")
async def get_bulk_recommendation(
    id: str = Query(..., description="상품 UUID"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    """PR-0305: 같은 카테고리 대용량 상품 추천.

    실제 service.products 테이블에 대용량 구매 링크를 담을 컬럼이 없어서
    (bulk_purchase_url 미존재) 준비 중 상태로 둔다 — 컬럼이 추가되면 구현.
    """
    pid = _to_uuid(id)
    try:
        await get_product(db, pid)
    except ProductNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return {
        "status": "PREPARING",
        "message": "대용량 상품 추천 기능은 준비 중입니다. (service.products에 대용량 구매 링크 컬럼 필요)",
        "list-products": [],
    }


@router.get("/review")
async def get_reviews(
    id: str = Query(..., description="상품 UUID"),
    is_more: bool = Query(False, alias="is-more"),
    page: int = Query(1, ge=1),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    """PR-0306: 상품 리뷰 (service.product_reviews 테이블 미정 — 준비 중)."""
    pid = _to_uuid(id)
    try:
        await get_product(db, pid)
    except ProductNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return {
        "status": "PREPARING",
        "message": "리뷰 기능은 준비 중입니다. (service.product_reviews 테이블 설계 필요)",
        "reviews": [],
    }


class FavoriteToggleBody(BaseModel):
    id: str


def _favorite_list_item(p: Product) -> dict[str, object]:
    return {
        "id": str(p.product_id),
        "name": p.product_name,
        "brand": p.brand_name,
        "image": p.image_url,
    }


@router.post("/favorite")
async def toggle_product_favorite(
    body: FavoriteToggleBody,
    db: AsyncSession = Depends(get_db),
    payload: dict = Depends(get_current_user),
) -> dict[str, object]:
    """PR-0307: 상품 찜 등록/해제 토글."""
    pid = _to_uuid(body.id)
    user_id: int = payload["user_id"]
    try:
        liked = await toggle_favorite(db, pid, user_id)
    except ProductNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return {"status": "SUCCESS", "liked": liked}


@router.get("/favorite/list")
async def get_product_favorite_list(
    db: AsyncSession = Depends(get_db),
    payload: dict = Depends(get_current_user),
) -> dict[str, object]:
    """PR-0308: 찜한 상품 목록."""
    user_id: int = payload["user_id"]
    products = await list_favorites(db, user_id)
    return {"list-products": [_favorite_list_item(p) for p in products]}
