from app.handlers.base import FeatureHandler, HandlerInput, HandlerResult


class ProductAnalysisHandler(FeatureHandler):
    """실제 사진 분석(Vision 모델 호출)은 아직 미구현 - data.img가 프론트에서
    챗봇 사진 첨부 UI를 통해 여기까지 도달하는 것만 이번에 연결했다. 실제
    분석 로직을 붙일 때는 data.img(data URL 문자열)를 디코드해서 Vision
    호출부에 넘기면 된다."""

    async def handle(self, data: HandlerInput) -> HandlerResult:
        if data.img:
            return HandlerResult(
                msg="사진 잘 받았어요! 사진으로 성분을 분석하는 기능은 아직 준비 중이에요. 조금만 기다려주세요.",
                is_img=True,
            )
        return HandlerResult(msg="상품 영양성분 분석 기능은 준비 중이에요. 곧 제공할게요.")
