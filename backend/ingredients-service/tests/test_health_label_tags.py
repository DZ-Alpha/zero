import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.routers import tags as tags_router


@pytest.mark.asyncio
async def test_health_label_endpoint_returns_code_and_metadata(monkeypatch) -> None:
    tag = SimpleNamespace(
        tag_id=uuid.uuid4(),
        tag_name="저당",
        tag_code="LOW_SUGAR",
        description="저당 기준 설명",
        caution_text="표시 확인",
        source_url="https://example.test/source",
    )
    list_tags = AsyncMock(return_value=[tag])
    monkeypatch.setattr(tags_router, "list_tags_by_type", list_tags)

    payload = await tags_router.health_label_list(db=AsyncMock())

    list_tags.assert_awaited_once()
    assert payload["list"][0]["code"] == "LOW_SUGAR"
    assert payload["list"][0]["caution"] == "표시 확인"

