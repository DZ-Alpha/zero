from app.handlers.base import FeatureHandler, HandlerInput, HandlerResult


class RecipeSubstituteHandler(FeatureHandler):
    async def handle(self, data: HandlerInput) -> HandlerResult:
        return HandlerResult(msg="레시피 대체 상품 추천 기능은 준비 중이에요. 곧 제공할게요.")
