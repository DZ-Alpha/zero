from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.recipe_store import RecipeNotFoundError, get_recipe
from app.services.substitute_store import get_substitutes_for_recipe

router = APIRouter(prefix="/recipes")


@router.get("/{recipe_id}/substitutes")
async def get_recipe_substitutes(recipe_id: int, db: AsyncSession = Depends(get_db)) -> dict[str, object]:
    try:
        await get_recipe(db, recipe_id)
    except RecipeNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    substitutes = await get_substitutes_for_recipe(db, recipe_id)

    return {
        "substitutes": [
            {
                "ingredientId": ingredient.id,
                "ingredientName": ingredient.name,
                "products": [
                    {
                        "productId": str(match.product_id),
                        "name": product.product_name,
                        "brand": product.brand_name,
                        "image": product.image_url,
                        "url": product.purchase_url,
                        "sugar": float(product.sugars),
                        "calories": float(product.calories),
                        "matchScore": float(match.match_score) if match.match_score is not None else None,
                        "isPrimary": match.is_primary,
                    }
                    for match, product in products
                ],
            }
            for ingredient, products in substitutes
        ]
    }
