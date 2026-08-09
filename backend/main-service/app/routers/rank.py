from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.recipe_swap_ranking import RecipeSwapRanking

router = APIRouter(prefix="/home")


@router.get("/rank/item")
async def get_recipe_swap_ranking(
    response: Response,
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    """Expose the DB-ranked recipes that already have sugar comparisons."""
    stmt = (
        select(RecipeSwapRanking)
        .order_by(RecipeSwapRanking.rnk, RecipeSwapRanking.id)
        .limit(limit)
    )
    recipes = list((await db.execute(stmt)).scalars().all())
    response.headers["Cache-Control"] = "public, max-age=300, stale-while-revalidate=900"
    return {
        "status": "SUCCESS",
        "listRecipes": [
            {
                "id": recipe.id,
                "rank": recipe.rnk,
                "name": recipe.name,
                "image": recipe.thumbnail_url,
                "source": recipe.source,
                "baseSugarG": (
                    float(recipe.base_sugar_g) if recipe.base_sugar_g is not None else None
                ),
                "totalSugarG": (
                    float(recipe.total_sugar_g) if recipe.total_sugar_g is not None else None
                ),
                "sugarSavedG": (
                    float(recipe.sugar_saved_g) if recipe.sugar_saved_g is not None else None
                ),
                "sugarReductionPct": float(recipe.sugar_reduction_pct),
                "totalKcal": (
                    float(recipe.total_kcal) if recipe.total_kcal is not None else None
                ),
                "baseKcal": (
                    float(recipe.base_kcal) if recipe.base_kcal is not None else None
                ),
                "kcalReductionPct": (
                    float(recipe.kcal_reduction_pct)
                    if recipe.kcal_reduction_pct is not None
                    else None
                ),
            }
            for recipe in recipes
        ],
        # 기존 클라이언트가 필드를 읽어도 깨지지 않게 빈 배열을 유지한다.
        "listProducts": [],
    }
