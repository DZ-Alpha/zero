import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.preference_store import (
    InvalidPreferenceError,
    _normalize_custom_values,
    _validate_tag_type,
)
from app.services.recommend_store import get_recommended_products


def test_preference_tag_types_are_restricted() -> None:
    _validate_tag_type("INTEREST_CATEGORY", SimpleNamespace(tag_type="HEALTH_LABEL"))
    _validate_tag_type("ALLERGEN", SimpleNamespace(tag_type="ALLERGEN"))

    with pytest.raises(InvalidPreferenceError):
        _validate_tag_type("ALLERGEN", SimpleNamespace(tag_type="HEALTH_LABEL"))


def test_caution_ingredients_are_trimmed_and_deduplicated() -> None:
    assert _normalize_custom_values(["  말티톨 ", "말티톨", "복숭아  농축액"]) == [
        "말티톨",
        "복숭아 농축액",
    ]


@pytest.mark.asyncio
async def test_recommendation_marks_plain_fallback_as_not_personalized() -> None:
    preference_result = MagicMock()
    preference_result.all.return_value = []
    product = SimpleNamespace(product_id=uuid.uuid4(), display_name="기본 상품")
    product_result = MagicMock()
    product_result.scalars.return_value.all.return_value = [product]
    db = MagicMock()
    db.execute = AsyncMock(side_effect=[preference_result, product_result])

    recommendation = await get_recommended_products(db, user_id=1)

    assert recommendation.personalized is False
    assert recommendation.reason == "NO_PREFERENCES"
    assert recommendation.matched_preference_ids == []
    assert recommendation.products == [product]


@pytest.mark.asyncio
async def test_recommendation_reports_preferences_used_for_personalization() -> None:
    preference_id = uuid.uuid4()
    tag_id = uuid.uuid4()
    preference_result = MagicMock()
    preference_result.all.return_value = [
        SimpleNamespace(
            preference_id=preference_id,
            preference_type="INTEREST_CATEGORY",
            tag_id=tag_id,
        )
    ]
    product = SimpleNamespace(product_id=uuid.uuid4(), display_name="맞춤 상품")
    product_result = MagicMock()
    product_result.scalars.return_value.all.return_value = [product]
    matched_tag_result = MagicMock()
    matched_tag_result.scalars.return_value.all.return_value = [tag_id]
    db = MagicMock()
    db.execute = AsyncMock(side_effect=[preference_result, product_result, matched_tag_result])

    recommendation = await get_recommended_products(db, user_id=1)

    assert recommendation.personalized is True
    assert recommendation.reason is None
    assert recommendation.matched_preference_ids == [preference_id]
