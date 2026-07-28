from confluent_kafka import Producer, Consumer
from kafka.config import BOOTSTRAP_SERVERS, MAX_POLL_INTERVAL_MS


def producer_config() -> dict:
    return {
        "bootstrap.servers": BOOTSTRAP_SERVERS,
        "enable.idempotence": True,
        "acks": "all",
    }


def consumer_config(group_id: str) -> dict:
    return {
        "bootstrap.servers": BOOTSTRAP_SERVERS,
        "group.id": group_id,
        "enable.auto.commit": False,
        "auto.offset.reset": "earliest",
        "max.poll.interval.ms": MAX_POLL_INTERVAL_MS,
    }


def make_producer() -> Producer:
    return Producer(producer_config())


def make_consumer(group_id: str) -> Consumer:
    return Consumer(consumer_config(group_id))
