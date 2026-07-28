import asyncio
import base64
import binascii
import logging
import re

from app.handlers.base import FeatureHandler, HandlerInput, HandlerResult
from app.handlers.food_render import render_food_analysis
from app.handlers.general_qa import strip_chat_markdown
from app.services.chat_photo_storage import store_best_effort
from app.services.vision_analyzer import VisionProviderError, is_retryable

logger = logging.getLogger("ai_service.product_analysis")

_DATA_URL_RE = re.compile(r"^data:(?P<media_type>image/[\w.+-]+);base64,(?P<data>.+)$", re.DOTALL)
_SUPPORTED_MEDIA_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}

_UNSUPPORTED_FORMAT_MSG = "죄송해요, 이 사진 형식은 아직 확인하지 못해요. JPG, PNG, WEBP 사진으로 다시 시도해 주세요."
_ANALYSIS_FAILED_MSG = "사진을 확인하지 못했어요. 잠시 후 다른 사진으로 다시 시도해 주세요."
_NOT_READY_MSG = "사진 잘 받았어요! 사진으로 성분을 분석하는 기능은 아직 준비 중이에요. 조금만 기다려주세요."


def _parse_data_url(data_url: str) -> tuple[str, bytes] | None:
    match = _DATA_URL_RE.match(data_url.strip())
    if not match:
        return None
    try:
        return match.group("media_type").lower(), base64.b64decode(match.group("data"), validate=True)
    except (binascii.Error, ValueError):
        return None


class ProductAnalysisHandler(FeatureHandler):
    """사진 첨부 챗봇 질의 - Gemini 비전으로 음식을 분석해 짧게 확인해준다.
    diet-service의 실제 식단 기록과는 별개의 참고용 답변이다."""

    def __init__(self, analyzer=None, *, confidence_threshold: float = 0.75, max_attempts: int = 3) -> None:
        self._analyzer = analyzer
        self._threshold = confidence_threshold
        self._max_attempts = max(1, max_attempts)

    async def handle(self, data: HandlerInput) -> HandlerResult:
        if not data.img:
            return HandlerResult(msg="상품 영양성분 분석 기능은 준비 중이에요. 곧 제공할게요.")
        if self._analyzer is None:
            return HandlerResult(msg=_NOT_READY_MSG, is_img=True)

        parsed = _parse_data_url(data.img)
        if parsed is None or parsed[0] not in _SUPPORTED_MEDIA_TYPES:
            return HandlerResult(msg=_UNSUPPORTED_FORMAT_MSG, is_img=True)
        media_type, image_bytes = parsed
        image_key = await store_best_effort(data.context.user_id, media_type, image_bytes)

        result = None
        for attempt in range(1, self._max_attempts + 1):
            try:
                result = await asyncio.to_thread(self._analyzer.analyze, image_bytes, media_type)
                break
            except VisionProviderError as exc:
                code = str(exc)
                if attempt < self._max_attempts and is_retryable(code):
                    logger.warning("vision retry attempt=%s code=%s", attempt, code)
                    continue
                logger.warning("vision analysis failed code=%s attempts=%s", code, attempt)
                return HandlerResult(msg=_ANALYSIS_FAILED_MSG, is_img=True)
            except Exception:
                logger.exception("vision analysis unexpected error")
                return HandlerResult(msg=_ANALYSIS_FAILED_MSG, is_img=True)

        answer = render_food_analysis(result, data.context)
        return HandlerResult(msg=strip_chat_markdown(answer), is_img=True, image_key=image_key)
