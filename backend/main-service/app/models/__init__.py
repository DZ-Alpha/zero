from app.models.content import ContentArticle, ContentCollection, ContentCollectionProduct
from app.models.meal_item import MealItem
from app.models.meal_log import MealLog
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
    "MealItem",
    "MealLog",
    "Product",
    "ProductDisplay",
    "ProductSwapPick",
    "ProductTag",
    "RecipeSwapRanking",
    "Tag",
    "UserHealthProfile",
    "UserPreference",
]

# 이 서비스가 소유하고 self-migrate하는 테이블만. MealItem/MealLog/Product/
# ProductTag/Tag는 각각 Diet/Product/Ingredients 소유 읽기전용 모델이라
# create_all() 대상에서 반드시 제외한다.
#
# v_meal_totals 뷰 모델(MealTotal)은 2026-08-13에 삭제했다 — gauge_store가
# meal_items 직접 집계로 바뀌면서 아무 데서도 안 쓰는데, 남겨두면 187ms짜리
# 느린 경로를 다시 집어드는 입구가 된다. 뷰 자체는 DB에 그대로 있다.
OWNED_TABLES = [UserHealthProfile.__table__, UserPreference.__table__]
