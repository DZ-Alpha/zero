from app.models.content import ContentArticle, ContentCollection, ContentCollectionProduct
from app.models.meal_log import MealLog
from app.models.meal_total import MealTotal
from app.models.product import Product
from app.models.product_display import ProductDisplay, ProductSwapPick
from app.models.product_tag import ProductTag
from app.models.recipe_swap_ranking import RecipeSwapRanking
from app.models.tag import Tag
from app.models.user_health_profile import UserHealthProfile
from app.models.user_preference import UserPreference

__all__ = [
    "ContentArticle",
    "ContentCollection",
    "ContentCollectionProduct",
    "MealLog",
    "MealTotal",
    "Product",
    "ProductDisplay",
    "ProductSwapPick",
    "ProductTag",
    "RecipeSwapRanking",
    "Tag",
    "UserHealthProfile",
    "UserPreference",
]

# 이 서비스가 소유하고 self-migrate하는 테이블만. MealLog/MealTotal/Product/
# ProductTag/Tag는 각각 Diet/Product/Ingredients 소유 읽기전용 모델이라
# create_all() 대상에서 반드시 제외한다.
OWNED_TABLES = [UserHealthProfile.__table__, UserPreference.__table__]
