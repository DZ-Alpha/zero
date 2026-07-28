from fastapi import APIRouter, Response

from app.services.vision_consumer import consumer_state

router = APIRouter()


@router.get("/health")
async def health(response: Response) -> dict:
    """웹서버 + Kafka vision consumer 생존을 함께 보고한다.

    2026-07-21: 컨슈머 fetch 태스크가 죽어도 /health가 200이라 40분간
    아무도 모른 사고가 있었다. 컨슈머가 켜져 있어야 하는데(KAFKA_BROKERS
    설정됨) 태스크가 죽어 있으면 503 — docker healthcheck와 모니터링이
    바로 잡아낸다. 컨슈머 비활성(로컬 개발)일 땐 200 유지.
    """
    consumer = consumer_state()
    body = {"status": "ok", "service": "diet-service", "vision_consumer": consumer}
    if consumer["enabled"] and not consumer["alive"]:
        response.status_code = 503
        body["status"] = "degraded"
    return body
