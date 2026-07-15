import logging
import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_admin
from app.core.database import get_db
from app.services.product_store import (
    ProductNotFoundError,
    TagNotFoundError,
    create_product,
    update_allergen_tags,
    update_nutrition,
    update_product,
)

logger = logging.getLogger("product_service.admin")

router = APIRouter(prefix="/admin")


class ProductCreateBody(BaseModel):
    name: str
    brand: str | None = None
    category_tag_id: str
    ingredient_text: str | None = None
    image_url: str | None = None
    purchase_url: str | None = None
    bulk_purchase_url: str | None = None
    commerce_product_id: str | None = None
    # 영양성분 (선택, AD-0103과 통합 가능)
    calories: Decimal | None = None
    carbohydrate: Decimal | None = None
    sugars: Decimal | None = None
    protein: Decimal | None = None
    fat: Decimal | None = None
    sodium: Decimal | None = None


class ProductUpdateBody(BaseModel):
    id: str
    name: str | None = None
    brand: str | None = None
    ingredient_text: str | None = None
    image_url: str | None = None
    purchase_url: str | None = None
    bulk_purchase_url: str | None = None
    publish_status: str | None = None
    commerce_product_id: str | None = None


class NutritionBody(BaseModel):
    id: str
    cal: Decimal | None = None
    natu: Decimal | None = None
    dang: Decimal | None = None
    dan: Decimal | None = None
    carb: Decimal | None = None
    fat: Decimal | None = None


class IngredientsBody(BaseModel):
    id: str
    ingredient_text: str | None = None
    allergen_tag_ids: list[str] = []


def _parse_uuid(value: str, label: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"유효하지 않은 {label} UUID 형식입니다.")


@router.post("")
async def admin_endpoint(
    body: dict,
    db: AsyncSession = Depends(get_db),
    _admin: dict = Depends(get_current_admin),
) -> dict[str, object]:
    """AD-0101~0104 통합 엔드포인트 (menu 파라미터로 분기).
    기능명세서 API-Spec 기준: /admin?menu=manage-item|manage-nutrients|manage-ingredients"""
    menu = body.get("menu", "")

    if menu == "manage-item":
        if "id" in body:
            return await _handle_update_product(body, db)
        return await _handle_create_product(body, db)

    if menu == "manage-nutrients":
        return await _handle_update_nutrition(body, db)

    if menu == "manage-ingredients":
        return await _handle_update_ingredients(body, db)

    raise HTTPException(status_code=422, detail=f"알 수 없는 menu 값입니다: {menu!r}")


async def _handle_create_product(body: dict, db: AsyncSession) -> dict[str, object]:
    """AD-0101: 상품 등록."""
    required = ["name", "category_tag_id"]
    for field in required:
        if not body.get(field):
            raise HTTPException(status_code=422, detail=f"필수 필드 누락: {field}")

    category_tag_id = _parse_uuid(body["category_tag_id"], "category_tag_id")

    try:
        product = await create_product(
            db,
            product_name=body["name"],
            brand_name=body.get("brand"),
            category_tag_id=category_tag_id,
            ingredient_text=body.get("ingredient_text"),
            image_url=body.get("image_url"),
            purchase_url=body.get("purchase_url"),
            bulk_purchase_url=body.get("bulk_purchase_url"),
            commerce_product_id=body.get("commerce_product_id"),
        )
    except TagNotFoundError as e:
        raise HTTPException(status_code=422, detail=str(e))

    logger.info("admin: product created product_id=%s by admin", product.product_id)
    return {"status": "SUCCESS", "id": str(product.product_id)}


async def _handle_update_product(body: dict, db: AsyncSession) -> dict[str, object]:
    """AD-0102: 상품 수정."""
    pid = _parse_uuid(body["id"], "상품 ID")
    fields = {k: v for k, v in {
        "product_name": body.get("name"),
        "brand_name": body.get("brand"),
        "ingredient_text": body.get("ingredient_text"),
        "image_url": body.get("image_url"),
        "purchase_url": body.get("purchase_url"),
        "bulk_purchase_url": body.get("bulk_purchase_url"),
        "publish_status": body.get("publish_status"),
        "commerce_product_id": body.get("commerce_product_id"),
    }.items() if v is not None}

    try:
        await update_product(db, pid, **fields)
    except ProductNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    logger.info("admin: product updated product_id=%s", pid)
    return {"status": "SUCCESS"}


async def _handle_update_nutrition(body: dict, db: AsyncSession) -> dict[str, object]:
    """AD-0103: 영양성분 등록/수정."""
    if not body.get("id"):
        raise HTTPException(status_code=422, detail="필수 필드 누락: id")
    pid = _parse_uuid(body["id"], "상품 ID")

    def _to_decimal(val: object) -> Decimal | None:
        return Decimal(str(val)) if val is not None else None

    try:
        await update_nutrition(
            db,
            product_id=pid,
            calories=_to_decimal(body.get("cal")),
            carbohydrate=_to_decimal(body.get("carb")),
            sugars=_to_decimal(body.get("dang")),
            protein=_to_decimal(body.get("dan")),
            fat=_to_decimal(body.get("fat")),
            sodium=_to_decimal(body.get("natu")),
        )
    except ProductNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    logger.info("admin: nutrition updated product_id=%s", pid)
    return {"status": "SUCCESS", "id": str(pid)}


async def _handle_update_ingredients(body: dict, db: AsyncSession) -> dict[str, object]:
    """AD-0104: 원재료/알레르기 등록."""
    if not body.get("id"):
        raise HTTPException(status_code=422, detail="필수 필드 누락: id")
    pid = _parse_uuid(body["id"], "상품 ID")

    allergen_ids_raw: list[str] = body.get("allergen_tag_ids", [])
    allergen_tag_ids = [_parse_uuid(tid, "allergen_tag_id") for tid in allergen_ids_raw]

    try:
        await update_allergen_tags(
            db,
            product_id=pid,
            ingredient_text=body.get("ingredient_text"),
            allergen_tag_ids=allergen_tag_ids,
        )
    except ProductNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except TagNotFoundError as e:
        raise HTTPException(status_code=422, detail=str(e))

    logger.info("admin: ingredients updated product_id=%s", pid)
    return {"status": "SUCCESS", "id": str(pid)}
