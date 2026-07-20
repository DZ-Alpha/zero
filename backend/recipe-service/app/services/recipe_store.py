from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.recipe import Recipe
from app.models.recipe_favorite import RecipeFavorite
from app.models.recipe_ingredient import RecipeIngredient

PAGE_SIZE = 20


class RecipeNotFoundError(Exception):
    pass


def _apply_recipe_filters(stmt, source: str | None):
    if source:
        stmt = stmt.where(Recipe.source == source)
    return stmt


async def list_recipes(
    db: AsyncSession,
    source: str | None = None,
    sort: str | None = None,
    page: int = 1,
) -> list[Recipe]:
    """PRODUCTION_HANDOFF.md P1-2 — source 필터(만개의레시피/유튜브 구분) + 페이지네이션.
    category/time(조리시간)은 명세엔 있지만 실제 service.recipes 테이블에 해당 컬럼이
    없어서 필터/응답 필드 모두 아직 못 채운다 — 데이터팀 스키마 추가 필요."""
    stmt = _apply_recipe_filters(select(Recipe), source)
    # sort=sugarReduction: 저당 비율 높은 순. 기본은 기존과 동일하게 id desc(최신 적재순).
    stmt = stmt.order_by(Recipe.sugar_reduction_pct.desc()) if sort == "sugarReduction" else stmt.order_by(Recipe.id.desc())
    stmt = stmt.offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE)
    return list((await db.execute(stmt)).scalars().all())


async def count_recipes(db: AsyncSession, source: str | None = None) -> int:
    stmt = _apply_recipe_filters(select(func.count()).select_from(Recipe), source)
    return (await db.execute(stmt)).scalar_one()


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
