from __future__ import annotations

import unittest

from app.contracts import validate_activity_event


class ActivityContractTests(unittest.TestCase):
    def test_accepts_postgres_user_id(self) -> None:
        event = validate_activity_event({
            "event_id": "018f2c87-9f62-7d91-8baa-3b7c2a7f6d44",
            "event_type": "user.diet.photo_requested",
            "user_id": 42,
            "occurred_at": "2026-07-20T12:00:00+00:00",
            "producer": "diet-service",
            "schema_version": 1,
            "properties": {"meal_log_id": "018f2c87-9f62-7d91-8baa-3b7c2a7f6d45"},
        })
        self.assertEqual(event["user_id"], 42)

    def test_rejects_mongo_style_string_user_id(self) -> None:
        with self.assertRaises(ValueError):
            validate_activity_event({
                "event_id": "018f2c87-9f62-7d91-8baa-3b7c2a7f6d44",
                "event_type": "user.login.succeeded",
                "user_id": "507f1f77bcf86cd799439011",
                "occurred_at": "2026-07-20T12:00:00+00:00",
                "producer": "login-service",
                "schema_version": 1,
                "properties": {},
            })
