from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import Response

from app.routers.rank import get_recipe_swap_ranking


@pytest.mark.asyncio
async def test_recipe_swap_ranking_returns_db_values() -> None:
    recipe = MagicMock()
    recipe.id = 17
    recipe.rnk = 1
    recipe.name = "설탕 없이 만든 카스테라"
    recipe.thumbnail_url = "/images/recipe.jpg"
    recipe.source = "youtube"
    recipe.base_sugar_g = Decimal("76.30")
    recipe.total_sugar_g = Decimal("0.50")
    recipe.sugar_saved_g = Decimal("75.80")
    recipe.sugar_reduction_pct = Decimal("99.30")
    recipe.total_kcal = Decimal("200.00")
    recipe.base_kcal = Decimal("240.00")
    recipe.kcal_reduction_pct = Decimal("16.67")

    result = MagicMock()
    result.scalars.return_value.all.return_value = [recipe]
    db = MagicMock()
    db.execute = AsyncMock(return_value=result)
    response = Response()

    payload = await get_recipe_swap_ranking(response=response, limit=10, db=db)

    assert payload["status"] == "SUCCESS"
    assert payload["listProducts"] == []
    assert payload["listRecipes"][0]["id"] == 17
    assert payload["listRecipes"][0]["sugarReductionPct"] == 99.3
    assert response.headers["Cache-Control"].startswith("public")
