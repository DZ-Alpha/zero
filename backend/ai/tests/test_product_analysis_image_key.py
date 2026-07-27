import base64

from app.handlers.base import HandlerInput
from app.handlers.product_analysis import ProductAnalysisHandler
from app.schemas import UserContext
import app.handlers.product_analysis as pa


def _png():
    return "data:image/png;base64," + base64.b64encode(b"fakepng").decode()


def _ctx():
    return UserContext(user_id=7, logged_in=True, interests=[], has_allergy=False,
                       consent=False, daily_sugar_target_g=None, daily_calorie_target=None)


def _data(img):
    return HandlerInput(msg=None, img=img, template=None, context=_ctx())


class _Ok:
    def analyze(self, image_bytes, media_type):
        return {"list-diet": [{"name": "케이크", "dang": 40, "calo": 300}],
                "confidence": 0.9, "needs_user_confirmation": False}


async def test_image_key_passed_to_result(monkeypatch):
    async def fake_store(user_id, media_type, image_bytes):
        return "7/abc.png"
    monkeypatch.setattr(pa, "store_best_effort", fake_store)
    out = await ProductAnalysisHandler(analyzer=_Ok()).handle(_data(_png()))
    assert out.image_key == "7/abc.png"
    assert out.is_img is True


async def test_image_key_none_when_store_fails(monkeypatch):
    async def fake_store(user_id, media_type, image_bytes):
        return None
    monkeypatch.setattr(pa, "store_best_effort", fake_store)
    out = await ProductAnalysisHandler(analyzer=_Ok()).handle(_data(_png()))
    assert out.image_key is None
    assert "케이크" in out.msg  # 저장 실패해도 분석·답변은 정상
