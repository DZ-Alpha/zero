import base64

from app.handlers.base import HandlerInput
from app.handlers.product_analysis import ProductAnalysisHandler
from app.schemas import UserContext
from app.services.vision_analyzer import VisionProviderError


def _png():
    return "data:image/png;base64," + base64.b64encode(b"fakepng").decode()


def _ctx():
    return UserContext(user_id=0, logged_in=False, interests=[], has_allergy=False,
                       consent=False, daily_sugar_target_g=None, daily_calorie_target=None)


def _data(img):
    return HandlerInput(msg=None, img=img, template=None, context=_ctx())


class _Ok:
    def analyze(self, image_bytes, media_type):
        return {"list-diet": [{"name": "초코케이크", "dang": 45, "calo": 380}],
                "confidence": 0.9, "needs_user_confirmation": False}


class _Boom:
    def __init__(self):
        self.calls = 0
    def analyze(self, image_bytes, media_type):
        self.calls += 1
        raise VisionProviderError("GEMINI_UNAVAILABLE")


async def test_no_image_placeholder():
    out = await ProductAnalysisHandler(analyzer=_Ok()).handle(_data(None))
    assert "준비" in out.msg or "분석" in out.msg


async def test_no_analyzer_not_ready():
    out = await ProductAnalysisHandler(analyzer=None).handle(_data(_png()))
    assert "준비" in out.msg


async def test_unsupported_format():
    out = await ProductAnalysisHandler(analyzer=_Ok()).handle(_data("data:image/heic;base64,AAAA"))
    assert "JPG" in out.msg or "다시" in out.msg


async def test_success_renders_sentence():
    out = await ProductAnalysisHandler(analyzer=_Ok()).handle(_data(_png()))
    assert "초코케이크" in out.msg
    assert out.is_img is True


async def test_retryable_then_graceful_fail():
    boom = _Boom()
    out = await ProductAnalysisHandler(analyzer=boom, max_attempts=3).handle(_data(_png()))
    assert boom.calls == 3
    assert "확인하지 못" in out.msg or "다시" in out.msg
