import asyncio
import logging
from datetime import datetime, timezone

import httpx

from app.context.provider import UserContextProvider
from app.schemas import UserContext

logger = logging.getLogger("ai_context")


def _age_from_birth_year(birth_year: int | None) -> int | None:
    if not birth_year:
        return None
    return datetime.now(timezone.utc).year - int(birth_year)

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
            # 목표 계산용 신체정보는 전부 health-profile에서 읽어 출처를 통일한다.
            # (mypage.healthStat에도 키·몸무게가 있으나 갱신 시점이 달라 값이
            #  어긋날 수 있어, 성별·활동량과 같은 출처인 health-profile로 맞춘다.)
            gender=profile.get("gender"),
            age=_age_from_birth_year(profile.get("birthYear")),
            height_cm=profile.get("heightCm"),
            weight_kg=profile.get("weightKg"),
            activity_level=profile.get("activityLevel"),
        )
