from __future__ import annotations

import os
import sys
import types
import unittest

os.environ.update({
    "DATABASE_URL": "postgresql://x/x",
    "KAFKA_BOOTSTRAP_SERVERS": "x:9092",
    "MINIO_ENDPOINT": "x:9000",
    "MINIO_ACCESS_KEY": "x",
    "MINIO_SECRET_KEY": "x",
})

# psycopg/confluent_kafka are only present inside the container image; the
# routing helpers under test do not touch either.
for _name, _attrs in (("psycopg", ("connect", "Connection")),
                      ("confluent_kafka", ("Producer",))):
    if _name not in sys.modules:
        _mod = types.ModuleType(_name)
        for _attr in _attrs:
            setattr(_mod, _attr, type(_attr, (object,), {}))
        sys.modules[_name] = _mod
if "psycopg.rows" not in sys.modules:
    _rows = types.ModuleType("psycopg.rows")
    _rows.dict_row = object()
    sys.modules["psycopg.rows"] = _rows
    sys.modules["psycopg"].rows = _rows

from app.config import load_settings
from app.zero_outbox_publisher import message_key, topic_for

_settings = load_settings()


class TopicRoutingTests(unittest.TestCase):
    def test_photo_request_routes_to_request_topic(self) -> None:
        self.assertEqual(topic_for("diet.photo.requested", _settings), "diet.photo.requested")

    def test_user_events_route_to_activity_topic(self) -> None:
        for event_type in ("user.auth.login_succeeded", "user.diet.photo_uploaded", "user.diet.meal_confirmed"):
            self.assertEqual(topic_for(event_type, _settings), "user.activity.raw", event_type)

    def test_unknown_event_type_is_unroutable(self) -> None:
        # Never guess a topic: an unroutable row is parked with last_error
        # instead of being published somewhere a consumer will not look.
        for event_type in ("diet.photo.completed", "recipe.created", ""):
            self.assertIsNone(topic_for(event_type, _settings), event_type)


class MessageKeyTests(unittest.TestCase):
    def test_user_id_wins(self) -> None:
        row = {"user_id": 42, "aggregate_id": "agg", "event_id": "ev"}
        self.assertEqual(message_key(row), "42")

    def test_falls_back_to_aggregate_then_event(self) -> None:
        self.assertEqual(message_key({"user_id": None, "aggregate_id": "agg", "event_id": "ev"}), "agg")
        self.assertEqual(message_key({"user_id": None, "aggregate_id": None, "event_id": "ev"}), "ev")
