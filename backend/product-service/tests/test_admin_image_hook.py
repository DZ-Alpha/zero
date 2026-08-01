import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.routers import admin


FAKE_CATEGORY_TAG_ID = "00000000-0000-0000-0000-000000000000"


def _base_body(image_url: str) -> dict:
    return {
        "name": "테스트 상품",
        "category_tag_id": FAKE_CATEGORY_TAG_ID,
        "image_url": image_url,
        "calories": Decimal("100"),
        "sugars": Decimal("5"),
        # 영양성분 선택 필드는 전부 None -> update_nutrition 트리거 안 되게
        "carbohydrate": None,
        "protein": None,
        "fat": None,
        "sodium": None,
    }


def _fake_product():
    product = MagicMock()
    product.product_id = uuid.uuid4()
    product.calories = Decimal("100")
    product.sugars = Decimal("5")
    return product


@pytest.mark.asyncio
async def test_handle_create_product_keeps_original_url_when_hosting_fails():
    """store_external_image가 None을 돌려주면(호스팅 실패) 원본 image_url로
    create_product가 호출돼야 한다 — 상품 등록 자체는 막히지 않는다."""
    original_url = "https://ext.example.com/x.jpg"
    body = _base_body(original_url)
    db = MagicMock()

    with patch.object(admin, "store_external_image", return_value=None) as mock_store, \
         patch.object(admin, "create_product", new=AsyncMock(return_value=_fake_product())) as mock_create, \
         patch.object(admin, "update_nutrition", new=AsyncMock()) as mock_update_nutrition:
        await admin._handle_create_product(body, db)

    mock_store.assert_called_once_with(original_url)
    mock_create.assert_called_once()
    assert mock_create.call_args.kwargs["image_url"] == original_url
    mock_update_nutrition.assert_not_called()


@pytest.mark.asyncio
async def test_handle_create_product_uses_rewritten_url_when_hosting_succeeds():
    """store_external_image가 self-hosted 경로를 돌려주면 그 값으로
    create_product가 호출돼야 한다."""
    original_url = "https://ext.example.com/x.jpg"
    rewritten_url = "/b/product-images/x.jpg"
    body = _base_body(original_url)
    db = MagicMock()

    with patch.object(admin, "store_external_image", return_value=rewritten_url) as mock_store, \
         patch.object(admin, "create_product", new=AsyncMock(return_value=_fake_product())) as mock_create, \
         patch.object(admin, "update_nutrition", new=AsyncMock()) as mock_update_nutrition:
        await admin._handle_create_product(body, db)

    mock_store.assert_called_once_with(original_url)
    mock_create.assert_called_once()
    assert mock_create.call_args.kwargs["image_url"] == rewritten_url
    mock_update_nutrition.assert_not_called()
