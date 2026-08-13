"""홈 게이지 집계가 v_meal_totals 뷰로 되돌아가지 않게 잡아두는 회귀 테스트.

2026-08-13 감사 A-1: 뷰 정의가 `GROUP BY ml.meal_log_id`라 바깥
`WHERE meal_logs.user_id`가 뷰 안으로 안 내려가고, 2행을 얻으려고 meal_logs ×
meal_items 전체를 집계했다(운영 EXPLAIN ANALYZE 187.409ms → 평탄화 0.162ms).
쿼리를 되돌리면 인덱스가 있어도 다시 Seq Scan이 되므로, "느려졌다"가 아니라
여기서 먼저 걸리게 한다.

DB 없이 statement를 컴파일해서 모양만 본다 — 실제 값 검증은 운영에서
1020.00 / 6.00 동일 확인 완료(감사 문서 A-1).
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.dialects import postgresql

from app.services import gauge_store


def _compiled_sql() -> str:
    """get_today_totals가 실제로 실행하는 SELECT를 문자열로 뽑는다."""
    captured: dict[str, object] = {}

    async def capture(stmt):
        captured["stmt"] = stmt
        result = MagicMock()
        result.one.return_value = (0, 0)
        return result

    db = MagicMock()
    db.execute = AsyncMock(side_effect=capture)

    import asyncio

    asyncio.run(gauge_store.get_today_totals(db, user_id=7))
    stmt = captured["stmt"]
    return str(stmt.compile(dialect=postgresql.dialect())).lower()


def test_gauge_aggregates_meal_items_not_the_view() -> None:
    sql = _compiled_sql()
    assert "meal_items" in sql
    assert "v_meal_totals" not in sql, (
        "홈 게이지가 다시 v_meal_totals를 읽고 있다 — 감사 A-1에서 187ms가 나온 경로다"
    )


def test_gauge_keeps_logs_without_items() -> None:
    """LEFT JOIN이어야 한다.

    사진 분석이 아직 안 끝난 meal_log는 meal_items가 비어 있다. 뷰를 쓰던
    시절에도 그런 로그는 0을 보탰으므로, INNER JOIN으로 바꾸면 "기록은 했는데
    게이지에 안 잡히는" 차이가 생긴다(값이 아니라 행이 사라진다).
    """
    sql = _compiled_sql()
    assert "left outer join" in sql


@pytest.mark.asyncio
async def test_gauge_returns_floats() -> None:
    result = MagicMock()
    result.one.return_value = (1020, 6)
    db = MagicMock()
    db.execute = AsyncMock(return_value=result)

    calories, sugars = await gauge_store.get_today_totals(db, user_id=7)

    assert (calories, sugars) == (1020.0, 6.0)
    assert isinstance(calories, float) and isinstance(sugars, float)
