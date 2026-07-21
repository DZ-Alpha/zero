import asyncio
import json
import logging
import uuid
from decimal import Decimal

from aiokafka import AIOKafkaConsumer

from app.core.config import settings
from app.core.database import async_session_factory
from app.services.diet_store import (
    apply_vision_result,
    get_meal_log_by_request_event_id,
    make_meal_item_from_analysis,
)

logger = logging.getLogger("diet_service.vision_consumer")

_TOPIC_COMPLETED = "diet.photo.completed"
_TOPIC_FAILED = "diet.photo.failed"

_consumer: AIOKafkaConsumer | None = None
_task: asyncio.Task | None = None


def _parse_causation_event_id(payload: dict) -> uuid.UUID | None:
    raw = payload.get("causation_event_id")
    if not raw:
        logger.warning("vision consumer: message missing causation_event_id event_id=%s", payload.get("event_id"))
        return None
    try:
        return uuid.UUID(raw)
    except ValueError:
        logger.warning("vision consumer: invalid causation_event_id=%s", raw)
        return None


async def _handle_completed(payload: dict) -> None:
    request_event_id = _parse_causation_event_id(payload)
    if request_event_id is None:
        return

    result = payload.get("result") or {}
    confidence_raw = result.get("confidence")
    confidence = Decimal(str(confidence_raw)) if confidence_raw is not None else None
    status = "AWAITING_CONFIRMATION" if result.get("needs_user_confirmation") else "COMPLETED"

    async with async_session_factory() as db:
        log = await get_meal_log_by_request_event_id(db, request_event_id)
        if log is None:
            logger.warning("vision consumer: no meal_log for causation_event_id=%s", request_event_id)
            return

        items = [
            make_meal_item_from_analysis(
                log.meal_log_id,
                item_name=entry.get("name", ""),
                serving_value=Decimal("0"),
                serving_unit="인분",
                calories=Decimal(str(entry.get("calo", 0))),
                sugars=Decimal(str(entry.get("dang", 0))),
                carbohydrate=Decimal("0"),
            )
            for entry in result.get("list-diet", [])
        ]
        await apply_vision_result(
            db,
            log.meal_log_id,
            status=status,
            confidence=confidence,
            provider=payload.get("processor_version"),
            items=items,
        )
        logger.info(
            "vision consumer: completed meal_log_id=%s status=%s causation_event_id=%s",
            log.meal_log_id, status, request_event_id,
        )


async def _handle_failed(payload: dict) -> None:
    request_event_id = _parse_causation_event_id(payload)
    if request_event_id is None:
        return

    async with async_session_factory() as db:
        log = await get_meal_log_by_request_event_id(db, request_event_id)
        if log is None:
            logger.warning("vision consumer: no meal_log for causation_event_id=%s", request_event_id)
            return

        await apply_vision_result(
            db,
            log.meal_log_id,
            status="FAILED",
            confidence=None,
            provider=None,
            items=[],
            retryable=bool(payload.get("retryable")),
        )
        logger.info(
            "vision consumer: failed meal_log_id=%s error_code=%s retryable=%s causation_event_id=%s",
            log.meal_log_id, payload.get("error_code"), payload.get("retryable"), request_event_id,
        )


async def _consume_once(consumer: AIOKafkaConsumer) -> None:
    async for msg in consumer:
        try:
            payload = json.loads(msg.value)
            if msg.topic == _TOPIC_COMPLETED:
                await _handle_completed(payload)
            else:
                await _handle_failed(payload)
        except Exception:
            # commit하지 않고 다음 메시지로 넘어간다 — 재기동하면 이 오프셋부터
            # 다시 전달된다 (at-least-once). apply_vision_result가 이미 종결
            # 상태(COMPLETED/FAILED)는 재적용하지 않으므로 재전달은 안전하다.
            logger.exception(
                "vision consumer: failed to process message topic=%s offset=%s", msg.topic, msg.offset
            )
            continue
        await consumer.commit()


async def _consume_loop(consumer: AIOKafkaConsumer) -> None:
    # `async for msg in consumer` 바깥에서 터지는 예외(브로커 연결 끊김, 리밸런스
    # 오류, 역직렬화 실패 등)는 이 태스크를 조용히 죽여서 이후 아무도 메시지를
    # 소비하지 않게 만든다 — 인프라팀 경고(2026-07-21, snappy 미지원으로 컨슈머가
    # 소리 없이 죽은 사고와 같은 계열). 최상위 try/except로 감싸 지수 백오프로
    # 재시작한다. 종료(stop_consumer)는 CancelledError로 오므로 그대로 전파한다.
    backoff = 1
    while True:
        try:
            await _consume_once(consumer)
            return  # consumer가 정상 종료되면 루프도 끝낸다
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("vision consumer: consume loop crashed, restarting in %ss", backoff)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30)


async def start_consumer() -> None:
    """diet.photo.completed/diet.photo.failed 전용 consumer 시작.

    개발팀 요청서 정정 1(2026-07-20) — worker는 HTTP callback을 호출하지
    않는다. 결과는 이 Kafka topic 두 개로만 온다. KAFKA_BROKERS가 비어있으면
    (로컬 개발 등) consumer를 아예 시작하지 않는다.
    """
    global _consumer, _task
    if not settings.kafka_brokers:
        logger.info("vision consumer: KAFKA_BROKERS not set, consumer disabled")
        return

    _consumer = AIOKafkaConsumer(
        _TOPIC_COMPLETED,
        _TOPIC_FAILED,
        bootstrap_servers=settings.kafka_brokers,
        group_id=settings.kafka_consumer_group,
        enable_auto_commit=False,
        auto_offset_reset="earliest",
    )
    await _consumer.start()
    _task = asyncio.create_task(_consume_loop(_consumer))
    logger.info(
        "vision consumer started group=%s topics=%s,%s",
        settings.kafka_consumer_group, _TOPIC_COMPLETED, _TOPIC_FAILED,
    )


async def stop_consumer() -> None:
    global _consumer, _task
    if _task is not None:
        _task.cancel()
        try:
            await _task
        except asyncio.CancelledError:
            pass
        _task = None
    if _consumer is not None:
        await _consumer.stop()
        _consumer = None
