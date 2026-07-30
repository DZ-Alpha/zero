import uuid
from decimal import Decimal
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

from app.services import diet_store


class ApplyVisionResultActivityEventTests(IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.db = SimpleNamespace(commit=AsyncMock(), refresh=AsyncMock())
        self.meal_log_id = uuid.uuid4()
        self.log = SimpleNamespace(
            meal_log_id=self.meal_log_id,
            user_id=42,
            analysis_status="PENDING",
            vision_confidence=None,
            vision_provider=None,
            vision_retryable=None,
            needs_user_confirmation=False,
        )

    async def test_completed_enqueues_user_activity_event(self) -> None:
        with (
            patch.object(diet_store, "get_meal_log", AsyncMock(return_value=self.log)),
            patch.object(diet_store, "_replace_meal_items", AsyncMock()) as replace_items,
            patch.object(diet_store, "enqueue_activity", AsyncMock()) as enqueue_activity,
            patch.object(diet_store, "enqueue_outbox", AsyncMock()) as enqueue_outbox,
            patch.object(diet_store, "_notify_room_meal_recorded", AsyncMock()) as notify,
        ):
            await diet_store.apply_vision_result(
                self.db,
                self.meal_log_id,
                status="COMPLETED",
                confidence=Decimal("0.91"),
                provider="gemini",
                items=[],
            )

        replace_items.assert_awaited_once_with(self.db, self.meal_log_id, [])
        enqueue_activity.assert_awaited_once_with(
            self.db,
            event_type="user.diet.analysis_completed",
            user_id=42,
            producer="diet-service",
            properties={"meal_log_id": str(self.meal_log_id)},
        )
        enqueue_outbox.assert_not_awaited()
        notify.assert_awaited_once_with(self.log)
        self.assertEqual(self.log.analysis_status, "COMPLETED")

    async def test_failed_enqueues_user_activity_event(self) -> None:
        with (
            patch.object(diet_store, "get_meal_log", AsyncMock(return_value=self.log)),
            patch.object(diet_store, "enqueue_activity", AsyncMock()) as enqueue_activity,
            patch.object(diet_store, "enqueue_outbox", AsyncMock()) as enqueue_outbox,
            patch.object(diet_store, "_notify_room_meal_recorded", AsyncMock()) as notify,
        ):
            await diet_store.apply_vision_result(
                self.db,
                self.meal_log_id,
                status="FAILED",
                confidence=None,
                provider="gemini",
                items=[],
                retryable=True,
            )

        enqueue_activity.assert_awaited_once_with(
            self.db,
            event_type="user.diet.analysis_failed",
            user_id=42,
            producer="diet-service",
            properties={"meal_log_id": str(self.meal_log_id), "retryable": True},
        )
        enqueue_outbox.assert_not_awaited()
        notify.assert_not_awaited()
        self.assertEqual(self.log.analysis_status, "FAILED")
        self.assertTrue(self.log.vision_retryable)
