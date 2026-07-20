from app.handlers.base import FeatureHandler, HandlerInput, HandlerResult


class AdminAnalyticsHandler(FeatureHandler):
    async def handle(self, data: HandlerInput) -> HandlerResult:
        return HandlerResult(msg="사용자 데이터 분석 기능은 준비 중이에요. 곧 제공할게요.")
