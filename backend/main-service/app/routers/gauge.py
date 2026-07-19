from fastapi import APIRouter, Depends, Header, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user_from_token, resolve_token
from app.services.gauge_store import get_today_totals
from app.services.health_profile_store import get_health_profile

router = APIRouter(prefix="/home")


@router.get("/user-sugar-calorie")
async def get_daily_gauge(
    response: Response,
    usr: str | None = None,
    authorization: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    user = get_current_user_from_token(resolve_token(usr, authorization), response)
    calories, sugars = await get_today_totals(db, user.user_id)
    profile = await get_health_profile(db, user.user_id)

    return {
        "cal": calories,
        "sugar": sugars,
        # Not in the MN-0106~0108 spec's output columns, but main-service.md's
        # own sample query pairs today's totals with the stored target — added
        # so the frontend doesn't need a second round trip to compute % filled.
        "calorieTarget": float(profile.daily_calorie_target)
        if profile and profile.daily_calorie_target is not None
        else None,
        "sugarTarget": float(profile.daily_sugar_target_g)
        if profile and profile.daily_sugar_target_g is not None
        else None,
    }
