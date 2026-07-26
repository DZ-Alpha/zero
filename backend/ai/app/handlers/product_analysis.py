import base64
import binascii
import logging
import re

from app.handlers.base import FeatureHandler, HandlerInput, HandlerResult
from app.handlers.general_qa import render_user_context_block, strip_chat_markdown
from app.llm.bedrock_client import LLMClient
from app.services.chat_photo_storage import store_best_effort

logger = logging.getLogger("ai_service.product_analysis")

_DATA_URL_RE = re.compile(r"^data:(?P<media_type>image/[\w.+-]+);base64,(?P<data>.+)$", re.DOTALL)

# Bedrock converse가 실제로 받아주는 이미지 포맷만 화이트리스트. HEIC 등 나머지는
# 여기서 걸러 친절한 안내로 대체한다(모델 호출까지 갔다가 400을 받는 것보다 낫다).
_SUPPORTED_MEDIA_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}

_SYSTEM_PROMPT = (
    "너는 저당·건강 식품 서비스의 상담 챗봇 '당당봇'이다. 사용자가 보낸 사진(음식 또는 "
    "제품 포장지·원재료명)을 보고 짧게 설명한다.\n"
    "1. 사진과 함께 사용자 질문이 주어지면 그 질문에 맞춰 우선 답한다. 질문이 없으면 사진 속 "
    "음식이나 제품이 무엇인지부터 짧게 말한다.\n"
    "2. 당류·자당·시럽류가 원재료 앞쪽에 있거나 흔히 당류가 높은 음식이면 그 점을 짚어준다. "
    "정확한 수치가 사진만으로 확인되지 않으면 지어내지 말고 '정확한 수치는 포장지 표시를 확인해 주세요'라고 안내한다.\n"
    "3. [사용자 정보]가 주어지면(하루 목표·알레르기 등) 그 기준으로 설명하고, 없으면 일반 기준으로 "
    "안내하되 개인값을 지어내지 않는다.\n"
    "4. 의학적 효능이나 건강 개선 효과를 단정하지 않는다.\n"
    "5. 이건 참고용 설명일 뿐, 실제 식단 기록에는 반영되지 않는다는 점을 사용자가 오해하지 않도록 "
    "'기록'이라는 표현 대신 '확인'이라는 표현을 쓴다.\n"
    "답변은 3문장 이내로 짧게, 제목·볼드 없이 친근한 대화체로 답한다."
)

_DEFAULT_USER_PROMPT = "이 사진을 분석해서 설명해줘."

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


def _build_user_prompt(user_msg: str | None, context_block: str) -> str:
    # 사진만 왔을 때(질문 없이 첨부 버튼만 누른 경우)는 기본 설명 요청으로,
    # 텍스트가 같이 왔으면(예: "이거 당류 많아?") 그 질문을 우선으로 반영한다.
    parts = [f"[사용자 질문]\n{user_msg}" if user_msg else _DEFAULT_USER_PROMPT]
    if context_block:
        parts.append(f"[사용자 정보]\n{context_block}")
    return "\n\n".join(parts)


class ProductAnalysisHandler(FeatureHandler):
    """사진 첨부 챗봇 질의 - Vision 모델(Bedrock)로 사진 속 음식·제품을 짧게
    설명해준다. diet-service의 실제 식단 기록과는 별개의 참고용 답변이다
    (구조화된 영양 수치는 반환하지 않는다 - 자유형 설명만 채택, 2026-07-26 결정)."""

    def __init__(self, llm: LLMClient | None = None) -> None:
        self._llm = llm

    async def handle(self, data: HandlerInput) -> HandlerResult:
        if not data.img:
            return HandlerResult(msg="상품 영양성분 분석 기능은 준비 중이에요. 곧 제공할게요.")

        if self._llm is None:
            return HandlerResult(msg=_NOT_READY_MSG, is_img=True)

        parsed = _parse_data_url(data.img)
        if parsed is None or parsed[0] not in _SUPPORTED_MEDIA_TYPES:
            return HandlerResult(msg=_UNSUPPORTED_FORMAT_MSG, is_img=True)
        media_type, image_bytes = parsed
        await store_best_effort(data.context.user_id, media_type, image_bytes)
        user_prompt = _build_user_prompt(data.msg, render_user_context_block(data.context))

        try:
            answer = await self._llm.complete_vision(_SYSTEM_PROMPT, user_prompt, media_type, image_bytes)
        except Exception:
            logger.exception("vision analysis failed")
            return HandlerResult(msg=_ANALYSIS_FAILED_MSG, is_img=True)

        return HandlerResult(msg=strip_chat_markdown(answer), is_img=True)
