import uuid
import logging
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy import and_, case, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product
from app.models.product_display import ProductDisplay
from app.models.product_ai_summary import ProductAiSummary
from app.models.product_favorite import ProductFavorite
from app.models.product_tag import ProductTag
from app.models.tag import Tag

logger = logging.getLogger("product_service.store")

PAGE_SIZE = 20


@dataclass(frozen=True)
class ProductRead:
    """Public product projection with the curated display name.

    ``v_product_display`` intentionally contains only list-level fields. The
    public read path joins it to the base table so detail responses retain
    nutrition and ingredient fields while removed products stay invisible.
    """

    product_id: uuid.UUID
    product_name: str
    raw_product_name: str
    brand_name: str | None
    manufacturer_name: str | None
    food_type: str | None
    serving_value: Decimal | None
    serving_unit: str | None
    calories: Decimal
    carbohydrate: Decimal | None
    sugars: Decimal
    protein: Decimal | None
    fat: Decimal | None
    sodium: Decimal | None
    ingredient_text: str | None
    image_url: str
    purchase_url: str | None
    source: str | None
    last_verified_at: datetime | None


def _public_product(product: Product, display_name: str) -> ProductRead:
    return ProductRead(
        product_id=product.product_id,
        product_name=display_name,
        raw_product_name=product.product_name,
        brand_name=product.brand_name,
        manufacturer_name=product.manufacturer_name,
        food_type=product.food_type,
        serving_value=product.serving_value,
        serving_unit=product.serving_unit,
        calories=product.calories,
        carbohydrate=product.carbohydrate,
        sugars=product.sugars,
        protein=product.protein,
        fat=product.fat,
        sodium=product.sodium,
        ingredient_text=product.ingredient_text,
        image_url=product.image_url,
        purchase_url=product.purchase_url,
        source=product.source,
        last_verified_at=product.last_verified_at,
    )


class ProductNotFoundError(Exception):
    pass


class TagNotFoundError(Exception):
    pass


