import logging
from datetime import date

import httpx

from app.core.config import settings

logger = logging.getLogger("diet_service.room_notify")


async def notify_meal_recorded(user_id: int, record_date: date, meal_type: str) -> None:
    """community-service의 POST /rooms/internal/meal-recorded를 서버간 호출한다.
    사용자 자신의 JWT가 아니라 공유 시크릿으로 인증한다 — community-service
    app/routers/rooms.py의 notify_meal_recorded/_verify_internal_secret 참고.

    room_meal_thread는 원래 누군가 방 화면을 열어봐야만 생겼다(build_meal_slots
    lazy 생성) - 그래서 실제로 식단을 기록해도 아무도 방을 안 열어보면 얌로그
    활동 피드/알림에 전혀 안 잡히는 문제가 있었다. 여기서 실패해도 절대
    식단 기록 자체를 막으면 안 되므로(사용자의 진짜 데이터가 이미 커밋된
    뒤에 호출되는 부가 알림일 뿐이다), 조용히 로그만 남기고 넘어간다."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                f"{settings.community_service_url}/rooms/internal/meal-recorded",
                json={"userId": user_id, "recordDate": record_date.isoformat(), "mealType": meal_type},
                headers={"X-Internal-Service-Secret": settings.internal_service_secret},
            )
            response.raise_for_status()
    except httpx.HTTPError:
        logger.warning(
            "room notify failed: user_id=%s record_date=%s meal_type=%s",
            user_id, record_date, meal_type, exc_info=True,
        )
