import calendar
import json
import logging
import uuid
from datetime import date as date_cls
from datetime import datetime, time, timezone
from decimal import Decimal

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user, get_current_user_bearer
from app.core.config import settings
from app.core.database import get_db
from app.services.diet_store import (
    MealLogNotFoundError,
    ProductNotFoundError,
    RecipeNotFoundError,
    complete_meal_log,
    create_manual_record,
    create_meal_log,
    delete_meal_log,
    delete_record,
    get_meal_items,
    get_meal_log_for_user,
    get_product_ref,
    get_records_for_range,
    get_recipe_ref,
    list_meal_logs_by_month,
    make_meal_item_from_analysis,
    make_meal_item_from_product,
    update_record,
)

logger = logging.getLogger("diet_service.diet")

router = APIRouter(prefix="/diet")


def _to_uuid(value: str, label: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"유효하지 않은 {label} UUID 형식입니다.")


def _to_int(value: str, label: str) -> int:
    try:
        return int(value)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"유효하지 않은 {label} 형식입니다.")


_MEAL_TYPE_KO = {"아침": "BREAKFAST", "점심": "LUNCH", "저녁": "DINNER", "간식": "SNACK"}
_MEAL_TYPES = {"BREAKFAST", "LUNCH", "DINNER", "SNACK", "OTHER"}


def _normalize_meal_type(value: str) -> str:
    mapped = _MEAL_TYPE_KO.get(value, value.upper())
    if mapped not in _MEAL_TYPES:
        raise HTTPException(status_code=422, detail=f"유효하지 않은 mealType입니다: {value}")
    return mapped


def _parse_date(value: str) -> datetime:
    try:
        d = date_cls.fromisoformat(value[:10])
    except ValueError:
        raise HTTPException(status_code=422, detail="date 형식이 올바르지 않습니다 (YYYY-MM-DD).")
    return datetime.combine(d, time.min, tzinfo=timezone.utc)


_INPUT_TYPE_TO_ITEM_TYPE = {"PRODUCT": "product", "RECIPE": "recipe", "VISION": "photo", "MANUAL": "photo"}


def _item_dict(item) -> dict:
    # service.meal_items에는 단백질/지방/나트륨 컬럼이 없다(실제 스키마 확인
    # 완료) — 있는 것처럼 꾸미지 않고 null로 명시한다.
    return {
        "name": item.item_name,
        "dang": float(item.sugars) if item.sugars is not None else None,
        "calo": float(item.calories) if item.calories is not None else None,
        "ingred-list": [
            {"name": "탄수화물", "amount": float(item.carbohydrate) if item.carbohydrate is not None else None},
            {"name": "단백질", "amount": None},
            {"name": "지방", "amount": None},
            {"name": "나트륨", "amount": None},
        ],
    }


# RC-0101: 한끼 식단 사진 업로드
# RC-0102: 하루 식단 사진 업로드 (mode=daily)
@router.post("/upload")
async def upload_diet(
    body: dict,
    db: AsyncSession = Depends(get_db),
    payload: dict = Depends(get_current_user),
) -> dict[str, object]:
    """RC-0101~0102: 식단 사진 URL 등록 → meal_log 생성 (분석은 별도 호출).

    body: {img: S3_URL, mode: 'daily'(optional)}
    """
    user_id: int = payload["user_id"]
    image_object_key: str | None = body.get("img")
    if not image_object_key:
        raise HTTPException(status_code=422, detail="필수 필드 누락: img")

    # 실제 DB의 meal_type CHECK 제약엔 'DAILY'가 없다(BREAKFAST/LUNCH/DINNER/
    # SNACK/OTHER만 허용) — "하루 식단" 업로드는 OTHER로 매핑한다.
    meal_type = "OTHER" if body.get("mode") == "daily" else "SNACK"

    log = await create_meal_log(
        db,
        user_id=user_id,
        image_object_key=image_object_key,
        meal_type=meal_type,
        input_type="VISION",
    )
    logger.info("diet: meal_log created meal_log_id=%s user_id=%s", log.meal_log_id, user_id)
    return {"status": "SUCCESS", "id": str(log.meal_log_id)}


# RC-0103: AI 식단 분석 (Vision AI → 음식 인식 + 영양 추정)
@router.get("/ai-analyze")
async def ai_analyze(
    id: str = Query(..., description="meal_log UUID"),
    db: AsyncSession = Depends(get_db),
    payload: dict = Depends(get_current_user),
) -> dict[str, object]:
    """RC-0103: meal_log의 이미지를 AI로 분석해 meal_items 저장.

    실제 Vision AI 파이프라인 미구현 → PREPARING 상태 반환.
    구현 시: 이미지 URL로 Claude Vision 또는 외부 API 호출,
    응답 파싱 후 make_meal_item_from_analysis로 items 생성,
    complete_meal_log(db, id, items) 로 저장.
    """
    user_id: int = payload["user_id"]
    log_id = _to_uuid(id, "meal_log ID")

    try:
        await get_meal_log_for_user(db, log_id, user_id)
    except MealLogNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return {
        "status": "PREPARING",
        "message": "AI 식단 분석 기능은 Vision AI 파이프라인 연동 후 활성화됩니다.",
        "id": str(log_id),
        "list-diet": [],
    }


