from app.handlers.base import HandlerInput, HandlerResult
from app.handlers.product_analysis import ProductAnalysisHandler
from app.handlers.recommend import RecommendHandler
from app.schemas import UserContext


def _input():
    ctx = UserContext(user_id=1, logged_in=True, interests=[], has_allergy=False,
                      consent=False, daily_sugar_target_g=None, daily_calorie_target=None)
    return HandlerInput(msg="이 제품 분석해줘", img=None, template=None, context=ctx)


async def test_product_stub_returns_preparing():
    result = await ProductAnalysisHandler().handle(_input())
    assert isinstance(result, HandlerResult)
    assert result.is_img is False
    assert "준비" in result.msg


async def test_recommend_stub_returns_preparing():
    result = await RecommendHandler().handle(_input())
    assert "준비" in result.msg
