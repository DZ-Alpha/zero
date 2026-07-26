from __future__ import annotations

import hashlib
import json
import logging
import signal
import time
import uuid
from typing import Any

from confluent_kafka import Consumer, KafkaException
from minio import Minio

from app.config import load_settings
from app.contracts import completed_event, failed_event, validate_requested_event
from app.db import close_pool, connect, initialize, json_value
from app.vision import (
    VisionProviderError,
    create_provider,
    is_retryable,
    needs_confirmation,
    read_minio_object,
)


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)
settings = load_settings()
running = True


def stop(*_: Any) -> None:
    global running
    running = False


def insert_outbox(conn, event: dict[str, Any], topic: str, event_key: str) -> None:
    conn.execute(
        """
        INSERT INTO outbox_events
            (event_id, causation_event_id, topic, event_key, payload)
        VALUES (%s, %s, %s, %s, %s::jsonb)
        ON CONFLICT DO NOTHING
        """,
        (event["event_id"], event.get("causation_event_id"), topic, event_key, json_value(event)),
    )


def claim_completion(conn, request: dict[str, Any], outcome: str) -> bool:
    row = conn.execute(
        """
        INSERT INTO processed_events (event_id, job_id, status)
        VALUES (%s, %s, %s)
        ON CONFLICT (event_id) DO NOTHING
        RETURNING event_id
        """,
        (request["event_id"], request["analysis_id"], outcome),
    ).fetchone()
    return row is not None


def finish_failed(request: dict[str, Any], error_code: str, attempts: int) -> None:
    failure = failed_event(request, error_code, attempts, is_retryable(error_code))
    with connect(settings) as conn:
        if not claim_completion(conn, request, "FAILED"):
            return
        conn.execute(
            """
            UPDATE diet_analysis_jobs
            SET status='FAILED', failure_code=%s, updated_at=now()
            WHERE analysis_id=%s
            """,
            (error_code, request["analysis_id"]),
        )
        insert_outbox(conn, failure, settings.failed_topic, request["user_id"])


def finish_completed(request: dict[str, Any], result: dict[str, Any]) -> None:
    completed = completed_event(request, result, settings.processor_version)
    with connect(settings) as conn:
        if not claim_completion(conn, request, "DONE"):
            return
        conn.execute(
            """
            UPDATE diet_analysis_jobs
            SET status='DONE', result=%s::jsonb, updated_at=now()
            WHERE analysis_id=%s
            """,
            (json_value(result), request["analysis_id"]),
        )
        insert_outbox(conn, completed, settings.completed_topic, request["user_id"])


def process(request: dict[str, Any], minio_client: Minio, vision_provider: Any) -> None:
    request = validate_requested_event(request)
    with connect(settings) as conn:
        if conn.execute("SELECT 1 FROM processed_events WHERE event_id=%s", (request["event_id"],)).fetchone():
            return
        conn.execute(
            """
            UPDATE diet_analysis_jobs
            SET status='PROCESSING', attempt_count=attempt_count+1, updated_at=now()
            WHERE analysis_id=%s AND status IN ('PENDING','PROCESSING')
            """,
            (request["analysis_id"],),
        )

    object_stat = None
    for attempt in range(1, 4):
        try:
            object_stat = minio_client.stat_object(settings.minio_bucket, request["image_key"])
            break
        except Exception:
            logger.warning(
                "claim-check read failed event_id=%s analysis_id=%s attempt=%s",
                request["event_id"], request["analysis_id"], attempt,
            )
            if attempt < 3:
                time.sleep(2 ** (attempt - 1))

    if object_stat is None:
        finish_failed(request, "OBJECT_NOT_READABLE", 3)
        return

    try:
        image, content_type = read_minio_object(
            minio_client, settings.minio_bucket, request["image_key"], settings.vision_max_image_bytes,
        )
    except VisionProviderError as exc:
        logger.warning("claim-check payload rejected event_id=%s code=%s", request["event_id"], exc)
        finish_failed(request, str(exc), 1)
        return

    for attempt in range(1, settings.vision_max_attempts + 1):
        try:
            result = vision_provider.analyze(image=image, content_type=content_type, image_key=request["image_key"])
            break
        except VisionProviderError as exc:
            code = str(exc)
            if attempt < settings.vision_max_attempts and is_retryable(code):
                delay = settings.vision_retry_backoff_seconds * (2 ** (attempt - 1))
                logger.warning(
                    "vision provider retrying event_id=%s code=%s attempt=%s delay=%s",
                    request["event_id"], code, attempt, delay,
                )
                time.sleep(delay)
                continue
            logger.warning(
                "vision provider failed event_id=%s code=%s attempts=%s",
                request["event_id"], code, attempt,
            )
            finish_failed(request, code, attempt)
            return

    result["object_size"] = object_stat.size
    result["needs_user_confirmation"] = needs_confirmation(result, settings.vision_confidence_threshold)
    finish_completed(request, result)


def emit_invalid(raw: bytes, reason: str) -> None:
    digest = hashlib.sha256(raw).hexdigest()
    event_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"dangdang-invalid:{digest}"))
    event = {
        "event_id": event_id,
        "causation_event_id": None,
        "analysis_id": None,
        "upload_id": None,
        "user_id": None,
        "error_code": "INVALID_EVENT",
        "attempt_count": 1,
        "retryable": False,
        "raw_sha256": digest,
        "reason": reason[:200],
        "schema_version": 1,
    }
    with connect(settings) as conn:
        insert_outbox(conn, event, settings.failed_topic, "invalid-event")


def main() -> None:
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    initialize(settings)
    minio_client = Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )
    vision_provider = create_provider(settings)
    consumer = Consumer(
        {
            "bootstrap.servers": settings.kafka_bootstrap_servers,
            "group.id": settings.kafka_consumer_group,
            "client.id": "dangdang-vision-worker",
            "enable.auto.commit": False,
            "auto.offset.reset": "earliest",
            "max.poll.interval.ms": 300000,
        }
    )
    consumer.subscribe([settings.request_topic])
    try:
        while running:
            message = consumer.poll(1.0)
            if message is None:
                continue
            if message.error():
                raise KafkaException(message.error())
            raw = message.value() or b""
            try:
                process(json.loads(raw), minio_client, vision_provider)
            except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
                logger.warning(
                    "invalid event topic=%s partition=%s offset=%s",
                    message.topic(), message.partition(), message.offset(),
                )
                emit_invalid(raw, str(exc))
            except Exception:
                logger.exception(
                    "message processing failed; offset remains uncommitted topic=%s partition=%s offset=%s",
                    message.topic(), message.partition(), message.offset(),
                )
                time.sleep(1)
                continue
            consumer.commit(message=message, asynchronous=False)
    finally:
        consumer.close()
        close_pool()


if __name__ == "__main__":
    main()
