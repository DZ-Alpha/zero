from datetime import date

import httpx

from app.core.config import settings


class DietServiceError(Exception):
    pass


async def get_meal_records(user_ids: list[int], record_date: date) -> list[dict[str, object]]:
    """Diet Service의 GET /diet/internal/meal-records를 서버간 호출한다.
    사용자 자신의 JWT가 아니라 공유 시크릿으로 인증한다 — diet-service
    app/routers/diet.py의 internal_meal_records/_verify_internal_secret 참고.
    실패하면 빈 목록으로 접어서(방 화면 자체가 죽지 않게) 조용히 넘긴다 —
    "식단 정보를 못 불러왔어요" 정도는 얌로그 화면에서 빈 슬롯으로 보여도
    충분하고, 다른 회원의 모임 진입 자체를 막을 정도는 아니다."""
    if not user_ids:
        return []
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.get(
                f"{settings.diet_service_url}/diet/internal/meal-records",
                params={"userIds": ",".join(str(uid) for uid in user_ids), "date": record_date.isoformat()},
                headers={"X-Internal-Service-Secret": settings.internal_service_secret},
            )
            response.raise_for_status()
            data = response.json()
        return list(data.get("records", []))
    except (httpx.HTTPError, ValueError):
        return []
