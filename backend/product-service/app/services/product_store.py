import uuid
import logging
from decimal import Decimal

from sqlalchemy import select, or_, func, exists, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product
from app.models.product_favorite import ProductFavorite
from app.models.product_tag import ProductTag
from app.models.tag import Tag

logger = logging.getLogger("product_service.store")

PAGE_SIZE = 20


class ProductNotFoundError(Exception):
    pass


class TagNotFoundError(Exception):
    pass


def _apply_search_filters(stmt, query: str | None, category_codes: list[str] | None, warning_codes: list[str] | None):
    if query:
        pattern = f"%{query}%"
        stmt = stmt.where(
            or_(
                Product.product_name.ilike(pattern),
                Product.brand_name.ilike(pattern),
            )
        )

    if category_codes:
        # 카테고리 코드 중 하나라도 일치하는 상품 (OR 조건)
        stmt = stmt.where(
            exists(
                select(ProductTag.product_id)
                .join(Tag, Tag.tag_id == ProductTag.tag_id)
                .where(
                    ProductTag.product_id == Product.product_id,
                    Tag.tag_type == "CATEGORY",
                    Tag.tag_code.in_(category_codes),
                    Tag.active.is_(True),
                )
            )
        )

    if warning_codes:
        # 주의 성분(알레르기) 코드가 하나라도 있으면 제외 (NOT EXISTS)
        stmt = stmt.where(
            ~exists(
                select(ProductTag.product_id)
                .join(Tag, Tag.tag_id == ProductTag.tag_id)
                .where(
                    ProductTag.product_id == Product.product_id,
                    Tag.tag_type == "ALLERGEN",
                    Tag.tag_code.in_(warning_codes),
                )
            )
        )

    return stmt


async def search_products(
    db: AsyncSession,
    query: str | None,
    category_codes: list[str] | None,
    warning_codes: list[str] | None,
    sort: str | None,
    page: int,
) -> list[Product]:
    stmt = _apply_search_filters(select(Product), query, category_codes, warning_codes)

    # rank 구현은 Kafka/MongoDB 파이프라인 필요. created_at 컬럼이 데이터팀
    # 재설계로 삭제돼 "최신순" 기본 정렬도 더 이상 불가능 — 두 경우 다 이름순.
    stmt = stmt.order_by(Product.product_name)

    stmt = stmt.offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def count_search_products(
    db: AsyncSession,
    query: str | None,
    category_codes: list[str] | None,
    warning_codes: list[str] | None,
) -> int:
    """P1-1(PRODUCTION_HANDOFF.md) — search_products와 동일한 필터로 전체 건수를 센다
    (프론트 total/hasNext 계산용)."""
    stmt = _apply_search_filters(
        select(func.count()).select_from(Product), query, category_codes, warning_codes
    )
    return (await db.execute(stmt)).scalar_one()


async def get_product_tags_bulk(db: AsyncSession, product_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[Tag]]:
    """P1-1(PRODUCTION_HANDOFF.md) — 검색 결과 카드에 태그를 붙일 때 상품마다 따로
    조회하는 N+1을 피하려고 페이지 전체를 한 번에 조회한다."""
    if not product_ids:
        return {}
    stmt = (
        select(ProductTag.product_id, Tag)
        .join(Tag, Tag.tag_id == ProductTag.tag_id)
        .where(ProductTag.product_id.in_(product_ids), Tag.active.is_(True))
        .order_by(Tag.tag_type, Tag.tag_name)
    )
    result = await db.execute(stmt)
    tags_by_product: dict[uuid.UUID, list[Tag]] = {pid: [] for pid in product_ids}
    for product_id, tag in result.all():
        tags_by_product[product_id].append(tag)
    return tags_by_product


