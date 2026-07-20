import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.meal_item import MealItem
from app.models.meal_log import MealLog
from app.models.product_ref import ProductRef
from app.models.recipe_ref import RecipeRef
from app.models.user_health_profile_ref import UserHealthProfileRef
from app.services.outbox import enqueue_activity, enqueue_outbox


class MealLogNotFoundError(Exception):
    pass


class ProductNotFoundError(Exception):
    pass


class RecipeNotFoundError(Exception):
    pass


class MealLogNotConfirmableError(Exception):
    pass


# ── MealLog ──────────────────────────────────────────────────────────────────

async def create_meal_log(
    db: AsyncSession,
    *,
    user_id: int,
    image_object_key: str,
    meal_type: str = "SNACK",
    input_type: str = "VISION",
    eaten_at: datetime | None = None,
) -> MealLog:
    """PENDING meal_log 생성 + 같은 트랜잭션 안에서 diet.photo.requested outbox
    이벤트 기록 + user.diet.photo_uploaded 활동 이벤트 기록. Kafka 발행은 이
    서비스가 하지 않는다 — zero-db의 outbox publisher가 service.event_outbox를
    폴링해서 발행한다."""
    log = MealLog(
        meal_log_id=uuid.uuid4(),
        user_id=user_id,
        input_type=input_type,
        meal_type=meal_type,
        image_object_key=image_object_key,
        analysis_status="PENDING",
        eaten_at=eaten_at or datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
    )
    db.add(log)
    await db.flush()

    # 개발팀 요청서 정정 2 — worker 쪽 diet_analysis_jobs.user_id 컬럼이 text라
    # 정수를 보내면 스키마 검증에서 거부(INVALID_EVENT)된다. 요청 이벤트에만
    # str(user_id)로 넣는다 (user.activity.raw는 반대로 정수 필수, enqueue_activity 참고).
    request_event = await enqueue_outbox(
        db,
        event_type="diet.photo.requested",
        user_id=user_id,
        producer="diet-service",
        aggregate_type="meal_log",
        aggregate_id=str(log.meal_log_id),
        payload={"job_id": str(log.meal_log_id), "image_key": image_object_key, "user_id": str(user_id)},
    )
    # worker가 diet.photo.completed/failed에 실어 보내는 causation_event_id로
    # 이 meal_log를 다시 찾기 위한 멱등 키 (app/services/vision_consumer.py).
    log.request_event_id = request_event.event_id

    await enqueue_activity(
        db,
        event_type="user.diet.photo_uploaded",
        user_id=user_id,
        producer="diet-service",
        properties={"meal_log_id": str(log.meal_log_id), "meal_type": meal_type},
    )

    await db.commit()
    await db.refresh(log)
    return log


async def get_meal_log_by_request_event_id(db: AsyncSession, request_event_id: uuid.UUID) -> MealLog | None:
    """Kafka consumer가 causation_event_id로 원본 meal_log를 찾을 때 쓴다."""
    result = await db.execute(select(MealLog).where(MealLog.request_event_id == request_event_id))
    return result.scalar_one_or_none()


async def get_meal_log(db: AsyncSession, meal_log_id: uuid.UUID) -> MealLog:
    result = await db.execute(select(MealLog).where(MealLog.meal_log_id == meal_log_id))
    log = result.scalar_one_or_none()
    if log is None:
        raise MealLogNotFoundError(f"식단 기록을 찾을 수 없습니다: {meal_log_id}")
    return log


async def get_meal_log_for_user(db: AsyncSession, meal_log_id: uuid.UUID, user_id: int) -> MealLog:
    """소유자 검증 포함 조회."""
    log = await get_meal_log(db, meal_log_id)
    if log.user_id != user_id:
        raise MealLogNotFoundError(f"식단 기록을 찾을 수 없습니다: {meal_log_id}")
    return log


async def complete_meal_log(db: AsyncSession, meal_log_id: uuid.UUID, items: list[MealItem]) -> MealLog:
    """AI 분석 완료 처리: meal_items insert + status=COMPLETED."""
    log = await get_meal_log(db, meal_log_id)
    for item in items:
        db.add(item)
    log.analysis_status = "COMPLETED"
    await db.commit()
    await db.refresh(log)
    return log


