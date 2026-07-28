import asyncio
import logging

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
        f"한 문장으로만 답하세요."
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
        + "\n소비자가 이해하기 쉽도록 각 성분을 2~3문장으로 설명해주세요."
    )
    return await _call_claude(prompt)
