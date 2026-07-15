import logging
from datetime import date

import httpx

from app.core.config import settings
from app.models.product import Product
from app.models.tag import Tag

logger = logging.getLogger("product_service.ai")

_CLAUDE_API_URL = "https://api.anthropic.com/v1/messages"
_MODEL = "claude-haiku-4-5-20251001"
_MAX_TOKENS = 300


async def _call_claude(prompt: str) -> str:
    if not settings.anthropic_api_key:
        return "AI 요약 기능을 사용하려면 ANTHROPIC_API_KEY 설정이 필요합니다."
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


async def generate_user_feature_info(
    product: Product,
    tags: list[Tag],
    birth_year: int | None,
    gender: str | None,
    daily_calorie_target: float | None,
    daily_sugar_target_g: float | None,
) -> str:
    """PR-0303: 사용자 맞춤형 영양 설명 (일일 권장량 대비 %)."""
    current_year = date.today().year
    age = (current_year - birth_year) if birth_year else None
    age_str = f"{age}세" if age else "나이 정보 없음"
    gender_str = gender or "성별 정보 없음"

    allergen_names = [t.tag_name for t in tags if t.tag_type == "ALLERGEN"]
    calorie_pct = (
        f"{float(product.calories) / daily_calorie_target * 100:.1f}%"
        if product.calories and daily_calorie_target
        else "정보 없음"
    )
    sugar_pct = (
        f"{float(product.sugars) / daily_sugar_target_g * 100:.1f}%"
        if product.sugars and daily_sugar_target_g
        else "정보 없음"
    )

    prompt = (
        f"사용자 정보: {age_str}, {gender_str}\n"
        f"제품명: {product.product_name}\n"
        f"이 제품 1회 섭취 시 일일 권장 칼로리의 {calorie_pct}, 당류의 {sugar_pct}를 섭취하게 됩니다.\n"
        f"주의 알레르기 성분: {', '.join(allergen_names) if allergen_names else '없음'}\n"
        f"사용자 눈높이에 맞춰 2~3문장으로 쉽게 설명해주세요."
    )
    return await _call_claude(prompt)
