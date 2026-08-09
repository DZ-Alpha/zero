import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException, Response
from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from app.models.product_display import ProductDisplay
from app.routers.product import _is_already_low_sugar_product
from app.routers.search import search
from app.services.alternative_store import get_product_alternatives
from app.services.product_store import _apply_search_order, _name_or_brand_matches


def _sql(statement) -> str:
    return str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )


def test_public_search_matches_curated_display_name() -> None:
    sql = _sql(select(ProductDisplay).where(_name_or_brand_matches("제로")))

    assert "v_product_display.display_name" in sql
    assert "v_product_display.brand_name" in sql


@pytest.mark.parametrize(
    ("sort", "expected"),
    [
        ("sugar_asc", "v_product_display.sugars ASC"),
        ("calorie_asc", "v_product_display.calories ASC"),
    ],
)
def test_public_search_uses_database_nutrition_sort(sort: str, expected: str) -> None:
    statement = _apply_search_order(select(ProductDisplay), None, sort)

    assert expected in _sql(statement)


@pytest.mark.asyncio
async def test_search_rejects_unknown_sort_before_querying_database() -> None:
    db = MagicMock()
    db.execute = AsyncMock()

    with pytest.raises(HTTPException) as exc_info:
        await search(
            response=Response(),
            query=None,
            category=None,
            warning=None,
            sort="popularity_guess",
            page=1,
            db=db,
        )

    assert exc_info.value.status_code == 400
    db.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_alternative_query_rechecks_food_type_serving_and_reduction() -> None:
    db = MagicMock()
    result = MagicMock()
    result.all.return_value = []
    db.execute = AsyncMock(return_value=result)

    await get_product_alternatives(db, uuid.UUID("00000000-0000-0000-0000-000000000001"), limit=3)

    sql = _sql(db.execute.await_args.args[0])
    assert "food_type" in sql
    assert "serving_value" in sql
    assert "serving_unit" in sql
    assert "similarity >= 0.70" in sql
    assert "sugar_delta_g <= -0.50" in sql


def test_low_sugar_or_zero_labeled_source_does_not_offer_swap() -> None:
    product = SimpleNamespace(product_name="일반 카라멜 팝콘", sugars=18.5)
    low_tag = SimpleNamespace(tag_type="HEALTH_LABEL", tag_code="LOW_SUGAR")

    assert _is_already_low_sugar_product(product, [low_tag])
    assert _is_already_low_sugar_product(
        SimpleNamespace(product_name="제로 팝콘", sugars=3.0),
        [],
    )
    assert not _is_already_low_sugar_product(product, [])