# RC-0104: OCR 분석 결과 (제품 영양성분 표 인식)
@router.get("/other-foods")
async def other_foods(
    id: str = Query(..., description="meal_log UUID"),
    db: AsyncSession = Depends(get_db),
    payload: dict = Depends(get_current_user),
) -> dict[str, object]:
    """RC-0104: meal_log에 저장된 분석 결과 조회 (합계 + 항목 목록).

    upload 후 ai-analyze 완료된 결과를 읽어 반환.
    """
    user_id: int = payload["user_id"]
    log_id = _to_uuid(id, "meal_log ID")

    try:
        log = await get_meal_log_for_user(db, log_id, user_id)
    except MealLogNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    if log.analysis_status == "PENDING":
        return {"status": "PENDING", "message": "분석이 아직 완료되지 않았습니다.", "id": str(log_id)}

    items = await get_meal_items(db, log_id)
    total_cal = sum(float(i.calories or 0) for i in items)
    total_sugar = sum(float(i.sugars or 0) for i in items)

    return {
        "id": str(log_id),
        "dang": total_sugar,
        "calo": total_cal,
        "list-diet": [_item_dict(i) for i in items],
    }


# RC-0105: 대체 제품 추천 (Product Service 검색 API 위임)
@router.get("/recommend-alt")
async def recommend_alt(
    id: str = Query(..., description="meal_log UUID"),
    db: AsyncSession = Depends(get_db),
    payload: dict = Depends(get_current_user),
) -> dict[str, object]:
    """RC-0105: 식단 내 제품의 저당/제로 대체 제품 추천 (Product Service 검색 위임).

    현재 PREPARING — Product Service /search 연동 후 활성화.
    """
    user_id: int = payload["user_id"]
    log_id = _to_uuid(id, "meal_log ID")

    try:
        await get_meal_log_for_user(db, log_id, user_id)
    except MealLogNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return {
        "status": "PREPARING",
        "message": "대체 제품 추천 기능은 Product Service 연동 후 활성화됩니다.",
        "list-products": [],
    }


# RC-0106: 캘린더 (날짜별 식단 기록)
@router.get("/calender")
async def calender(
    year: int = Query(..., description="연도 (예: 2026)"),
    month: int = Query(..., ge=1, le=12, description="월 (1~12)"),
    db: AsyncSession = Depends(get_db),
    payload: dict = Depends(get_current_user),
) -> dict[str, object]:
    """RC-0106: 월별 캘린더 — 날짜별 식단 목록."""
    user_id: int = payload["user_id"]

    logs = await list_meal_logs_by_month(db, user_id, year, month)
    return {
        "list": [
            {
                "date": log.eaten_at.strftime("%Y-%m-%d"),
                "name": log.meal_type,
                # usr는 토큰이라 응답에 그대로 안 심는다 — 프론트가 자기 토큰으로 붙여서 호출.
                "url": f"/diet/other-foods?id={log.meal_log_id}",
            }
            for log in logs
        ]
    }


class DietRecordCreateBody(BaseModel):
    date: str
    mealType: str
    itemType: str
    itemId: str
    serving: Decimal
    sugar: Decimal
    calories: Decimal


class DietRecordUpdateBody(BaseModel):
    mealType: str | None = None
    serving: Decimal | None = None
    sugar: Decimal | None = None
    calories: Decimal | None = None


def _record_item_dict(log, item) -> dict[str, object]:
    if item.product_id is not None:
        item_id = str(item.product_id)
    elif item.external_recipe_id is not None:
        item_id = item.external_recipe_id
    else:
        item_id = str(log.meal_log_id)
    return {
        "mealType": log.meal_type,
        "itemType": _INPUT_TYPE_TO_ITEM_TYPE.get(log.input_type, "photo"),
        "itemId": item_id,
        "name": item.item_name,
        "sugar": float(item.sugars) if item.sugars is not None else None,
        "calories": float(item.calories) if item.calories is not None else None,
    }


