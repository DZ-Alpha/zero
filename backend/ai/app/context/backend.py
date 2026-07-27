import asyncio
import logging
from datetime import datetime, timezone

import httpx

from app.context.provider import UserContextProvider
from app.schemas import UserContext

logger = logging.getLogger("ai_context")

# diet 지연이 챗봇 응답을 늘어뜨리지 않도록 짧은 타임아웃(Redis P0-1 교훈).
_TIMEOUT = httpx.Timeout(3.0)


def _age_from_birth_year(birth_year: int | None) -> int | None:
    if not birth_year:
        return None
    return datetime.now(timezone.utc).year - int(birth_year)


_ANONYMOUS = UserContext(user_id=0, logged_in=False, interests=[], has_allergy=False,
                         consent=False, daily_sugar_target_g=None, daily_calorie_target=None)


class BackendUserContextProvider(UserContextProvider):
    def __init__(self, login_url: str, main_url: str, diet_url: str,
                 http_client: httpx.AsyncClient | None = None) -> None:
        self._login_url = login_url.rstrip("/")
        self._main_url = main_url.rstrip("/")
        self._diet_url = diet_url.rstrip("/")
        self._client = http_client or httpx.AsyncClient(timeout=_TIMEOUT)

    async def load(self, token: str) -> UserContext:
        try:
            mypage_resp, profile_resp, diet_resp = await asyncio.gather(
                self._client.get(f"{self._login_url}/user/mypage", params={"usr": token}),
                self._client.get(f"{self._main_url}/home/health-profile", params={"usr": token}),
                self._client.get(f"{self._diet_url}/home/user-sugar-calorie", params={"usr": token}),
                return_exceptions=True,
            )
        except httpx.HTTPError:
            logger.warning("context load failed: reason=http_error")
            return _ANONYMOUS

        # mypage는 필수 — 실패(예외 또는 non-200)면 익명 폴백.
        if isinstance(mypage_resp, Exception) or mypage_resp.status_code != 200:
            return _ANONYMOUS

        mypage = mypage_resp.json()
        health = mypage.get("healthStat", {}) or {}

        # profile/diet는 부가 — 실패해도 해당 부분만 비운다(격리).
        profile = {}
        if not isinstance(profile_resp, Exception) and profile_resp.status_code == 200:
            profile = profile_resp.json()

        today_sugar = today_cal = None
        if not isinstance(diet_resp, Exception) and diet_resp.status_code == 200:
            diet = diet_resp.json()
            today_sugar = diet.get("sugar")
            today_cal = diet.get("cal")

        return UserContext(
            user_id=0,
            logged_in=True,
            interests=list(mypage.get("favorite") or []),
            has_allergy=bool(health.get("allergic")),
            consent=bool(profile.get("consent")),
            daily_sugar_target_g=profile.get("dailySugarTargetG"),
            daily_calorie_target=profile.get("dailyCalorieTarget"),
            gender=profile.get("gender"),
            age=_age_from_birth_year(profile.get("birthYear")),
            height_cm=profile.get("heightCm"),
            weight_kg=profile.get("weightKg"),
            activity_level=profile.get("activityLevel"),
            today_sugar=today_sugar,
            today_cal=today_cal,
        )
