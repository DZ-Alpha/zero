from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from app.models.recipe import Recipe
from app.services.recipe_store import _apply_recipe_filters


def _sql(statement) -> str:
    return str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )


def test_recipe_search_filters_by_partial_recipe_name() -> None:
    statement = _apply_recipe_filters(select(Recipe), source=None, search="샐러드")

    sql = _sql(statement)
    assert "service.recipes.name ILIKE" in sql
    assert "%%샐러드%%" in sql


def test_recipe_search_combines_source_and_name_filters() -> None:
    statement = _apply_recipe_filters(
        select(Recipe),
        source="10000recipe",
        search="저당밥",
    )

    sql = _sql(statement)
    assert "service.recipes.source = '10000recipe'" in sql
    assert "service.recipes.name ILIKE" in sql