# RC-0113: 식단 기록 생성 (레시피/상품/사진 공통 기록 모델)
@router.post("/records")
async def create_diet_record(
    body: DietRecordCreateBody,
    db: AsyncSession = Depends(get_db),
    payload: dict = Depends(get_current_user_bearer),
) -> dict[str, object]:
    user_id: int = payload["user_id"]
    eaten_at = _parse_date(body.date)
    meal_type = _normalize_meal_type(body.mealType)

    if body.itemType == "product":
        pid = _to_uuid(body.itemId, "상품 ID")
        try:
            ref = await get_product_ref(db, pid)
        except ProductNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e))
        item_name, product_id, external_recipe_id, input_type = ref.product_name, pid, None, "PRODUCT"
    elif body.itemType == "recipe":
        rid = _to_int(body.itemId, "레시피 ID")
        try:
            ref = await get_recipe_ref(db, rid)
        except RecipeNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e))
        item_name, product_id, external_recipe_id, input_type = ref.name, None, str(rid), "RECIPE"
    elif body.itemType == "photo":
        item_name, product_id, external_recipe_id, input_type = "사진 기록", None, None, "VISION"
    else:
        raise HTTPException(status_code=422, detail="itemType은 recipe/product/photo 중 하나여야 합니다.")

    log = await create_manual_record(
        db,
        user_id=user_id,
        eaten_at=eaten_at,
        meal_type=meal_type,
        input_type=input_type,
        item_name=item_name,
        serving=body.serving,
        sugar=body.sugar,
        calories=body.calories,
        product_id=product_id,
        external_recipe_id=external_recipe_id,
    )
    logger.info("diet: record created meal_log_id=%s user_id=%s", log.meal_log_id, user_id)
    return {"status": "SUCCESS", "id": str(log.meal_log_id)}


# RC-0114: 식단 기록 수정
@router.put("/records/{id}")
async def update_diet_record(
    id: str,
    body: DietRecordUpdateBody,
    db: AsyncSession = Depends(get_db),
    payload: dict = Depends(get_current_user_bearer),
) -> dict[str, object]:
    user_id: int = payload["user_id"]
    record_id = _to_uuid(id, "기록 ID")
    meal_type = _normalize_meal_type(body.mealType) if body.mealType is not None else None

    try:
        await update_record(
            db, record_id, user_id,
            meal_type=meal_type, serving=body.serving, sugar=body.sugar, calories=body.calories,
        )
    except MealLogNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return {"status": "SUCCESS"}


# RC-0115: 식단 기록 삭제
@router.delete("/records/{id}")
async def delete_diet_record(
    id: str,
    db: AsyncSession = Depends(get_db),
    payload: dict = Depends(get_current_user_bearer),
) -> dict[str, object]:
    user_id: int = payload["user_id"]
    record_id = _to_uuid(id, "기록 ID")

    try:
        await delete_record(db, record_id, user_id)
    except MealLogNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return {"status": "SUCCESS"}


# RC-0116: 식단 기록 날짜별/월별 조회 + 합계
@router.get("/records")
async def list_diet_records(
    date: str | None = Query(None, description="YYYY-MM-DD"),
    year: int | None = Query(None),
    month: int | None = Query(None, ge=1, le=12),
    db: AsyncSession = Depends(get_db),
    payload: dict = Depends(get_current_user_bearer),
) -> dict[str, object]:
    user_id: int = payload["user_id"]

    if date:
        start = _parse_date(date)
        end = datetime.combine(start.date(), time.max, tzinfo=timezone.utc)
        response_date = start.strftime("%Y-%m-%d")
    elif year and month:
        _, last_day = calendar.monthrange(year, month)
        start = datetime(year, month, 1, tzinfo=timezone.utc)
        end = datetime(year, month, last_day, 23, 59, 59, tzinfo=timezone.utc)
        # 월 단위 조회는 명세 출력에 날짜별 그룹핑이 없어 date는 비워두고
        # list에 그 달 전체 기록을 펼쳐서 담는다.
        response_date = None
    else:
        raise HTTPException(status_code=422, detail="date 또는 year+month 파라미터가 필요합니다.")

    rows = await get_records_for_range(db, user_id, start, end)
    sugar_total = sum(float(item.sugars) for _, item in rows if item.sugars is not None)
    calories_total = sum(float(item.calories) for _, item in rows if item.calories is not None)

    return {
        "date": response_date,
        "sugar-total": sugar_total,
        "calories-total": calories_total,
        "list": [_record_item_dict(log, item) for log, item in rows],
    }


# RC-0117: 업로드 취소 (확정 전 draft 상태의 사진 업로드만 삭제 가능)
@router.delete("/upload/{id}")
async def cancel_diet_upload(
    id: str,
    db: AsyncSession = Depends(get_db),
    payload: dict = Depends(get_current_user_bearer),
) -> dict[str, object]:
    user_id: int = payload["user_id"]
    log_id = _to_uuid(id, "업로드 ID")

    try:
        log = await get_meal_log_for_user(db, log_id, user_id)
    except MealLogNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    if log.analysis_status == "COMPLETED":
        raise HTTPException(status_code=409, detail="이미 확정된 기록입니다. /diet/records/{id}로 삭제해주세요.")

    await delete_meal_log(db, log)
    return {"status": "SUCCESS"}
