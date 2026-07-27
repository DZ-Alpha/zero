from __future__ import annotations

import json
import logging
import threading
import time

from confluent_kafka import Producer

from app.config import Settings
from app.db import connect


logger = logging.getLogger(__name__)


class OutboxPublisher(threading.Thread):
    def __init__(self, settings: Settings) -> None:
        super().__init__(name="outbox-publisher", daemon=True)
        self.settings = settings
        self.stop_event = threading.Event()
        self.producer = Producer(
            {
                "bootstrap.servers": settings.kafka_bootstrap_servers,
                "client.id": "dangdang-outbox-publisher",
                "enable.idempotence": True,
                "acks": "all",
                # gzip, not snappy: diet-service consumes these topics with
                # aiokafka (pure python), whose snappy support needs an extra
                # C library the backend image does not ship. A snappy batch
                # kills its fetch task silently. gzip decodes with the stdlib.
                "compression.type": "gzip",
                "delivery.timeout.ms": 30000,
            }
        )

    def stop(self) -> None:
        self.stop_event.set()

    def run(self) -> None:
        next_cleanup = time.monotonic() + self.settings.outbox_cleanup_interval_seconds
        while not self.stop_event.is_set():
            self.publish_batch()
            if time.monotonic() >= next_cleanup:
                self.sweep_published()
                next_cleanup = time.monotonic() + self.settings.outbox_cleanup_interval_seconds
            self.stop_event.wait(self.settings.outbox_poll_seconds)
        self.producer.flush(10)

    def sweep_published(self) -> None:
        """Drop outbox rows that were published long enough ago to be settled.

        Only rows with a published_at are eligible, and the retention window is
        deliberately far longer than Kafka's own retention: the unique index on
        (topic, causation_event_id) is a duplicate-publish guard, so a row must
        outlive any window in which the same event could still be redelivered.
        Deletes are batched so one sweep cannot lock the table for long.
        """
        deleted = 0
        try:
            while not self.stop_event.is_set():
                with connect(self.settings) as conn:
                    removed = conn.execute(
                        """
                        DELETE FROM outbox_events
                        WHERE id IN (
                            SELECT id FROM outbox_events
                            WHERE published_at IS NOT NULL
                              AND published_at < now() - make_interval(days => %s)
                            ORDER BY id
                            LIMIT 5000
                        )
                        """,
                        (self.settings.outbox_retention_days,),
                    ).rowcount
                deleted += removed
                if removed < 5000:
                    break
        except Exception:
            logger.exception("outbox retention sweep failed after %s rows", deleted)
            return
        if deleted:
            logger.info("outbox retention sweep removed %s published row(s) older than %s day(s)",
                        deleted, self.settings.outbox_retention_days)

    def publish_batch(self) -> None:
        try:
            with connect(self.settings) as conn:
                rows = conn.execute(
                    """
                    SELECT id, topic, event_key, payload
                    FROM outbox_events
                    WHERE published_at IS NULL
                    ORDER BY id
                    LIMIT 20
                    FOR UPDATE SKIP LOCKED
                    """
                ).fetchall()
                for row in rows:
                    try:
                        payload = row["payload"]
                        if not isinstance(payload, str):
                            payload = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
                        self.producer.produce(
                            row["topic"],
                            key=row["event_key"].encode(),
                            value=payload.encode(),
                        )
                        if self.producer.flush(10) != 0:
                            raise RuntimeError("Kafka delivery timed out")
                        conn.execute(
                            "UPDATE outbox_events SET published_at=now(), publish_attempts=publish_attempts+1, last_error=NULL WHERE id=%s",
                            (row["id"],),
                        )
                    except Exception as exc:  # keep the row for a later retry
                        conn.execute(
                            "UPDATE outbox_events SET publish_attempts=publish_attempts+1, last_error=%s WHERE id=%s",
                            (str(exc)[:500], row["id"]),
                        )
                        logger.exception("outbox publish failed for id=%s", row["id"])
                        break
        except Exception:
            logger.exception("outbox batch failed")
            time.sleep(1)

