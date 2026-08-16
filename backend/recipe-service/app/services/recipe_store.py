from sqlalchemy import exists, func, nulls_last, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.recipe import Recipe
from app.models.recipe_favorite import RecipeFavorite
from app.models.recipe_ingredient import RecipeIngredient
from app.models.recipe_ingredient_product import RecipeIngredientProduct

PAGE_SIZE = 20


class RecipeNotFoundError(Exception):
    pass


def _apply_recipe_filters(
    stmt,
    source: str | None,
    search: str | None = None,
    eligible: bool = False,
    category: str | None = None,
):
    if source:
        stmt = stmt.where(Recipe.source == source)
    if search and search.strip():
        stmt = stmt.where(Recipe.name.ilike(f"%{search.strip()}%"))
    # 카테고리는 서버에서 걸러야 한다. 프론트가 받아온 페이지 안에서만 거르던 때는
    # 1,709건 중 음료가 3.9%라 첫 20건에 0~1건뿐이었고, 다음 페이지를 부르는 조건도
    # 안 맞아 "다음 레시피를 불러오고 있어요"에서 멈췄다(2026-08-16).
    if category and category.strip():
        stmt = stmt.where(Recipe.category == category.strip())
    if eligible:
        matched_product = (
            select(1)
            .select_from(RecipeIngredient)
            .join(
                RecipeIngredientProduct,
                RecipeIngredientProduct.recipe_ingredient_id == RecipeIngredient.id,
            )
            .where(RecipeIngredient.recipe_id == Recipe.id)
        )
        stmt = stmt.where(
            Recipe.comparison_status.in_(("ready", "completed")),
            Recipe.base_sugar_g.is_not(None),
            Recipe.total_sugar_g.is_not(None),
            Recipe.base_sugar_g > Recipe.total_sugar_g,
            exists(matched_product),
        )
    return stmt


async def list_recipes(
    db: AsyncSession,
    source: str | None = None,
    sort: str | None = None,
    page: int = 1,
    search: str | None = None,
) -> list[Recipe]:
    """PRODUCTION_HANDOFF.md P1-2 — source 필터(만개의레시피/유튜브 구분) + 페이지네이션.

    category 는 007_columns_recipes_products.sql 로 컬럼이 생겼고 2026-08-16 에
    1,677건 백필됐다(4개 체계: 한 끼/간식/음료/양념·소스, 미판정 32건은 NULL).
    아래 list_related_recipes 가 이 값으로 같은 카테고리를 고른다 — 전량 NULL 이던
    동안에는 그 분기가 한 번도 타지 않아 연관 레시피가 카테고리와 무관하게 나왔다.
    cook_time_min 은 컬럼만 있고 아직 전량 NULL 이라 응답에 못 채운다."""
    stmt = _apply_recipe_filters(select(Recipe), source, search)
    # sort=sugarReduction: 저당 비율 높은 순. 기본은 기존과 동일하게 id desc(최신 적재순).
    # nulls_last 가 필수다 — Postgres 는 DESC 에서 NULL 을 맨 앞에 놓는다. eligible 필터를
    # 걷어내 전체 레시피를 보여주면서(2026-08-16) 감소율이 없는 레시피가 목록 최상단을
    # 덮는 문제가 드러났다. eligible=true 일 때는 NULL 이 애초에 걸러져 티가 안 났다.
    stmt = stmt.order_by(nulls_last(Recipe.sugar_reduction_pct.desc())) if sort == "sugarReduction" else stmt.order_by(Recipe.id.desc())
    stmt = stmt.offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE)
    return list((await db.execute(stmt)).scalars().all())