async def autocomplete_products(db: AsyncSession, query: str) -> list[Product]:
    pattern = f"{query}%"
    stmt = (
        select(Product)
        .where(
            or_(
                Product.product_name.ilike(pattern),
                Product.brand_name.ilike(pattern),
            ),
        )
        .order_by(Product.product_name)
        .limit(10)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_product(db: AsyncSession, product_id: uuid.UUID) -> Product:
    stmt = select(Product).where(Product.product_id == product_id)
    result = await db.execute(stmt)
    product = result.scalar_one_or_none()
    if product is None:
        raise ProductNotFoundError(f"상품을 찾을 수 없습니다. id={product_id}")
    return product


async def get_product_tags(db: AsyncSession, product_id: uuid.UUID) -> list[Tag]:
    stmt = (
        select(Tag)
        .join(ProductTag, ProductTag.tag_id == Tag.tag_id)
        .where(ProductTag.product_id == product_id, Tag.active.is_(True))
        .order_by(Tag.tag_type, Tag.tag_name)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_sweetener_tags_for_product(db: AsyncSession, product_id: uuid.UUID) -> list[Tag]:
    stmt = (
        select(Tag)
        .join(ProductTag, ProductTag.tag_id == Tag.tag_id)
        .where(
            ProductTag.product_id == product_id,
            Tag.tag_type == "SWEETENER",
            Tag.active.is_(True),
        )
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def create_product(
    db: AsyncSession,
    product_name: str,
    brand_name: str | None,
    category_tag_id: uuid.UUID,
    ingredient_text: str | None,
    image_url: str,
    calories: Decimal,
    sugars: Decimal,
    purchase_url: str | None = None,
    report_no: str | None = None,
    manufacturer_name: str | None = None,
    food_type: str | None = None,
    serving_value: Decimal | None = None,
    serving_unit: str | None = None,
) -> Product:
    # tag 유효성 확인 (CATEGORY, active)
    tag_stmt = select(Tag).where(
        Tag.tag_id == category_tag_id,
        Tag.tag_type == "CATEGORY",
        Tag.active.is_(True),
    )
    tag_result = await db.execute(tag_stmt)
    tag = tag_result.scalar_one_or_none()
    if tag is None:
        raise TagNotFoundError(f"유효한 CATEGORY 태그를 찾을 수 없습니다. tag_id={category_tag_id}")

    if (serving_value is None) != (serving_unit is None):
        raise ValueError("serving_value와 serving_unit은 둘 다 있거나 둘 다 없어야 합니다.")

    product = Product(
        product_id=uuid.uuid4(),
        product_name=product_name,
        brand_name=brand_name,
        ingredient_text=ingredient_text,
        image_url=image_url,
        purchase_url=purchase_url,
        calories=calories,
        sugars=sugars,
        report_no=report_no,
        manufacturer_name=manufacturer_name,
        food_type=food_type,
        serving_value=serving_value,
        serving_unit=serving_unit,
    )
    db.add(product)

    # CATEGORY 태그를 같은 트랜잭션에서 insert (트리거: DEFERRABLE INITIALLY DEFERRED)
    product_tag = ProductTag(product_id=product.product_id, tag_id=category_tag_id, evidence_source="NAME")
    db.add(product_tag)

    await db.commit()
    await db.refresh(product)
    logger.info("product created product_id=%s name=%r", product.product_id, product.product_name)
    return product


async def update_product(
    db: AsyncSession,
    product_id: uuid.UUID,
    **fields: object,
) -> Product:
    product = await get_product(db, product_id)
    allowed = {
        "product_name", "brand_name", "ingredient_text",
        "image_url", "purchase_url",
        "report_no", "manufacturer_name", "food_type", "serving_value", "serving_unit",
    }
    for key, value in fields.items():
        if key in allowed:
            setattr(product, key, value)
    await db.commit()
    await db.refresh(product)
    logger.info("product updated product_id=%s", product_id)
    return product


async def update_nutrition(
    db: AsyncSession,
    product_id: uuid.UUID,
    calories: Decimal | None,
    carbohydrate: Decimal | None,
    sugars: Decimal | None,
    protein: Decimal | None,
    fat: Decimal | None,
    sodium: Decimal | None,
) -> Product:
    product = await get_product(db, product_id)
    product.calories = calories
    product.carbohydrate = carbohydrate
    product.sugars = sugars
    product.protein = protein
    product.fat = fat
    product.sodium = sodium
    await db.commit()
    await db.refresh(product)
    logger.info("nutrition updated product_id=%s", product_id)
    return product


async def toggle_favorite(db: AsyncSession, product_id: uuid.UUID, user_id: int) -> bool:
    """PR-0307: 찜 등록/해제 토글. 반환값은 토글 후 상태(True=찜됨)."""
    await get_product(db, product_id)  # 없는 상품이면 404

    existing = await db.get(ProductFavorite, {"product_id": product_id, "user_id": user_id})
    if existing is not None:
        await db.delete(existing)
        await db.commit()
        return False

    db.add(ProductFavorite(product_id=product_id, user_id=user_id))
    await db.commit()
    return True


async def list_favorites(db: AsyncSession, user_id: int) -> list[Product]:
    """PR-0308: 찜한 상품 목록."""
    stmt = (
        select(Product)
        .join(ProductFavorite, ProductFavorite.product_id == Product.product_id)
        .where(ProductFavorite.user_id == user_id)
        .order_by(ProductFavorite.created_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def update_allergen_tags(
    db: AsyncSession,
    product_id: uuid.UUID,
    ingredient_text: str | None,
    allergen_tag_ids: list[uuid.UUID],
) -> None:
    """원재료 텍스트 업데이트 + ALLERGEN 태그 교체 (기존 삭제 후 재삽입)."""
    product = await get_product(db, product_id)
    product.ingredient_text = ingredient_text

    # 기존 ALLERGEN 태그 삭제
    existing_allergen_stmt = (
        select(ProductTag)
        .join(Tag, Tag.tag_id == ProductTag.tag_id)
        .where(
            ProductTag.product_id == product_id,
            Tag.tag_type == "ALLERGEN",
        )
    )
    result = await db.execute(existing_allergen_stmt)
    for pt in result.scalars().all():
        await db.delete(pt)

    # 신규 ALLERGEN 태그 삽입 (유효성 확인 포함)
    for tag_id in allergen_tag_ids:
        tag_stmt = select(Tag).where(
            Tag.tag_id == tag_id,
            Tag.tag_type == "ALLERGEN",
            Tag.active.is_(True),
        )
        tag_result = await db.execute(tag_stmt)
        if tag_result.scalar_one_or_none() is None:
            raise TagNotFoundError(f"유효한 ALLERGEN 태그를 찾을 수 없습니다. tag_id={tag_id}")
        db.add(ProductTag(product_id=product_id, tag_id=tag_id, evidence_source="INGREDIENT"))

    await db.commit()
    logger.info("allergen tags updated product_id=%s count=%d", product_id, len(allergen_tag_ids))