async def _replace_meal_items(db: AsyncSession, meal_log_id: uuid.UUID, items: list[MealItem]) -> None:
    for existing in await get_meal_items(db, meal_log_id):
        await db.delete(existing)
    await db.flush()
    for item in items:
        db.add(item)


async def apply_vision_result(
    db: AsyncSession,
    meal_log_id: uuid.UUID,
    *,
    status: str,
    confidence: Decimal | None,
    provider: str | None,
    items: list[MealItem],
    retryable: bool | None = None,
) -> MealLog:
    """Kafka consumer(diet.photo.completed/failed) 처리: confidence/provider
    기록 + 상태 전이 + outbox.

    같은 causation_event_id로 재전달돼도(Kafka at-least-once) 안전하도록,
    이미 종결 상태(COMPLETED/FAILED)인 meal_log는 그대로 반환하고 재적용하지
    않는다 — vision_consumer.py는 이 반환값과 무관하게 매번 commit한다.
    """
    log = await get_meal_log(db, meal_log_id)
    if log.analysis_status in ("COMPLETED", "FAILED"):
        return log

    log.vision_confidence = confidence
    log.vision_provider = provider

    if status == "FAILED":
        log.analysis_status = "FAILED"
        log.vision_retryable = retryable
        await enqueue_outbox(
            db,
            event_type="diet.analysis_failed",
            user_id=log.user_id,
            producer="diet-service",
            aggregate_type="meal_log",
            aggregate_id=str(meal_log_id),
            payload={"meal_log_id": str(meal_log_id), "retryable": bool(retryable)},
        )
    else:
        await _replace_meal_items(db, meal_log_id, items)
        if status == "AWAITING_CONFIRMATION":
            log.analysis_status = "AWAITING_CONFIRMATION"
            log.needs_user_confirmation = True
        else:
            log.analysis_status = "COMPLETED"
            log.needs_user_confirmation = False
            await enqueue_outbox(
                db,
                event_type="diet.analysis_completed",
                user_id=log.user_id,
                producer="diet-service",
                aggregate_type="meal_log",
                aggregate_id=str(meal_log_id),
                payload={"meal_log_id": str(meal_log_id)},
            )

    await db.commit()
    await db.refresh(log)
    return log


async def confirm_meal_log(
    db: AsyncSession,
    meal_log_id: uuid.UUID,
    user_id: int,
    items: list[MealItem],
) -> MealLog:
    """사용자가 (수정 가능한) 초안을 확정 — AWAITING_CONFIRMATION에서만 허용."""
    log = await get_meal_log_for_user(db, meal_log_id, user_id)
    if log.analysis_status != "AWAITING_CONFIRMATION":
        raise MealLogNotConfirmableError(
            f"확정할 수 없는 상태입니다: {log.analysis_status}"
        )

    await _replace_meal_items(db, meal_log_id, items)
    log.analysis_status = "COMPLETED"
    log.needs_user_confirmation = False

    await enqueue_activity(
        db,
        event_type="user.diet.meal_confirmed",
        user_id=user_id,
        producer="diet-service",
        properties={"meal_log_id": str(meal_log_id)},
    )

    await db.commit()
    await db.refresh(log)
    return log


async def list_meal_logs_by_month(
    db: AsyncSession,
    user_id: int,
    year: int,
    month: int,
) -> list[MealLog]:
    """RC-0106: 월별 캘린더용 식단 목록."""
    from datetime import date
    import calendar

    _, last_day = calendar.monthrange(year, month)
    start = datetime(year, month, 1, tzinfo=timezone.utc)
    end = datetime(year, month, last_day, 23, 59, 59, tzinfo=timezone.utc)

    result = await db.execute(
        select(MealLog)
        .where(MealLog.user_id == user_id)
        .where(MealLog.eaten_at >= start)
        .where(MealLog.eaten_at <= end)
        .order_by(MealLog.eaten_at)
    )
    return list(result.scalars().all())


