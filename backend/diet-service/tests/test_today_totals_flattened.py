"""오늘 합계 집계가 v_meal_totals 뷰로 되돌아가지 않게 잡아두는 회귀 테스트.

main-service/tests/test_gauge_store_flattened.py와 같은 이유다 — 같은 뷰를
같은 방식으로 읽는 곳이 두 군데였고(감사 A-1), 한쪽만 고치면 절반만 해결된다.
main-service는 3레플리카라 호출량은 그쪽이 더 많을 수 있다.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services import diet_store


async def _captured_sql() -> str:
    captured: dict[str, object] = {}

    async def capture(stmt, params=None):
        captured["sql"] = str(stmt)
        row = MagicMock()
        row.calories = 0
        row.sugars = 0
        result = MagicMock()
        result.one.return_value = row
        return result

    db = MagicMock()
    db.execute = AsyncMock(side_effect=capture)
    await diet_store.get_today_totals(db, user_id=7)
    return str(captured["sql"]).lower()


@pytest.mark.asyncio
async def test_today_totals_aggregates_meal_items_not_the_view() -> None:
    sql = await _captured_sql()
    assert "service.meal_items" in sql
    assert "v_meal_totals" not in sql, (
        "오늘 합계가 다시 v_meal_totals를 읽고 있다 — 감사 A-1에서 187ms가 나온 경로다"
    )


@pytest.mark.asyncio
async def test_today_totals_keeps_logs_without_items() -> None:
    """분석 대기 중(meal_items 없음)인 meal_log가 결과에서 사라지면 안 된다."""
    sql = await _captured_sql()
    assert "left join" in sql


@pytest.mark.asyncio
async def test_today_totals_uses_kst_day_boundary() -> None:
    """KST 자정 기준은 이 쿼리의 원래 버그픽스다 — 평탄화하면서 잃지 않았는지 본다.

    프론트가 날짜를 KST로 매기고 그 날짜의 00:00Z로 eaten_at을 저장하기 때문에,
    UTC로 자르면 KST 자정~오전 9시 사이 기록이 어제로 밀려 홈 게이지에 안 잡혔다.
    """
    sql = await _captured_sql()
    assert "asia/seoul" in sql


@pytest.mark.asyncio
async def test_today_totals_returns_floats() -> None:
    row = MagicMock()
    row.calories = 1020
    row.sugars = 6
    result = MagicMock()
    result.one.return_value = row
    db = MagicMock()
    db.execute = AsyncMock(return_value=result)

    totals = await diet_store.get_today_totals(db, user_id=7)

    assert totals == {"cal": 1020.0, "sugar": 6.0}
