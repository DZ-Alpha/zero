from fastapi import APIRouter, Depends, Header, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user_from_token, resolve_token
from app.services.recommend_store import get_recommended_products

router = APIRouter(prefix="/home")


@router.get("/user-recommend")
async def get_user_recommendations(
    response: Response,
    authorization: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    user = get_current_user_from_token(resolve_token(None, authorization), response)
    recommendation = await get_recommended_products(db, user.user_id)

    return {
        "personalized": recommendation.personalized,
        "matchedPreferenceIds": [
            str(preference_id) for preference_id in recommendation.matched_preference_ids
        ],
        "reason": recommendation.reason,
        "listProducts": [
            {
                # 프론트가 상세 페이지로 바로 링크하려면 상품 ID가 필요한데 빠져
                # 있어서, 이름으로 로컬 카탈로그를 매칭 못 하면 검색 페이지로만
                # 보내고 있었다(2026-07-31 리포트 - 상세로 가야 함).
                "id": str(product.product_id),
                "name": product.display_name,
                "brand": product.brand_name,
                "image": product.image_url,
                "url": None,
            }
            for product in recommendation.products
        ]
    }