async def delete_meal_log(db: AsyncSession, log: MealLog) -> None:
    for item in await get_meal_items(db, log.meal_log_id):
        await db.delete(item)
    await db.delete(log)
    await db.commit()


# ── 식단 기록 CRUD (RC-0113~0117) ────────────────────────────────────────────
# "기록" = meal_log 1개 + meal_item 1개(1:1) — RC-0101/0103의 사진 업로드→AI분석
# 흐름(meal_log 1개에 items N개)과 달리, 사용자가 레시피/상품/사진 기록을 직접
# 값(serving/sugar/calories)까지 채워서 수동으로 남기는 기록이다.

async def get_records_for_range(
    db: AsyncSession, user_id: int, start: datetime, end: datetime
) -> list[tuple[MealLog, MealItem]]:
    result = await db.execute(
        select(MealLog, MealItem)
        .join(MealItem, MealItem.meal_log_id == MealLog.meal_log_id)
        .where(MealLog.user_id == user_id, MealLog.eaten_at >= start, MealLog.eaten_at <= end)
        .order_by(MealLog.eaten_at)
    )
    return list(result.all())


async def create_manual_record(
    db: AsyncSession,
    *,
    user_id: int,
    eaten_at: datetime,
    meal_type: str,
    input_type: str,
    item_name: str,
    serving: Decimal,
    sugar: Decimal,
    calories: Decimal,
    product_id: uuid.UUID | None = None,
    external_recipe_id: str | None = None,
) -> MealLog:
    log = MealLog(
        meal_log_id=uuid.uuid4(),
        user_id=user_id,
        input_type=input_type,
        meal_type=meal_type,
        image_object_key=None,
        analysis_status="COMPLETED",
        eaten_at=eaten_at,
        created_at=datetime.now(timezone.utc),
    )
    db.add(log)
    # meal_items.meal_log_id는 모델에 ForeignKey()가 없어(meal_item.py 주석 참고)
    # SQLAlchemy가 두 insert의 순서를 FK로 추론하지 못한다 — flush로 log부터
    # 먼저 실제 insert해 meal_log_id가 참조 가능하게 만든 뒤 item을 추가한다.
    await db.flush()

    item = MealItem(
        meal_item_id=uuid.uuid4(),
        meal_log_id=log.meal_log_id,
        product_id=product_id,
        external_recipe_id=external_recipe_id,
        item_name=item_name,
        serving_value=serving,
        # RC-0113 입력에는 단위가 없다 — 실제 컬럼은 NOT NULL이라 고정 단위로 저장.
        serving_unit="인분",
        calories=calories,
        sugars=sugar,
        # RC-0113 입력에 탄수화물이 없다 — 실제 컬럼은 NOT NULL이라 0으로 저장
        # (있는 것처럼 추정하지 않는다).
        carbohydrate=Decimal("0"),
    )
    db.add(item)

    await db.commit()
    await db.refresh(log)
    return log


async def update_record(
    db: AsyncSession,
    record_id: uuid.UUID,
    user_id: int,
    *,
    meal_type: str | None = None,
    serving: Decimal | None = None,
    sugar: Decimal | None = None,
    calories: Decimal | None = None,
) -> MealLog:
    log = await get_meal_log_for_user(db, record_id, user_id)
    items = await get_meal_items(db, record_id)
    if not items:
        raise MealLogNotFoundError(f"식단 기록 항목을 찾을 수 없습니다: {record_id}")
    item = items[0]

    if meal_type is not None:
        log.meal_type = meal_type
    if serving is not None:
        item.serving_value = serving
    if sugar is not None:
        item.sugars = sugar
    if calories is not None:
        item.calories = calories

    await db.commit()
    await db.refresh(log)
    return log


async def delete_record(db: AsyncSession, record_id: uuid.UUID, user_id: int) -> None:
    log = await get_meal_log_for_user(db, record_id, user_id)
    await delete_meal_log(db, log)


