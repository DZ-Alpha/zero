import json
import logging

import anthropic

from app.core.config import settings

logger = logging.getLogger("diet_service.vision")

_MODEL = "claude-opus-4-8"

_ITEMS_SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "servingValue": {"type": "number"},
                    "servingUnit": {"type": "string"},
                    "calories": {"type": "number"},
                    "sugars": {"type": "number"},
                    "carbohydrate": {"type": "number"},
                },
                "required": ["name", "servingValue", "servingUnit", "calories", "sugars", "carbohydrate"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["items"],
    "additionalProperties": False,
}

_PROMPT = (
    "이 사진 속 음식을 분석해주세요. 각 항목마다 이름, 1회 제공량(숫자)과 단위(예: g, ml, 인분), "
    "칼로리(kcal), 당류(g), 탄수화물(g)을 추정해서 알려주세요. 사진에서 명확히 구분되는 음식마다 "
    "하나의 항목으로 나눠주세요."
)


async def analyze_meal_photo(image_url: str) -> list[dict]:
    """RC-0103: 식단 사진을 Claude Vision으로 분석해 항목 목록을 반환한다.

    ANTHROPIC_API_KEY가 없으면 빈 목록을 반환 — 호출 측(app/routers/diet.py)이
    기존과 동일하게 PREPARING으로 처리한다. 즉 키를 안 넣으면 이전 동작 그대로다.
    """
    if not settings.anthropic_api_key:
        return []

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    response = await client.messages.create(
        model=_MODEL,
        max_tokens=2048,
        output_config={"format": {"type": "json_schema", "schema": _ITEMS_SCHEMA}},
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "url", "url": image_url}},
                    {"type": "text", "text": _PROMPT},
                ],
            }
        ],
    )

    if response.stop_reason == "refusal":
        logger.warning("vision: analysis refused meal_log image")
        return []

    text = next((block.text for block in response.content if block.type == "text"), None)
    if text is None:
        return []

    return json.loads(text)["items"]
