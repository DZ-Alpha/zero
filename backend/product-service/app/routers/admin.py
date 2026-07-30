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
    # 실제 DB에서 NOT NULL — 상품 생성 시 필수
    image_url: str
    calories: Decimal
    sugars: Decimal
    # 실제 DB에서 nullable — 선택
    purchase_url: str | None = None
    report_no: str | None = None
    manufacturer_name: str | None = None
    food_type: str | None = None
    serving_value: Decimal | None = None
    serving_unit: str | None = None
    # 나머지 영양성분은 선택 (AD-0103에서 별도 등록/수정 가능)
    carbohydrate: Decimal | None = None
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
    report_no: str | None = None
    manufacturer_name: str | None = None
    food_type: str | None = None
    serving_value: Decimal | None = None
    serving_unit: str | None = None


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


# ── RESTful 분리 엔드포인트 (Istio 전환 요청서 §1, 2026-07-30) ────────────────
# 프록시가 JSON body의 menu 값을 읽어 서비스를 고르던 구조(아래 레거시 POST
# /admin)를 없애기 위해 기능별 URL을 분리했다. 경로만으로 소유 서비스가
# 정해진다: /admin/products/* → product-service(여기).


@router.post("/products")
async def create_product_endpoint(
    body: dict,
    db: AsyncSession = Depends(get_db),
    _admin: dict = Depends(get_current_admin),
) -> dict[str, object]:
    """AD-0101: 상품 등록."""
    return await _handle_create_product(body, db)


@router.patch("/products/{product_id}")
async def update_product_endpoint(
    product_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
    _admin: dict = Depends(get_current_admin),
) -> dict[str, object]:
    """AD-0102: 상품 수정."""
    return await _handle_update_product({**body, "id": product_id}, db)


@router.post("/products/{product_id}/nutrients")
async def update_nutrition_endpoint(
    product_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
    _admin: dict = Depends(get_current_admin),
) -> dict[str, object]:
    """AD-0103: 영양성분 등록/수정."""
    return await _handle_update_nutrition({**body, "id": product_id}, db)


@router.post("/products/{product_id}/ingredients")
async def update_ingredients_endpoint(
    product_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
    _admin: dict = Depends(get_current_admin),
) -> dict[str, object]:
    """AD-0104: 원재료/알레르기 등록."""
    return await _handle_update_ingredients({**body, "id": product_id}, db)


@router.post("")
async def admin_endpoint(
    body: dict,
    db: AsyncSession = Depends(get_db),
    _admin: dict = Depends(get_current_admin),
) -> dict[str, object]:
    """[레거시] AD-0101~0104 통합 엔드포인트 (menu 파라미터로 분기).
    Istio 전환 요청서 §1로 위 RESTful 경로들이 정식이 됐다 - frontend-admin이
    전부 새 경로로 전환된 뒤 제거 예정. 그때까지 하위호환으로만 유지."""
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
    """AD-0101: 상품 등록. image_url/calories/sugars는 실제 DB에서 NOT NULL이라
    필수로 취급한다."""
    required = ["name", "category_tag_id", "image_url", "calories", "sugars"]
    for field in required:
        if body.get(field) is None:
            raise HTTPException(status_code=422, detail=f"필수 필드 누락: {field}")

    category_tag_id = _parse_uuid(body["category_tag_id"], "category_tag_id")

    try:
        product = await create_product(
            db,
            product_name=body["name"],
            brand_name=body.get("brand"),
            category_tag_id=category_tag_id,
            ingredient_text=body.get("ingredient_text"),
            image_url=body["image_url"],
            calories=Decimal(str(body["calories"])),
            sugars=Decimal(str(body["sugars"])),
            purchase_url=body.get("purchase_url"),
            report_no=body.get("report_no"),
            manufacturer_name=body.get("manufacturer_name"),
            food_type=body.get("food_type"),
            serving_value=Decimal(str(body["serving_value"])) if body.get("serving_value") is not None else None,
            serving_unit=body.get("serving_unit"),
        )
    except TagNotFoundError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    remaining_nutrition = {k: body.get(k) for k in ("carbohydrate", "protein", "fat", "sodium")}
    if any(v is not None for v in remaining_nutrition.values()):
        await update_nutrition(
            db,
            product_id=product.product_id,
            calories=product.calories,
            sugars=product.sugars,
            carbohydrate=Decimal(str(remaining_nutrition["carbohydrate"])) if remaining_nutrition["carbohydrate"] is not None else None,
            protein=Decimal(str(remaining_nutrition["protein"])) if remaining_nutrition["protein"] is not None else None,
            fat=Decimal(str(remaining_nutrition["fat"])) if remaining_nutrition["fat"] is not None else None,
            sodium=Decimal(str(remaining_nutrition["sodium"])) if remaining_nutrition["sodium"] is not None else None,
        )

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
        "report_no": body.get("report_no"),
        "manufacturer_name": body.get("manufacturer_name"),
        "food_type": body.get("food_type"),
        "serving_value": Decimal(str(body["serving_value"])) if body.get("serving_value") is not None else None,
        "serving_unit": body.get("serving_unit"),
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
