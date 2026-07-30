import asyncio
import logging
import re

import httpx

from app.core.config import settings
from app.models.product import Product
from app.models.tag import Tag

logger = logging.getLogger("product_service.ai")

_CLAUDE_API_URL = "https://api.anthropic.com/v1/messages"
_MODEL = "claude-haiku-4-5-20251001"
_MAX_TOKENS = 300

# _call_claude*가 실패/미설정일 때 돌려주는 안내 문구 — 실제 AI 생성 결과가
# 아니므로 캐시(product_ai_summaries)에 저장하면 안 된다. is_summary_unavailable()
# 로 호출 측이 캐싱 여부를 판단한다.
_NO_API_KEY_MSG = "AI 요약 기능을 사용하려면 ANTHROPIC_API_KEY 설정이 필요합니다."
_BEDROCK_FAILURE_MSG = "AI 요약을 생성하지 못했습니다. 잠시 후 다시 시도해주세요."


def is_summary_unavailable(text: str) -> bool:
    return text in (_NO_API_KEY_MSG, _BEDROCK_FAILURE_MSG)


# 상품 상세 요약 서식 규칙(2026-07-30 요청): 제목/부제목/헤딩/목록/이모지 없이
# 순수 문장만. 강조는 **단어** 마커만 허용 - 프론트(ProductDetail.tsx)가
# <strong>으로 렌더한다. 프롬프트로 지시하지만 모델이 어길 수 있어(특히 감미료
# 설명처럼 성분별 나열이 자연스러운 경우 헤딩·이모지가 자주 섞임) 후처리로도
# 걷어낸다. 캐시(product_ai_summaries)에 이미 저장된 과거 응답에도 적용해야
# 하므로 라우터가 캐시 조회 결과에도 이 함수를 태운다.
_FORMAT_RULE = (
    "서식 규칙: 제목·부제목·헤딩(#)·목록·이모지를 절대 쓰지 말고, 이어지는 "
    "순수한 문장으로만 답하세요. 꼭 강조할 단어가 있으면 **단어** 형태만 쓸 수 있습니다."
)

_HEADING_LINE_RE = re.compile(r"^\s{0,3}#{1,6}\s.*$", re.MULTILINE)
_LIST_MARKER_RE = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+", re.MULTILINE)
# 이모지·기호 계열: 그림문자/딩뱃/화살표 장식/변형 선택자/ZWJ. 한글·라틴·일반
# 문장부호는 건드리지 않는다.
_EMOJI_RE = re.compile(
    "["
    "\U0001f000-\U0001faff"  # 그림문자 전반(이모티콘·음식·사물 등)
    "\u2600-\u27bf"          # 기타 기호·딩뱃(별·체크·손가락 등)
    "\U0001f1e6-\U0001f1ff"  # 국기(리전 인디케이터)
    "\u2b00-\u2bff"          # 화살표·별 장식
    "\ufe0f"                  # 이모지 변형 선택자
    "\u200d"                  # ZWJ(조합 이모지 연결자)
    "]"
)


def sanitize_summary(text: str) -> str:
    """헤딩 줄(제목/부제목)은 통째로 제거, 목록 마커·이모지는 걷어내고 한
    문단으로 정리한다. **강조** 마커는 프론트가 굵게 렌더하므로 남긴다."""
    text = _HEADING_LINE_RE.sub("", text)
    text = _LIST_MARKER_RE.sub("", text)
    text = _EMOJI_RE.sub("", text)
    text = re.sub(r"\s*\n+\s*", " ", text)
    return re.sub(r"[ \t]{2,}", " ", text).strip()


async def _call_claude_anthropic(prompt: str) -> str:
    if not settings.anthropic_api_key:
        return _NO_API_KEY_MSG
    headers = {
        "x-api-key": settings.anthropic_api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    body = {
        "model": _MODEL,
        "max_tokens": _MAX_TOKENS,
        "messages": [{"role": "user", "content": prompt}],
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(_CLAUDE_API_URL, headers=headers, json=body)
        resp.raise_for_status()
        data = resp.json()
    return data["content"][0]["text"].strip()


def _call_claude_bedrock_sync(prompt: str) -> str:
    import boto3

    client = boto3.client("bedrock-runtime", region_name=settings.bedrock_region)
    resp = client.converse(
        modelId=settings.bedrock_model_id,
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        inferenceConfig={"maxTokens": _MAX_TOKENS},
    )
    return resp["output"]["message"]["content"][0]["text"].strip()


async def _call_claude(prompt: str) -> str:
    # ai_provider="bedrock"이어도 이 함수만 영향받는다 - 챗봇(backend/ai)과
    # diet-service의 Vision 분석은 각자 자기 설정을 따로 쓰므로 이 스위치와
    # 무관하다. boto3는 동기 SDK라 스레드로 돌린다(tools/model-eval의
    # call_bedrock, backend/ai의 BedrockClient와 동일한 패턴).
    if settings.ai_provider == "bedrock":
        try:
            return await asyncio.to_thread(_call_claude_bedrock_sync, prompt)
        except Exception:
            logger.exception("Bedrock 호출 실패")
            return _BEDROCK_FAILURE_MSG
    return await _call_claude_anthropic(prompt)


async def generate_product_summary(product: Product, tags: list[Tag]) -> str:
    """PR-0301: 영양성분과 원재료 기반 AI 한줄 요약."""
    sweetener_names = [t.tag_name for t in tags if t.tag_type == "SWEETENER"]
    allergen_names = [t.tag_name for t in tags if t.tag_type == "ALLERGEN"]

    prompt = (
        f"다음 제품을 소비자가 이해하기 쉽게 한 문장으로 요약해주세요.\n"
        f"제품명: {product.product_name}\n"
        f"브랜드: {product.brand_name or '미상'}\n"
        f"칼로리: {product.calories or '정보 없음'}kcal, 당류: {product.sugars or '정보 없음'}g, "
        f"나트륨: {product.sodium or '정보 없음'}mg\n"
        f"대체 당: {', '.join(sweetener_names) if sweetener_names else '없음'}\n"
        f"알레르기 유발 성분: {', '.join(allergen_names) if allergen_names else '없음'}\n"
        f"원재료: {product.ingredient_text or '정보 없음'}\n"
        f"한 문장으로만 답하세요. {_FORMAT_RULE}"
    )
    return await _call_claude(prompt)


async def generate_sweetener_description(product: Product, sweetener_tags: list[Tag]) -> str:
    """PR-0302: 해당 제품의 대체 당에 대한 쉬운 설명."""
    if not sweetener_tags:
        return "이 제품에는 대체 당이 포함되어 있지 않습니다."

    descriptions = []
    for tag in sweetener_tags:
        desc = tag.description or tag.tag_name
        caution = f" 주의: {tag.caution_text}" if tag.caution_text else ""
        descriptions.append(f"{tag.tag_name}: {desc}{caution}")

    prompt = (
        f"다음은 '{product.product_name}'에 들어간 대체 당 성분들입니다.\n"
        + "\n".join(descriptions)
        + "\n소비자가 이해하기 쉽도록 각 성분을 2~3문장으로 설명해주세요. "
        + _FORMAT_RULE
    )
    return await _call_claude(prompt)
