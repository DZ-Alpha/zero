from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.meal_item import MealItem
from app.models.meal_log import MealLog

# "오늘"은 서버가 도는 지역과 무관하게 한국 사용자 기준 하루 — UTC 자정이 아니라
# KST 자정을 하루 경계로 쓴다.
_KST = ZoneInfo("Asia/Seoul")


async def get_today_totals(db: AsyncSession, user_id: int) -> tuple[float, float]:
    """(total_calories, total_sugars) consumed today (KST calendar day).

    Aggregates service.meal_items directly instead of reading the
    service.v_meal_totals view. The view groups by meal_log_id, so the outer
    `WHERE meal_logs.user_id` cannot be pushed into it: PostgreSQL aggregates
    every meal_log × meal_item row (19,867 × 19,497 in production, spilling
    HashAggregate to disk) to return two rows — 187ms per call, measured with
    EXPLAIN ANALYZE on 2026-08-13. Flattened, the same result takes 0.162ms and
    actually uses idx_meal_items_meal_log.

    main-service runs 3 replicas, so this path can issue more of those calls
    than diet-service's equivalent (diet-service/app/services/diet_store.py
    get_today_totals) — both were flattened together; fixing one alone only
    solves half the load.

    LEFT JOIN, not JOIN: a meal_log whose items haven't landed yet (photo still
    PENDING) contributed 0 through the view and must keep contributing 0 rather
    than dropping the log. COALESCE covers the all-NULL case."""
    now_kst = datetime.now(_KST)
    day_start = now_kst.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = now_kst.replace(hour=23, minute=59, second=59, microsecond=999999)

    stmt = (
        select(
            func.coalesce(func.sum(MealItem.calories), 0),
            func.coalesce(func.sum(MealItem.sugars), 0),
        )
        .select_from(MealLog)
        .outerjoin(MealItem, MealItem.meal_log_id == MealLog.meal_log_id)
        .where(MealLog.user_id == user_id, MealLog.eaten_at >= day_start, MealLog.eaten_at <= day_end)
    )
    calories, sugars = (await db.execute(stmt)).one()
    return float(calories), float(sugars)
