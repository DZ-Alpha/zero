"""결과 이벤트 재전달 시 종결된 meal_log를 덮어쓰지 않는지 확인한다.

Kafka/SQS 모두 at-least-once라 같은 causation_event_id가 두 번 오는 것은
정상이다. 그때 apply_vision_result가 이미 결과가 반영된 행을 다시 건드리면
사용자가 확인·수정한 meal_items가 사라진다.

AWS 전환 후에는 이 경로가 더 자주 열린다 — SQS visibility timeout 만료는
Kafka 리플레이보다 흔하고, 지금 앞단에서 중복을 걸러주던 pipeline DB의
processed_events도 함께 폐기된다.
"""

import uuid
from decimal import Decimal
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

from app.services import diet_store


class ApplyVisionResultFinalStateTests(IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.db = SimpleNamespace(commit=AsyncMock(), refresh=AsyncMock())
        self.meal_log_id = uuid.uuid4()

    def _log(self, status: str) -> SimpleNamespace:
        return SimpleNamespace(
            meal_log_id=self.meal_log_id,
            user_id=42,
            analysis_status=status,
            vision_confidence=Decimal("0.91"),
            vision_provider="gemini-first-delivery",
            vision_retryable=None,
            needs_user_confirmation=(status == "AWAITING_CONFIRMATION"),
        )

    async def _redeliver(self, log: SimpleNamespace):
        """같은 결과 이벤트가 한 번 더 도착한 상황을 재현한다."""
        with (
            patch.object(diet_store, "get_meal_log", AsyncMock(return_value=log)),
            patch.object(diet_store, "_replace_meal_items", AsyncMock()) as replace_items,
            patch.object(diet_store, "enqueue_activity", AsyncMock()) as enqueue_activity,
            patch.object(diet_store, "enqueue_outbox", AsyncMock()),
            patch.object(diet_store, "_notify_room_meal_recorded", AsyncMock()) as notify,
        ):
            returned = await diet_store.apply_vision_result(
                self.db,
                self.meal_log_id,
                status="COMPLETED",
                confidence=Decimal("0.42"),
                provider="gemini-redelivered",
                items=[object()],
            )
        return returned, replace_items, enqueue_activity, notify

    def _assert_untouched(self, log, returned, replace_items, enqueue_activity, notify) -> None:
        self.assertIs(returned, log)
        replace_items.assert_not_awaited()
        enqueue_activity.assert_not_awaited()
        notify.assert_not_awaited()
        self.db.commit.assert_not_awaited()
        self.assertEqual(log.vision_provider, "gemini-first-delivery")
        self.assertEqual(log.vision_confidence, Decimal("0.91"))

    async def test_completed_is_final(self) -> None:
        log = self._log("COMPLETED")
        self._assert_untouched(log, *await self._redeliver(log))
        self.assertEqual(log.analysis_status, "COMPLETED")

    async def test_failed_is_final(self) -> None:
        log = self._log("FAILED")
        self._assert_untouched(log, *await self._redeliver(log))
        self.assertEqual(log.analysis_status, "FAILED")

    async def test_awaiting_confirmation_is_final(self) -> None:
        """실측 314건(요청 이벤트를 가진 647건의 48%)이 이 상태다.

        '확인 대기'는 결과가 아직 없다는 뜻이 아니라 이미 반영됐고 사용자
        확정만 남았다는 뜻이다. 재전달로 meal_items를 교체하면 사용자가
        확인 중이던 항목이 사라진다.
        """
        log = self._log("AWAITING_CONFIRMATION")
        self._assert_untouched(log, *await self._redeliver(log))
        self.assertEqual(log.analysis_status, "AWAITING_CONFIRMATION")
        self.assertTrue(log.needs_user_confirmation)

    async def test_pending_is_still_applied(self) -> None:
        """가드가 넓어져 정상 최초 반영까지 막지 않는지 확인한다."""
        log = self._log("PENDING")
        log.needs_user_confirmation = False
        returned, replace_items, enqueue_activity, notify = await self._redeliver(log)

        self.assertIs(returned, log)
        replace_items.assert_awaited_once()
        enqueue_activity.assert_awaited_once()
        notify.assert_awaited_once()
        self.db.commit.assert_awaited_once()
        self.assertEqual(log.analysis_status, "COMPLETED")
        self.assertEqual(log.vision_provider, "gemini-redelivered")