async def list_recipes_with_total(
    db: AsyncSession,
    source: str | None = None,
    sort: str | None = None,
    page: int = 1,
    search: str | None = None,
    eligible: bool = False,
    category: str | None = None,
) -> tuple[list[Recipe], int]:
    """Return one recipe page and total count with one database round trip.

    The window count replaces the separate count query for non-empty pages.
    """
    stmt = _apply_recipe_filters(
        select(Recipe, func.count().over().label("total_count")),
        source,
        search,
        eligible,
        category,
    )
    # nulls_last 이유는 list_recipes 주석 참고.
    stmt = stmt.order_by(nulls_last(Recipe.sugar_reduction_pct.desc())) if sort == "sugarReduction" else stmt.order_by(Recipe.id.desc())
    stmt = stmt.offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE)

    rows = (await db.execute(stmt)).all()
    if rows:
        return [row[0] for row in rows], int(rows[0][1])
    if page > 1:
        return [], await count_recipes(db, source=source, search=search, eligible=eligible, category=category)
    return [], 0


async def count_recipes(
    db: AsyncSession,
    source: str | None = None,
    search: str | None = None,
    eligible: bool = False,
    category: str | None = None,
) -> int:
    stmt = _apply_recipe_filters(select(func.count()).select_from(Recipe), source, search, eligible, category)
    return (await db.execute(stmt)).scalar_one()


async def list_related_recipes(db: AsyncSession, recipe: Recipe, limit: int = 3) -> list[Recipe]:
    """Return useful alternatives from the same category, ranked by sugar reduction."""
    stmt = select(Recipe).where(Recipe.id != recipe.id)
    if recipe.category:
        stmt = stmt.where(Recipe.category == recipe.category)
    stmt = _apply_recipe_filters(stmt, source=None, eligible=True)
    stmt = stmt.order_by(Recipe.sugar_reduction_pct.desc().nullslast(), Recipe.id.desc()).limit(limit)
    return list((await db.execute(stmt)).scalars().all())


async def get_recipe(db: AsyncSession, recipe_id: int) -> Recipe:
    recipe = await db.get(Recipe, recipe_id)
    if recipe is None:
        raise RecipeNotFoundError("레시피를 찾을 수 없습니다.")
    return recipe


async def recipe_exists(db: AsyncSession, recipe_id: int) -> bool:
    return await db.get(Recipe, recipe_id) is not None


async def get_ingredients(db: AsyncSession, recipe_id: int) -> list[RecipeIngredient]:
    stmt = select(RecipeIngredient).where(RecipeIngredient.recipe_id == recipe_id).order_by(RecipeIngredient.id)
    return list((await db.execute(stmt)).scalars().all())


async def get_recipe_with_ingredients(
    db: AsyncSession,
    recipe_id: int,
) -> tuple[Recipe, list[RecipeIngredient]]:
    """Load a recipe and its ingredients in a single database round trip."""
    stmt = (
        select(Recipe, RecipeIngredient)
        .outerjoin(RecipeIngredient, RecipeIngredient.recipe_id == Recipe.id)
        .where(Recipe.id == recipe_id)
        .order_by(RecipeIngredient.id)
    )
    rows = (await db.execute(stmt)).all()
    if not rows:
        raise RecipeNotFoundError("레시피를 찾을 수 없습니다.")
    return rows[0][0], [ingredient for _, ingredient in rows if ingredient is not None]


async def toggle_favorite(db: AsyncSession, recipe_id: int, user_id: int) -> bool:
    """RC-0111: 찜 등록/해제 토글. 반환값은 토글 후 상태(True=찜됨)."""
    await get_recipe(db, recipe_id)  # 없는 레시피면 404

    existing = await db.get(RecipeFavorite, {"recipe_id": recipe_id, "user_id": user_id})
    if existing is not None:
        await db.delete(existing)
        await db.commit()
        return False

    db.add(RecipeFavorite(recipe_id=recipe_id, user_id=user_id))
    await db.commit()
    return True


async def list_favorites(db: AsyncSession, user_id: int) -> list[Recipe]:
    """RC-0112: 찜한 레시피 목록."""
    stmt = (
        select(Recipe)
        .join(RecipeFavorite, RecipeFavorite.recipe_id == Recipe.id)
        .where(RecipeFavorite.user_id == user_id)
        .order_by(RecipeFavorite.created_at.desc())
    )
    return list((await db.execute(stmt)).scalars().all())
