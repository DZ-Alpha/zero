import asyncio
import logging

import httpx

from app.context.provider import UserContextProvider
from app.schemas import UserContext

logger = logging.getLogger("ai_context")

_ANONYMOUS = UserContext(user_id=0, logged_in=False, interests=[], has_allergy=False,
                         consent=False, daily_sugar_target_g=None, daily_calorie_target=None)


class BackendUserContextProvider(UserContextProvider):
    def __init__(self, login_url: str, main_url: str, http_client: httpx.AsyncClient | None = None) -> None:
        self._login_url = login_url.rstrip("/")
        self._main_url = main_url.rstrip("/")
        self._client = http_client or httpx.AsyncClient()

    async def load(self, token: str) -> UserContext:
        try:
            mypage_resp, profile_resp = await asyncio.gather(
                self._client.get(f"{self._login_url}/user/mypage", params={"usr": token}),
                self._client.get(f"{self._main_url}/home/health-profile", params={"usr": token}),
            )
        except httpx.HTTPError:
            logger.warning("context load failed: reason=http_error")
            return _ANONYMOUS

        if mypage_resp.status_code != 200:
            return _ANONYMOUS

        mypage = mypage_resp.json()
        health = mypage.get("healthStat", {}) or {}
        profile = profile_resp.json() if profile_resp.status_code == 200 else {}

        return UserContext(
            user_id=0,  # mypage에 user_id 미포함 — 필요 시 토큰 sub로 확장.
            logged_in=True,
            interests=list(mypage.get("favorite") or []),
            has_allergy=bool(health.get("allergic")),
            consent=bool(profile.get("consent")),
            daily_sugar_target_g=profile.get("dailySugarTargetG"),
            daily_calorie_target=profile.get("dailyCalorieTarget"),
            # 키·몸무게·나이는 동의 무관하게 mypage.healthStat에 있고,
            # 성별·활동량은 health-profile에 있다(동의 시에만 채워질 수 있음).
            gender=profile.get("gender"),
            age=health.get("age"),
            height_cm=health.get("tall"),
            weight_kg=health.get("weight"),
            activity_level=profile.get("activityLevel"),
        )