async def get_recipe_ref(db: AsyncSession, recipe_id: int) -> RecipeRef:
    result = await db.execute(select(RecipeRef).where(RecipeRef.id == recipe_id))
    recipe = result.scalar_one_or_none()
    if recipe is None:
        raise RecipeNotFoundError(f"레시피를 찾을 수 없습니다: {recipe_id}")
    return recipe


# ── MealItem ─────────────────────────────────────────────────────────────────

async def get_meal_items(db: AsyncSession, meal_log_id: uuid.UUID) -> list[MealItem]:
    result = await db.execute(
        select(MealItem).where(MealItem.meal_log_id == meal_log_id)
    )
    return list(result.scalars().all())


def make_meal_item_from_product(
    meal_log_id: uuid.UUID,
    product: ProductRef,
    serving_value: Decimal,
    serving_unit: str,
) -> MealItem:
    """Product 현재 값을 스냅샷으로 복제해 MealItem 생성.

    serving_value/serving_unit은 ProductRef(읽기전용 미러)가 안 갖고 있는 값이라
    호출 측에서 넘겨받는다(예: 사용자가 선택한 섭취량).
    """
    return MealItem(
        meal_item_id=uuid.uuid4(),
        meal_log_id=meal_log_id,
        product_id=product.product_id,
        item_name=product.product_name,
        serving_value=serving_value,
        serving_unit=serving_unit,
        calories=product.calories,
        sugars=product.sugars,
        carbohydrate=product.carbohydrate,
    )


def make_meal_item_from_analysis(
    meal_log_id: uuid.UUID,
    item_name: str,
    serving_value: Decimal,
    serving_unit: str,
    calories: Decimal,
    sugars: Decimal,
    carbohydrate: Decimal,
) -> MealItem:
    """AI/OCR 분석 결과로 MealItem 생성 (product_id 없음).

    실제 service.meal_items에는 protein/fat/sodium/raw_analysis 컬럼이 없어서
    분석 결과 중 이 값들은 저장하지 않는다 — RC-0103/0104 응답의 단백질/지방/
    나트륨 필드는 항상 null이 된다(app/routers/diet.py의 _item_dict 참고).
    """
    return MealItem(
        meal_item_id=uuid.uuid4(),
        meal_log_id=meal_log_id,
        item_name=item_name,
        serving_value=serving_value,
        serving_unit=serving_unit,
        calories=calories,
        sugars=sugars,
        carbohydrate=carbohydrate,
    )


# ── Product 스냅샷 조회 ───────────────────────────────────────────────────────

async def get_product_ref(db: AsyncSession, product_id: uuid.UUID) -> ProductRef:
    result = await db.execute(select(ProductRef).where(ProductRef.product_id == product_id))
    p = result.scalar_one_or_none()
    if p is None:
        raise ProductNotFoundError(f"상품을 찾을 수 없습니다: {product_id}")
    return p


# ── 홈 당/칼로리 게이지 (MN-0106~0108) ────────────────────────────────────────

async def get_today_totals(db: AsyncSession, user_id: int) -> dict:
    """오늘 날짜 칼로리/당 합계 — v_meal_totals 뷰 기반."""
    row = await db.execute(
        text("""
            SELECT
                COALESCE(SUM(vt.total_calories), 0) AS calories,
                COALESCE(SUM(vt.total_sugars), 0)   AS sugars
            FROM service.meal_logs ml
            JOIN service.v_meal_totals vt ON vt.meal_log_id = ml.meal_log_id
            WHERE ml.user_id = :uid
              AND date_trunc('day', ml.eaten_at AT TIME ZONE 'UTC') =
                  date_trunc('day', now() AT TIME ZONE 'UTC')
        """),
        {"uid": user_id},
    )
    r = row.one()
    return {"cal": float(r.calories), "sugar": float(r.sugars)}


# ── 사용자 건강 프로필 (MN-0106 게이지 목표값) ──────────────────────────────────

async def get_user_health_profile(
    db: AsyncSession, user_id: int
) -> UserHealthProfileRef | None:
    result = await db.execute(
        select(UserHealthProfileRef).where(UserHealthProfileRef.user_id == user_id)
    )
    return result.scalar_one_or_none()
