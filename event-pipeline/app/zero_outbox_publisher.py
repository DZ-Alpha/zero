"""Publish zero DB's service.event_outbox rows to Kafka.

Backend services (diet-service, login-service, ...) INSERT into
service.event_outbox inside their own business transactions and never touch
Kafka directly; this process is the single component that turns those rows
into Kafka messages. It is deliberately NOT part of any backend service:
the table is shared by every service, so embedding the publisher in one of
them would make that service a single point of failure for everyone else's
events.

Delivery is at-least-once. Both downstream consumers deduplicate by
event_id (vision worker via processed_events, Mongo activity consumer via
_id), so a crash between Kafka ACK and the published_at UPDATE only causes
a harmless duplicate.

Rows whose publish_attempts reach the configured cap are left alone with
their last_error — that is how poison rows (e.g. legacy payload formats)
are parked without blocking the rest of the queue.
"""
from __future__ import annotations

import json
import logging
import signal
import time
from typing import Any

import psycopg
from confluent_kafka import Producer
from psycopg.rows import dict_row

from app.config import Settings, load_settings


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)
settings = load_settings()
running = True


def stop(*_: Any) -> None:
    global running
    running = False


def topic_for(event_type: str, settings: Settings) -> str | None:
    """Map an outbox event_type to its Kafka topic; None means unroutable."""
    if event_type == settings.request_topic:
        return settings.request_topic
    if event_type.startswith("user."):
        return settings.activity_topic
    return None


def message_key(row: dict[str, Any]) -> str:
    """Partition key: user_id keeps one user's events ordered; fall back so the
    key is never empty."""
    if row.get("user_id") is not None:
        return str(row["user_id"])
    return str(row.get("aggregate_id") or row["event_id"])


def publish_batch(conn: psycopg.Connection, producer: Producer) -> int:
    published = 0
    with conn.transaction():
        rows = conn.execute(
            """
            SELECT id, event_id, event_type, user_id, aggregate_id, payload
            FROM service.event_outbox
            WHERE published_at IS NULL AND publish_attempts < %s
            ORDER BY id
            LIMIT 20
            FOR UPDATE SKIP LOCKED
            """,
            (settings.zero_outbox_max_publish_attempts,),
        ).fetchall()
        for row in rows:
            topic = topic_for(row["event_type"], settings)
            if topic is None:
                conn.execute(
                    """
                    UPDATE service.event_outbox
                    SET publish_attempts=%s, last_error=%s
                    WHERE id=%s
                    """,
                    (settings.zero_outbox_max_publish_attempts,
                     f"no topic route for event_type={row['event_type']}", row["id"]),
                )
                logger.error("unroutable outbox row id=%s event_type=%s", row["id"], row["event_type"])
                continue
            try:
                payload = row["payload"]
                if not isinstance(payload, str):
                    payload = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
                producer.produce(topic, key=message_key(row).encode(), value=payload.encode())
                if producer.flush(10) != 0:
                    raise RuntimeError("Kafka delivery timed out")
                conn.execute(
                    """
                    UPDATE service.event_outbox
                    SET published_at=now(), publish_attempts=publish_attempts+1, last_error=NULL
                    WHERE id=%s
                    """,
                    (row["id"],),
                )
                published += 1
            except Exception as exc:
                conn.execute(
                    """
                    UPDATE service.event_outbox
                    SET publish_attempts=publish_attempts+1, last_error=%s
                    WHERE id=%s
                    """,
                    (str(exc)[:500], row["id"]),
                )
                logger.exception("outbox publish failed id=%s", row["id"])
                break
    return published


def main() -> None:
    if not settings.zero_database_url:
        raise RuntimeError("ZERO_DATABASE_URL is required for the zero outbox publisher")
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    producer = Producer(
        {
            "bootstrap.servers": settings.kafka_bootstrap_servers,
            "client.id": "zero-outbox-publisher",
            "enable.idempotence": True,
            "acks": "all",
            # gzip, not snappy — aiokafka consumers (diet-service) cannot
            # decompress snappy without an extra C library. See app/outbox.py.
            "compression.type": "gzip",
            "delivery.timeout.ms": 30000,
        }
    )
    logger.info("zero outbox publisher started; routing %s and user.* -> %s",
                settings.request_topic, settings.activity_topic)
    while running:
        try:
            with psycopg.connect(settings.zero_database_url, row_factory=dict_row) as conn:
                while running:
                    if publish_batch(conn, producer) == 0:
                        time.sleep(settings.zero_outbox_poll_seconds)
        except Exception:
            logger.exception("publisher loop failed; reconnecting")
            time.sleep(2)
    producer.flush(10)


if __name__ == "__main__":
    main()