def _escape_like(value: str) -> str:
    """Return a literal ILIKE pattern fragment (not a user supplied wildcard)."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _normalized_query(query: str | None) -> str | None:
    if query is None:
        return None
    normalized = query.strip()
    return normalized or None


def _has_hangul(value: str) -> bool:
    return any("가" <= char <= "힣" for char in value)


def _max_edit_distance(query: str) -> int:
    """Allow a small, predictable number of typos for Korean product names."""
    length = len(query.replace(" ", ""))
    if length <= 5:
        return 1
    if length <= 12:
        return 2
    return 3


def _fuzzy_search_text(column):
    """Ignore a leading marketing label such as ``(저당)`` for typo matching."""
    return func.btrim(func.regexp_replace(column, r"^\s*\([^)]*\)\s*", ""))


def _korean_edit_distance(column, query: str):
    return func.levenshtein_less_equal(
        _fuzzy_search_text(column), query, _max_edit_distance(query)
    )


def _name_or_brand_matches(query: str):
    """Name/brand partial matches plus typo matches.

    The cluster database uses ``C`` locale, where pg_trgm cannot form Korean
    trigrams. Korean queries therefore use fuzzystrmatch's Levenshtein
    function, while other queries use pg_trgm's indexed ``%`` operator.
    """
    contains_pattern = f"%{_escape_like(query)}%"
    matches = [
        ProductDisplay.display_name.ilike(contains_pattern, escape="\\"),
        ProductDisplay.brand_name.ilike(contains_pattern, escape="\\"),
    ]
    if _has_hangul(query):
        max_distance = _max_edit_distance(query)
        matches.extend((
            _korean_edit_distance(ProductDisplay.display_name, query) <= max_distance,
            _korean_edit_distance(ProductDisplay.brand_name, query) <= max_distance,
        ))
    elif len(query) >= 2:
        matches.extend((
            ProductDisplay.display_name.op("%")(query),
            ProductDisplay.brand_name.op("%")(query),
        ))
    return or_(*matches)


def _apply_search_order(stmt, query: str | None, sort: str | None):
    """Keep exact/partial results above fuzzy matches, then sort fuzzy by score."""
    if sort == "sugar_asc":
        return stmt.order_by(ProductDisplay.sugars.asc(), ProductDisplay.display_name.asc())
    if sort == "calorie_asc":
        return stmt.order_by(ProductDisplay.calories.asc(), ProductDisplay.display_name.asc())
    if sort == "abc" or query is None:
        return stmt.order_by(ProductDisplay.display_name)

    prefix_pattern = f"{_escape_like(query)}%"
    contains_pattern = f"%{_escape_like(query)}%"
    normalized_query = query.lower()
    match_priority = case(
        (func.lower(ProductDisplay.display_name) == normalized_query, 5),
        (func.lower(ProductDisplay.brand_name) == normalized_query, 4),
        (ProductDisplay.display_name.ilike(prefix_pattern, escape="\\"), 3),
        (ProductDisplay.brand_name.ilike(prefix_pattern, escape="\\"), 2),
        (ProductDisplay.display_name.ilike(contains_pattern, escape="\\"), 1),
        else_=0,
    )
    if _has_hangul(query):
        max_distance = _max_edit_distance(query)
        edit_distance = func.least(
            _korean_edit_distance(ProductDisplay.display_name, query),
            func.coalesce(_korean_edit_distance(ProductDisplay.brand_name, query), max_distance + 1),
        )
        return stmt.order_by(match_priority.desc(), edit_distance.asc(), ProductDisplay.display_name)

    similarity_score = func.greatest(
        func.similarity(ProductDisplay.display_name, query),
        func.coalesce(func.similarity(ProductDisplay.brand_name, query), 0.0),
    )
    return stmt.order_by(match_priority.desc(), similarity_score.desc(), ProductDisplay.display_name)


def _apply_search_filters(stmt, query: str | None, category_codes: list[str] | None, warning_codes: list[str] | None):
    normalized_query = _normalized_query(query)
    if normalized_query:
        stmt = stmt.where(_name_or_brand_matches(normalized_query))

    if category_codes:
        # 카테고리 코드 중 하나라도 일치하는 상품 (OR 조건)
        stmt = stmt.where(
            exists(
                select(ProductTag.product_id)
                .join(Tag, Tag.tag_id == ProductTag.tag_id)
                .where(
                    ProductTag.product_id == ProductDisplay.product_id,
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
                    ProductTag.product_id == ProductDisplay.product_id,
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
) -> list[ProductRead]:
    normalized_query = _normalized_query(query)
    stmt = _apply_search_filters(
        select(Product, ProductDisplay.display_name).join(
            ProductDisplay, ProductDisplay.product_id == Product.product_id
        ),
        normalized_query,
        category_codes,
        warning_codes,
    )
    stmt = _apply_search_order(stmt, normalized_query, sort)

    stmt = stmt.offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE)
    rows = (await db.execute(stmt)).all()
    return [_public_product(product, display_name) for product, display_name in rows]


async def search_products_with_total(
    db: AsyncSession,
    query: str | None,
    category_codes: list[str] | None,
    warning_codes: list[str] | None,
    sort: str | None,
    page: int,
) -> tuple[list[ProductRead], int]:
    """Return one page and its total count with one database round trip.

    An empty page beyond the end needs one fallback count query so callers can
    still distinguish "no matches" from "page is past the last result".
    """
    normalized_query = _normalized_query(query)
    stmt = _apply_search_filters(
        select(
            Product,
            ProductDisplay.display_name,
            func.count().over().label("total_count"),
        ).join(ProductDisplay, ProductDisplay.product_id == Product.product_id),
        normalized_query,
        category_codes,
        warning_codes,
    )
    stmt = _apply_search_order(stmt, normalized_query, sort)
    stmt = stmt.offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE)

    rows = (await db.execute(stmt)).all()
    if rows:
        products = [_public_product(row[0], row[1]) for row in rows]
        return products, int(rows[0][2])
    if page > 1:
        return [], await count_search_products(db, query, category_codes, warning_codes)
    return [], 0


async def count_search_products(
    db: AsyncSession,
    query: str | None,
    category_codes: list[str] | None,
    warning_codes: list[str] | None,
) -> int:
    """P1-1(PRODUCTION_HANDOFF.md) — search_products와 동일한 필터로 전체 건수를 센다
    (프론트 total/hasNext 계산용)."""
    stmt = _apply_search_filters(
        select(func.count()).select_from(ProductDisplay),
        _normalized_query(query),
        category_codes,
        warning_codes,
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


async def autocomplete_products(db: AsyncSession, query: str) -> list[ProductRead]:
    normalized_query = _normalized_query(query)
    if normalized_query is None:
        return []

    stmt = (
        select(Product, ProductDisplay.display_name)
        .join(ProductDisplay, ProductDisplay.product_id == Product.product_id)
        .where(_name_or_brand_matches(normalized_query))
    )
    stmt = _apply_search_order(stmt, normalized_query, sort="rank").limit(10)
    rows = (await db.execute(stmt)).all()
    return [_public_product(product, display_name) for product, display_name in rows]


async def get_product(db: AsyncSession, product_id: uuid.UUID) -> Product:
    stmt = select(Product).where(Product.product_id == product_id)
    result = await db.execute(stmt)
    product = result.scalar_one_or_none()
    if product is None:
        raise ProductNotFoundError(f"상품을 찾을 수 없습니다. id={product_id}")
    return product


async def get_public_product(db: AsyncSession, product_id: uuid.UUID) -> ProductRead:
    """Return a visible product with its curated display name."""
    stmt = (
        select(Product, ProductDisplay.display_name)
        .join(ProductDisplay, ProductDisplay.product_id == Product.product_id)
        .where(Product.product_id == product_id)
    )
    row = (await db.execute(stmt)).one_or_none()
    if row is None:
        raise ProductNotFoundError(f"상품을 찾을 수 없습니다. id={product_id}")
    return _public_product(row[0], row[1])


async def get_product_tags(db: AsyncSession, product_id: uuid.UUID) -> list[Tag]:
    stmt = (
        select(Tag)
        .join(ProductTag, ProductTag.tag_id == Tag.tag_id)
        .where(ProductTag.product_id == product_id, Tag.active.is_(True))
        .order_by(Tag.tag_type, Tag.tag_name)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_product_with_tags(
    db: AsyncSession,
    product_id: uuid.UUID,
) -> tuple[ProductRead, list[Tag]]:
    """Load a product and all active tags in a single database round trip."""
    stmt = (
        select(Product, ProductDisplay.display_name, Tag)
        .join(ProductDisplay, ProductDisplay.product_id == Product.product_id)
        .outerjoin(ProductTag, ProductTag.product_id == Product.product_id)
        .outerjoin(
            Tag,
            and_(Tag.tag_id == ProductTag.tag_id, Tag.active.is_(True)),
        )
        .where(Product.product_id == product_id)
        .order_by(Tag.tag_type, Tag.tag_name)
    )
    rows = (await db.execute(stmt)).all()
    if not rows:
        raise ProductNotFoundError(f"상품을 찾을 수 없습니다. id={product_id}")
    product = _public_product(rows[0][0], rows[0][1])
    return product, [tag for _, _, tag in rows if tag is not None]


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
    await get_public_product(db, product_id)

    existing = await db.get(ProductFavorite, {"product_id": product_id, "user_id": user_id})
    if existing is not None:
        await db.delete(existing)
        await db.commit()
        return False

    db.add(ProductFavorite(product_id=product_id, user_id=user_id))
    await db.commit()
    return True


async def list_favorites(db: AsyncSession, user_id: int) -> list[ProductRead]:
    """PR-0308: 찜한 상품 목록."""
    stmt = (
        select(Product, ProductDisplay.display_name)
        .join(ProductDisplay, ProductDisplay.product_id == Product.product_id)
        .join(ProductFavorite, ProductFavorite.product_id == Product.product_id)
        .where(ProductFavorite.user_id == user_id)
        .order_by(ProductFavorite.created_at.desc())
    )
    rows = (await db.execute(stmt)).all()
    return [_public_product(product, display_name) for product, display_name in rows]


async def get_ai_summary_cache(db: AsyncSession, product_id: uuid.UUID) -> ProductAiSummary | None:
    """AI 한줄요약(PR-0301)/감미료 설명(PR-0302) 캐시 조회 — 회의 결정(2026-07-27)
    으로 한 번 생성한 결과를 재사용한다."""
    return await db.get(ProductAiSummary, product_id)


async def upsert_ai_summary_cache(
    db: AsyncSession,
    product_id: uuid.UUID,
    ai_oneline: str | None = None,
    gammi_info: str | None = None,
) -> None:
    cache = await db.get(ProductAiSummary, product_id)
    if cache is None:
        cache = ProductAiSummary(product_id=product_id)
        db.add(cache)
    if ai_oneline is not None:
        cache.ai_oneline = ai_oneline
    if gammi_info is not None:
        cache.gammi_info = gammi_info
    await db.commit()


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
