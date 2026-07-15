import uuid
import logging
from decimal import Decimal

from sqlalchemy import select, or_, func, exists, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product
from app.models.product_tag import ProductTag
from app.models.tag import Tag

logger = logging.getLogger("product_service.store")

_PAGE_SIZE = 20


class ProductNotFoundError(Exception):
    pass


class TagNotFoundError(Exception):
    pass


async def search_products(
    db: AsyncSession,
    query: str | None,
    category_codes: list[str] | None,
    warning_codes: list[str] | None,
    sort: str | None,
    page: int,
) -> list[Product]:
    stmt = (
        select(Product)
        .where(Product.publish_status == "ACTIVE")
    )

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

    if sort == "abc":
        stmt = stmt.order_by(Product.product_name)
    else:
        # 기본: 최신 등록순 (rank 구현은 Kafka/MongoDB 파이프라인 필요 — 현재는 최신순)
        stmt = stmt.order_by(Product.created_at.desc())

    stmt = stmt.offset((page - 1) * _PAGE_SIZE).limit(_PAGE_SIZE)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def autocomplete_products(db: AsyncSession, query: str) -> list[Product]:
    pattern = f"{query}%"
    stmt = (
        select(Product)
        .where(
            Product.publish_status == "ACTIVE",
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


async def get_bulk_candidates(db: AsyncSession, product_id: uuid.UUID) -> list[Product]:
    """같은 카테고리 상품 중 bulk_purchase_url이 있는 것을 최대 5개 반환."""
    # 대상 상품의 CATEGORY tag_id 조회
    cat_stmt = (
        select(ProductTag.tag_id)
        .join(Tag, Tag.tag_id == ProductTag.tag_id)
        .where(
            ProductTag.product_id == product_id,
            Tag.tag_type == "CATEGORY",
        )
        .limit(1)
    )
    cat_result = await db.execute(cat_stmt)
    category_tag_id = cat_result.scalar_one_or_none()

    if category_tag_id is None:
        return []

    stmt = (
        select(Product)
        .join(ProductTag, ProductTag.product_id == Product.product_id)
        .where(
            ProductTag.tag_id == category_tag_id,
            Product.publish_status == "ACTIVE",
            Product.bulk_purchase_url.isnot(None),
            Product.product_id != product_id,
        )
        .order_by(Product.created_at.desc())
        .limit(5)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def create_product(
    db: AsyncSession,
    product_name: str,
    brand_name: str | None,
    category_tag_id: uuid.UUID,
    ingredient_text: str | None,
    image_url: str | None,
    purchase_url: str | None,
    bulk_purchase_url: str | None,
    commerce_product_id: str | None,
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

    product = Product(
        product_id=uuid.uuid4(),
        product_name=product_name,
        brand_name=brand_name,
        ingredient_text=ingredient_text,
        image_url=image_url,
        purchase_url=purchase_url,
        bulk_purchase_url=bulk_purchase_url,
        commerce_product_id=commerce_product_id,
        publish_status="ACTIVE",
    )
    db.add(product)

    # CATEGORY 태그를 같은 트랜잭션에서 insert (트리거: DEFERRABLE INITIALLY DEFERRED)
    product_tag = ProductTag(product_id=product.product_id, tag_id=category_tag_id)
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
        "image_url", "purchase_url", "bulk_purchase_url",
        "publish_status", "commerce_product_id",
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
        db.add(ProductTag(product_id=product_id, tag_id=tag_id))

    await db.commit()
    logger.info("allergen tags updated product_id=%s count=%d", product_id, len(allergen_tag_ids))
