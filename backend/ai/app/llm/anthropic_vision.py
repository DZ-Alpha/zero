import base64
import logging

import anthropic

from app.core.config import settings

logger = logging.getLogger("ai_service.anthropic_vision")

_MODEL = "claude-opus-4-8"


async def analyze_photo(system: str, prompt: str, media_type: str, image_bytes: bytes) -> str | None:
    """챗봇 사진 첨부(product_analysis) 전용 - 비용 협의(2026-07-26)로 Bedrock이
    아니라 Anthropic API를 직접 호출한다. 일반 텍스트 질의(Bedrock)와는 완전히
    별개 경로다. 식사 사진(아침/점심/저녁/간식) 분석과도 별개다 - 그쪽은
    zero-db Vision worker(Kafka 파이프라인)만 쓴다(회의 결정 2026-07-27).

    키가 없거나 모델이 거부하면 None을 반환한다 - 호출 측이 "준비 중"/실패
    안내로 폴백한다(기존 무비용 폴백과 동일 패턴)."""
    if not settings.anthropic_api_key:
        return None

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    response = await client.messages.create(
        model=_MODEL,
        max_tokens=500,
        system=system,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": base64.b64encode(image_bytes).decode("ascii"),
                    },
                },
                {"type": "text", "text": prompt},
            ],
        }],
    )

    if response.stop_reason == "refusal":
        logger.warning("vision: chat photo analysis refused")
        return None

    return next((block.text for block in response.content if block.type == "text"), None)
