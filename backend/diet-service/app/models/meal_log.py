import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class MealLog(Base):
    """Diet Service 소유 — service.meal_logs.

    input_type: VISION | MANUAL | PRODUCT | RECIPE (실제 DB CHECK 제약)
    analysis_status: PENDING | PROCESSING | AWAITING_CONFIRMATION | COMPLETED | FAILED
      (실제 DB CHECK 제약 — AWAITING_CONFIRMATION은 2026-07-20 이벤트 파이프라인
      연동 작업으로 추가됨, Vision confidence가 낮을 때 사용자 확인 대기 상태)
    meal_type: BREAKFAST | LUNCH | DINNER | SNACK | OTHER (실제 DB CHECK 제약 —
      'DAILY'는 허용되지 않는다. "하루 식단" 업로드는 OTHER로 매핑한다,
      app/routers/diet.py 참고)
    """

    __tablename__ = "meal_logs"
    __table_args__ = {"schema": "service"}

    meal_log_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[int] = mapped_column(nullable=False)           # FK → public.users(id), 소프트 참조
    input_type: Mapped[str] = mapped_column(String(20), default="VISION")
    meal_type: Mapped[str] = mapped_column(String(20), default="SNACK")
    # 실제 컬럼명은 image_object_key (image_url이 아님)
    image_object_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    analysis_status: Mapped[str] = mapped_column(String(20), default="PENDING")
    # diet.photo.requested 발행 시 event_outbox row에 배정된 event_id를 그대로
    # 저장해둔다 — worker가 diet.photo.completed/failed에 실어 보내는
    # causation_event_id와 매칭해 어느 meal_log인지 찾는 멱등 키 (개발팀 요청서
    # 정정 1). worker의 upload_id/analysis_id는 우리 meal_log_id와 다른 값이라
    # 이걸로 매칭할 수 없다.
    request_event_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    # Vision worker(zero-db dangdang-pipeline-worker)가 Kafka로 채워준다.
    vision_confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3), nullable=True)
    vision_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    needs_user_confirmation: Mapped[bool] = mapped_column(default=False)
    # retryable=true FAILED 재시도 UI 분기용 (개발팀 요청서 정정 1). FAILED가
    # 아니면 의미 없음(null).
    vision_retryable: Mapped[bool | None] = mapped_column(nullable=True)
    eaten_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
