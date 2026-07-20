from app.handlers.base import FeatureHandler, HandlerInput, HandlerResult


class ProductAnalysisHandler(FeatureHandler):
    async def handle(self, data: HandlerInput) -> HandlerResult:
        return HandlerResult(msg="상품 영양성분 분석 기능은 준비 중이에요. 곧 제공할게요.")
