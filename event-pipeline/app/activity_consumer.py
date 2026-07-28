from __future__ import annotations

import json
import logging
import signal
import time
from typing import Any

from confluent_kafka import Consumer, KafkaException
from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.errors import DuplicateKeyError

from app.config import load_settings
from app.contracts import validate_activity_event


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)
settings = load_settings()
running = True


def stop(*_: Any) -> None:
    global running
    running = False


def main() -> None:
    if not settings.mongodb_uri:
        raise RuntimeError("MONGODB_URI is required for the activity consumer")
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    mongo = MongoClient(settings.mongodb_uri, serverSelectionTimeoutMS=5000, connectTimeoutMS=5000)
    collection = mongo[settings.activity_mongodb_database][settings.activity_mongodb_collection]
    collection.create_index([("user_id", ASCENDING), ("occurred_at", DESCENDING)])
    collection.create_index([("event_type", ASCENDING), ("occurred_at", DESCENDING)])
    consumer = Consumer({
        "bootstrap.servers": settings.kafka_bootstrap_servers,
        "group.id": settings.activity_consumer_group,
        "client.id": "dangdang-activity-mongodb-consumer",
        "enable.auto.commit": False,
        "auto.offset.reset": "earliest",
    })
    consumer.subscribe([settings.activity_topic])
    try:
        while running:
            message = consumer.poll(1.0)
            if message is None:
                continue
            if message.error():
                raise KafkaException(message.error())
            try:
                event = validate_activity_event(json.loads(message.value() or b""))
                document = {"_id": event["event_id"], **event}
                try:
                    collection.insert_one(document)
                except DuplicateKeyError:
                    logger.info("duplicate activity event ignored event_id=%s", event["event_id"])
            except (ValueError, KeyError, TypeError, json.JSONDecodeError):
                logger.exception("invalid activity event; offset remains uncommitted")
                time.sleep(1)
                continue
            consumer.commit(message=message, asynchronous=False)
    finally:
        consumer.close()
        mongo.close()


if __name__ == "__main__":
    main()
