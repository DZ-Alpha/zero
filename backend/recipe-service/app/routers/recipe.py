from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user_bearer
from app.core.database import get_db
from app.models.recipe import Recipe
from app.models.recipe_ingredient import RecipeIngredient
from app.services.recipe_store import (
    PAGE_SIZE,
    RecipeNotFoundError,
    count_recipes,
    get_ingredients,
    get_recipe,
    list_favorites,
    list_recipes,
    recipe_exists,
    toggle_favorite,
)

router = APIRouter(prefix="/recipes")


def _thumbnail_url(recipe: Recipe) -> str | None:
    # 2026-07-20 실측 — source="유튜브" 레시피는 thumbnail_url이
    # "/data/thumbnails/{id}.jpg" 같은 상대경로인데, 이 경로를 서빙하는 곳이
    # 어디에도 없어(gateway/frontend 다 확인함) 항상 404가 난다. source="만개의레시피"는
    # 절대 URL(recipe1.ezmember.co.kr)이라 정상 로드됨. YouTube는 video_id로
    # 썸네일을 공개 제공하므로(API 키 불필요) 상대경로일 땐 그쪽을 대신 쓴다.
    if recipe.thumbnail_url and not recipe.thumbnail_url.startswith("/"):
        return recipe.thumbnail_url
    if recipe.video_id:
        return f"https://img.youtube.com/vi/{recipe.video_id}/hqdefault.jpg"
    return recipe.thumbnail_url


def _list_item(recipe: Recipe) -> dict[str, object]:
    return {
        "id": recipe.id,
        "name": recipe.name,
        "thumbnailUrl": _thumbnail_url(recipe),
        "sugarReductionPct": float(recipe.sugar_reduction_pct) if recipe.sugar_reduction_pct is not None else None,
        "comparisonStatus": recipe.comparison_status,
        # PRODUCTION_HANDOFF.md P1-2 — 카드 필드. category/time(조리시간)은 명세엔
        # 있지만 service.recipes에 해당 컬럼이 없어서 아직 못 채운다.
        "sugar": float(recipe.total_sugar_g) if recipe.total_sugar_g is not None else None,
        "calories": float(recipe.total_kcal) if recipe.total_kcal is not None else None,
        "source": recipe.source,
    }


def _ingredient_item(ingredient: RecipeIngredient) -> dict[str, object]:
    return {
        "id": ingredient.id,
        "name": ingredient.name,
        "amount": ingredient.amount,
        "type": ingredient.ingredient_type,
        "sugarG": float(ingredient.sugar_g) if ingredient.sugar_g is not None else None,
        "kcal": float(ingredient.kcal) if ingredient.kcal is not None else None,
        # substituted 재료가 원래 재료였다면의 당/칼로리. common은 sugarG/kcal과 동일값.
        "baseSugarG": float(ingredient.base_sugar_g) if ingredient.base_sugar_g is not None else None,
        "baseKcal": float(ingredient.base_kcal) if ingredient.base_kcal is not None else None,
    }


@router.get("")
async def get_recipe_list(
    source: str | None = Query(None, description="출처 필터: 10000recipe | youtube (PRODUCTION_HANDOFF.md P1-2)"),
    sort: str | None = Query(None, description="정렬: sugarReduction(저당 비율순) | 기본(최신 적재순)"),
    page: int = Query(1, ge=1),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    recipes = await list_recipes(db, source=source, sort=sort, page=page)
    total = await count_recipes(db, source=source)
    return {
        "recipes": [_list_item(recipe) for recipe in recipes],
        "page": page,
        "pageSize": PAGE_SIZE,
        "total": total,
        "hasNext": page * PAGE_SIZE < total,
    }


class FavoriteToggleBody(BaseModel):
    id: int


# /favorite* 라우트는 반드시 /{recipe_id}보다 먼저 등록해야 한다 — 안 그러면
# "/recipes/favorite"가 recipe_id="favorite"로 매칭 시도돼 422가 난다.
@router.post("/favorite")
async def toggle_recipe_favorite(
    body: FavoriteToggleBody,
    db: AsyncSession = Depends(get_db),
    payload: dict = Depends(get_current_user_bearer),
) -> dict[str, object]:
    """RC-0111: 레시피 찜 등록/해제 토글."""
    user_id: int = payload["user_id"]
    try:
        liked = await toggle_favorite(db, body.id, user_id)
    except RecipeNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    return {"status": "SUCCESS", "liked": liked}


@router.get("/favorite/list")
async def get_recipe_favorite_list(
    db: AsyncSession = Depends(get_db),
    payload: dict = Depends(get_current_user_bearer),
) -> dict[str, object]:
    """RC-0112: 찜한 레시피 목록."""
    user_id: int = payload["user_id"]
    recipes = await list_favorites(db, user_id)
    return {"list-receipe": [{"id": r.id, "name": r.name, "image": _thumbnail_url(r)} for r in recipes]}


@router.get("/{recipe_id}")
async def get_recipe_detail(recipe_id: int, db: AsyncSession = Depends(get_db)) -> dict[str, object]:
    try:
        recipe = await get_recipe(db, recipe_id)
    except RecipeNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    ingredients = await get_ingredients(db, recipe_id)

    return {
        "id": recipe.id,
        "name": recipe.name,
        # 유튜브 수집 레시피만 값이 있고 만개의레시피는 None — 프론트가 이 값으로
        # 상세 페이지 썸네일에 인라인 재생 버튼을 조건부 노출한다(video_id는 이미
        # 모델에 매핑돼 있고 _thumbnail_url에서도 쓰던 값).
        "videoId": recipe.video_id,
        "thumbnailUrl": _thumbnail_url(recipe),
        "steps": recipe.steps,
        "source": recipe.source,
        "publishedAt": recipe.published_at.isoformat() if recipe.published_at else None,
        "nutrition": {
            "totalSugarG": float(recipe.total_sugar_g) if recipe.total_sugar_g is not None else None,
            "totalKcal": float(recipe.total_kcal) if recipe.total_kcal is not None else None,
            "baseSugarG": float(recipe.base_sugar_g) if recipe.base_sugar_g is not None else None,
            "baseKcal": float(recipe.base_kcal) if recipe.base_kcal is not None else None,
            "sugarReductionPct": float(recipe.sugar_reduction_pct) if recipe.sugar_reduction_pct is not None else None,
            "comparisonStatus": recipe.comparison_status,
        },
        "ingredients": [_ingredient_item(ingredient) for ingredient in ingredients],
    }


@router.get("/{recipe_id}/exists")
async def check_recipe_exists(recipe_id: int, db: AsyncSession = Depends(get_db)) -> dict[str, bool]:
    # Diet/Main이 external_recipe_id(느슨한 참조)의 유효성을 확인할 때 쓰는
    # 용도 — recipe-service.md 설계 메모 참고.
    return {"exists": await recipe_exists(db, recipe_id)}
