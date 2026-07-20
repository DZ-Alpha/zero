from app.models.product import Product
from app.models.raw_ingredient_nutrient import RawIngredientNutrient
from app.models.recipe import Recipe
from app.models.recipe_favorite import RecipeFavorite
from app.models.recipe_ingredient import RecipeIngredient
from app.models.recipe_ingredient_product import RecipeIngredientProduct
from app.models.user_ref import UserRef

__all__ = [
    "Product",
    "RawIngredientNutrient",
    "Recipe",
    "RecipeFavorite",
    "RecipeIngredient",
    "RecipeIngredientProduct",
    "UserRef",
]

# Everything above except RecipeFavorite is read-only data from the data
# team's recipe pipeline (or, for Product, the Product Service) — no DDL.
# RecipeFavorite (RC-0111/0112) is this service's own table in its own
# `recipe` schema; OWNED_TABLES scopes create_all() to just that one table.
OWNED_TABLES = [RecipeFavorite.__table__]
