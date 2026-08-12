import asyncio
import calendar
import json
import logging
import uuid
from datetime import date as date_cls
from datetime import datetime, time, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.services.diet_store import (
    MealLogNotConfirmableError,
    MealLogNotFoundError,
    ProductNotFoundError,
    RecipeNotFoundError,
    confirm_meal_log,
    create_manual_record,
    create_meal_log,
    delete_meal_log,
    delete_record,
    get_meal_items,
    get_meal_log_for_user,
    get_product_ref,
    get_product_refs_bulk,
    get_records_for_range,
    get_records_for_users_on_date,
    get_recipe_ref,
    get_recipe_refs_bulk,
    list_meal_logs_by_month,
    make_meal_item_from_analysis,
    make_meal_item_from_product,
    update_record,
)
from app.services.storage import StorageUploadError, presign_diet_photo_url, validate_diet_photo_key
from app.services.swap_rules import (
    is_already_low_sugar,
    is_credible_product_match,
    is_valid_swap_candidate,
    serving_key,
)

_KST = ZoneInfo("Asia/Seoul")

logger = logging.getLogger("diet_service.diet")

router = APIRouter(prefix="/diet")


def _recipe_thumbnail_url(recipe) -> str | None:
    # recipe-service의 app/routers/recipe.py의 _thumbnail_url()과 동일한
    # 폴백 - source="유튜브" 레시피는 thumbnail_url이 "/data/thumbnails/{id}.jpg"
    # 같은 상대경로인데 이걸 서빙하는 곳이 없어 항상 깨진다. 여기서 이 폴백을
    # 안 하면 유튜브 레시피로 기록한 사람만 얌로그 사진이 안 뜨는 것처럼 보인다
    # (실사용 중 재현 - "유저마다 이미지 들어가는 애/안 들어가는 애가 있다").
    if recipe.thumbnail_url and not recipe.thumbnail_url.startswith("/"):
        return recipe.thumbnail_url
    if recipe.video_id:
        return f"https://img.youtube.com/vi/{recipe.video_id}/hqdefault.jpg"
    return recipe.thumbnail_url


async def _photo_entry(log_id: uuid.UUID, object_key: str, photo_item_names: dict[uuid.UUID, list[str]]) -> dict[str, str]:
    # presign_diet_photo_url도 boto3(동기)라 event loop를 막는다 - 이 함수를
    # 부르는 internal_meal_records는 여러 유저의 사진을 한 번에 묶어 내려주므로
    # (얌로그 방 하나 조회에 사진이 여러 장) 순서대로 막혀서 부르면 사진 수만큼
    # 지연이 그대로 쌓인다. to_thread + gather로 병렬로 스레드에 위임한다.
    image_url = await asyncio.to_thread(presign_diet_photo_url, object_key)
    return {"imageUrl": image_url, "name": ", ".join(photo_item_names.get(log_id, [])) or "사진으로 기록한 식사"}


async def _resolve_photo_entries(
    photo_object_keys: dict[uuid.UUID, str],
    photo_item_names: dict[uuid.UUID, list[str]],
    include_photos: bool,
) -> list[dict[str, str]]:
    """includePhotos=false면 서명을 아예 건너뛴다 - 이 파라미터의 존재 이유다.
    얌로그가 이 엔드포인트를 부르는 6곳 중 4곳(방 요약/멤버 목록/주간 랭킹/
    배지 - community-service room_aggregation.py)은 사진을 한 장도 안 쓰고
    sugar와 connectedItems만 읽는데, 그동안 그 4곳도 "사람 수 x 사진 수"만큼
    SigV4 서명을 하고 그 URL을 JSON에 실어 보내고 있었다. 특히 주간 랭킹은
    방 하나에 77명을 한 번에 넘기면서 sugar 하나만 쓴다.

    connectedItems(레시피/저당픽 썸네일)는 서명 대상이 아니라 DB에 있는 값
    그대로라 비용이 없으므로 includePhotos와 무관하게 항상 내려준다 - 배지
    집계가 connectedItems의 source="recipe"를 세기 때문에, 이걸 같이 빼면
    배지 호출부는 이 파라미터를 못 쓴다."""
    if not include_photos:
        return []
    return list(await asyncio.gather(*(
        _photo_entry(log_id, object_key, photo_item_names)
        for log_id, object_key in photo_object_keys.items()
    )))


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


class DietPhotoUploadBody(BaseModel):
    object_key: str
    mealType: str | None = None
    mode: str | None = None
    eatenAt: str | None = None


# RC-0101~0102: 식단 사진 업로드 — object_key(POST /uploads/diet-photo가 반환한
# 값) 등록 → meal_log(PENDING) 생성 + diet.photo.requested outbox 이벤트.
# user_id는 body가 아니라 인증 JWT에서만 뽑는다.
@router.post("/upload", status_code=202)
async def upload_diet(
    body: DietPhotoUploadBody,
    db: AsyncSession = Depends(get_db),
    payload: dict = Depends(get_current_user),
) -> dict[str, object]:
    """RC-0101~0102: object_key(POST /uploads/diet-photo가 반환한 값) 등록 →
    meal_log(PENDING) 생성. 분석은 항상 zero-db Vision worker(별도 Vision AI)가
    수행한다 — outbox의 diet.photo.requested를 워커가 처리해 diet.photo.
    completed/failed를 Kafka로 발행하고 app/services/vision_consumer.py가
    구독한다. 프론트는 GET /diet/photo/{id}를 폴링한다. 회의 결정(2026-07-27):
    식사 사진 분석은 이 파이프라인만 사용한다 — 이전에 병행 존재하던
    Claude Vision 동기 경로(vision_service.py)는 제거됨.

    mode='daily'는 mealType 없을 때만 쓰는 하위호환 폴백이다.
    """
    user_id: int = payload["user_id"]

    try:
        image_object_key = validate_diet_photo_key(body.object_key, user_id)
    except StorageUploadError as e:
        raise HTTPException(status_code=403, detail=str(e))

    # 실제 DB의 meal_type CHECK 제약엔 'DAILY'가 없다(BREAKFAST/LUNCH/DINNER/
    # SNACK/OTHER만 허용) — "하루 식단" 업로드는 OTHER로 매핑한다.
    if body.mealType:
        meal_type = _normalize_meal_type(body.mealType)
    else:
        meal_type = "OTHER" if body.mode == "daily" else "SNACK"

    eaten_at = _parse_date(body.eatenAt) if body.eatenAt else None

    log = await create_meal_log(
        db,
        user_id=user_id,
        image_object_key=image_object_key,
        meal_type=meal_type,
        input_type="VISION",
        eaten_at=eaten_at,
    )
    logger.info("diet: meal_log created meal_log_id=%s user_id=%s", log.meal_log_id, user_id)
    return {"meal_log_id": str(log.meal_log_id), "status": log.analysis_status}


# 사진 분석 상태 폴링 — RecordMealModal이 여기를 반복 호출한다. 업로드 성공을
# 분석 완료로 취급하면 안 된다는 게 이 엔드포인트를 따로 둔 이유.
@router.get("/photo/{meal_log_id}")
async def get_diet_photo_status(
    meal_log_id: str,
    db: AsyncSession = Depends(get_db),
    payload: dict = Depends(get_current_user),
) -> dict[str, object]:
    user_id: int = payload["user_id"]
    log_id = _to_uuid(meal_log_id, "meal_log ID")

    try:
        log = await get_meal_log_for_user(db, log_id, user_id)
    except MealLogNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    items = (
        await get_meal_items(db, log_id)
        if log.analysis_status in ("AWAITING_CONFIRMATION", "COMPLETED")
        else []
    )
    return {
        "meal_log_id": str(log_id),
        "status": log.analysis_status,
        "needs_user_confirmation": log.needs_user_confirmation,
        "confidence": float(log.vision_confidence) if log.vision_confidence is not None else None,
        "confidence_source": log.vision_provider,
        "list-diet": [_item_dict(i) for i in items],
    }


class DietConfirmItem(BaseModel):
    name: str
    sugar: Decimal = Decimal("0")
    calories: Decimal = Decimal("0")
    carbohydrate: Decimal = Decimal("0")


class DietConfirmBody(BaseModel):
    items: list[DietConfirmItem]


# 사용자가 AWAITING_CONFIRMATION 초안을 (필요하면 수정해서) 확정한다.
@router.post("/ai-analyze/{meal_log_id}/confirm")
async def confirm_diet_analysis(
    meal_log_id: str,
    body: DietConfirmBody,
    db: AsyncSession = Depends(get_db),
    payload: dict = Depends(get_current_user),
) -> dict[str, object]:
    user_id: int = payload["user_id"]
    log_id = _to_uuid(meal_log_id, "meal_log ID")

    items = [
        make_meal_item_from_analysis(log_id, i.name, Decimal("0"), "인분", i.calories, i.sugar, i.carbohydrate)
        for i in body.items
    ]

    try:
        log = await confirm_meal_log(db, log_id, user_id, items)
    except MealLogNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except MealLogNotConfirmableError as e:
        raise HTTPException(status_code=409, detail=str(e))

    return {"status": "SUCCESS", "meal_log_id": str(log.meal_log_id), "analysisStatus": log.analysis_status}


# 개발팀 요청서 정정 1(2026-07-20) — worker는 HTTP callback을 호출하지 않는다.
# 결과는 diet.photo.completed/diet.photo.failed Kafka topic으로만 온다.
# app/services/vision_consumer.py가 전용 consumer group으로 직접 구독한다.
# (이전에 여기 있던 POST /photo/{id}/vision-callback은 실제로 호출된 적이
# 없어 삭제했다 — 개발팀 요청서 확인.)


# RC-0103: AI 식단 분석 결과 조회. 분석 자체는 여기서 하지 않는다 — 회의
# 결정(2026-07-27): 식사 사진 분석은 별도 Vision AI(zero-db worker, Kafka
# 파이프라인)만 사용한다. 이전에 여기 있던 Claude Vision 동기 호출
# (vision_service.py)은 프론트가 실제로 쓰지 않는 병행 경로였고, 분석 주체가
# 이원화되는 문제(+호출 시 Anthropic 비용 발생)로 제거했다. 진행 상태 폴링의
# 정식 경로는 GET /diet/photo/{meal_log_id}다.
@router.get("/ai-analyze")
async def ai_analyze(
    id: str = Query(..., description="meal_log UUID"),
    db: AsyncSession = Depends(get_db),
    payload: dict = Depends(get_current_user),
) -> dict[str, object]:
    user_id: int = payload["user_id"]
    log_id = _to_uuid(id, "meal_log ID")

    try:
        log = await get_meal_log_for_user(db, log_id, user_id)
    except MealLogNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    if log.analysis_status == "COMPLETED":
        items = await get_meal_items(db, log_id)
        return {
            "id": str(log_id),
            "dang": sum(float(i.sugars) for i in items if i.sugars is not None),
            "calo": sum(float(i.calories) for i in items if i.calories is not None),
            "list-diet": [_item_dict(i) for i in items],
            # 개발팀 요청서 "변경된 파이프라인 API 응답" — 이전엔 list-diet만 내려줘서
            # 프론트가 confidence 분기를 못 만들었다. 기존 필드는 안 건드려서 호환.
            "confidence": float(log.vision_confidence) if log.vision_confidence is not None else None,
            "confidence_source": log.vision_provider,
            "needs_user_confirmation": log.needs_user_confirmation,
        }

    return {
        "status": log.analysis_status,
        "message": "분석은 Vision AI 파이프라인에서 진행돼요. GET /diet/photo/{meal_log_id}로 상태를 확인하세요.",
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


async def _swap_sources_for_item(
    client: httpx.AsyncClient,
    product_service: str,
    meal_item,
    recognized_name: str,
    drop,
) -> list[dict[str, object]]:
    """스왑 비교의 기준이 될 "지금 먹은 제품"을 확보한다.

    vision 아이템의 94.7%는 이미 meal_item.product_id를 갖고 있는데도(2026-08-12
    운영 실측) 예전에는 인식된 이름으로 /search를 다시 뒤졌다. 그 경로는
    is_credible_product_match의 양방향 부분문자열 게이트와 search_items[:5]
    절단을 함께 통과해야 해서, 정작 아는 제품이 탈락하곤 했다. product_id가
    있으면 상세를 직접 읽고, 없을 때만 예전 이름 검색으로 폴백한다."""
    product_id = str(getattr(meal_item, "product_id", None) or "").strip()
    if product_id:
        detail_response = await client.get(f"{product_service}/product", params={"id": product_id})
        detail_response.raise_for_status()
        return [_source_from_product_detail(product_id, detail_response.json())]

    if not recognized_name:
        drop("item_without_product_id_and_name")
        return []

    search_response = await client.get(
        f"{product_service}/search",
        params={"query": recognized_name, "page": 1},
    )
    search_response.raise_for_status()
    search_items = search_response.json().get("items", [])
    if not search_items:
        drop("search_empty")
        return []

    matched = [
        item for item in search_items[:5]
        if is_credible_product_match(recognized_name, item.get("name"))
    ]
    if not matched:
        drop("name_match_failed")
    return matched


def _source_from_product_detail(product_id: str, detail: dict[str, object]) -> dict[str, object]:
    """/product 상세 응답을 /search 항목과 같은 모양으로 맞춘다.

    두 응답은 키가 다르다(당류 dang↔sugar, 열량 cal↔calories). 매핑을 빠뜨리면
    is_already_low_sugar가 sugar를 None으로 읽어 float(None or 0) <= 0이 참이
    되고, 모든 소스가 조용히 걸러진다 - 2026-08-12 장애와 똑같은 증상이 된다.
    응답의 current 필드는 프론트 DietSwapProduct 타입이 그대로 소비하므로
    /search 형태를 유지해야 한다(상세 응답에는 id가 없어 인자로 받는다)."""
    return {
        "id": product_id,
        "name": detail.get("name"),
        "desc": detail.get("brand") or "",
        "url": detail.get("imageUrl") or "",
        "brand": detail.get("brand"),
        "category": detail.get("category"),
        "foodType": detail.get("foodType"),
        "serving": detail.get("serving"),
        "sugar": detail.get("dang"),
        "calories": detail.get("cal"),
        "image": detail.get("imageUrl"),
        # 상세 응답의 allerg는 알레르기 태그라 저당 판정에 쓸 수 없다. 이름
        # 마커 검사와 sugar 값만으로 판정하고, 태그 기반 판정은 이어지는
        # /product/alternatives(ALREADY_LOW)가 맡는다.
        "tags": [],
    }


# RC-0105: 사진 분석 결과에 연결되는 대체 제품 추천
@router.get("/recommend-alt")
async def recommend_alt(
    id: str = Query(..., description="meal_log UUID"),
    db: AsyncSession = Depends(get_db),
    payload: dict = Depends(get_current_user),
) -> dict[str, object]:
    """사진에서 인식된 제품에만 보수적인 저당 스왑 후보를 반환한다.

    후보는 Product Service가 ``v_product_swap_pick``으로 브랜드 중복을 묶어
    제공하며, 이 경계에서 세부 식품군·비교 단위·감소폭을 다시 검증한다.
    조건을 만족하지 않으면 설명용 카드 대신 ``NO_MATCH``만 반환한다.
    """
    user_id: int = payload["user_id"]
    log_id = _to_uuid(id, "meal_log ID")

    try:
        log = await get_meal_log_for_user(db, log_id, user_id)
    except MealLogNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    if log.input_type != "VISION" or log.analysis_status != "COMPLETED":
        return {"status": "NO_MATCH", "mealLogId": str(log_id), "alternatives": []}

    meal_items = await get_meal_items(db, log_id)
    product_service = settings.product_service_url.rstrip("/")
    # 어느 단계에서 후보가 떨어졌는지 남긴다 - 예전에는 모든 실패가 똑같이
    # NO_MATCH로 접혀서, product-service가 500을 내던 2026-08-12 장애를
    # 사용자도 모니터링도 알아채지 못했다.
    drops: dict[str, int] = {}

    def drop(reason: str) -> None:
        drops[reason] = drops.get(reason, 0) + 1

    try:
        async with httpx.AsyncClient(timeout=6.0) as client:
            for meal_item in meal_items:
                recognized_name = str(meal_item.item_name or "").strip()
                sources = await _swap_sources_for_item(
                    client, product_service, meal_item, recognized_name, drop
                )

                for source in sources:
                    if is_already_low_sugar(source):
                        drop("source_already_low_sugar")
                        continue
                    if not source.get("foodType") or not serving_key(source.get("serving")):
                        drop("source_missing_food_type_or_serving")
                        continue

                    alternatives_response = await client.get(
                        f"{product_service}/product/alternatives",
                        params={"id": source.get("id")},
                    )
                    alternatives_response.raise_for_status()
                    alternatives_payload = alternatives_response.json()
                    alternatives_status = alternatives_payload.get("status")
                    if alternatives_status != "AVAILABLE":
                        # ALREADY_LOW가 비정상적으로 높으면 태깅 문제를 의심해야 한다.
                        drop(f"alternatives_{str(alternatives_status or 'UNKNOWN').lower()}")
                        continue

                    valid: list[dict[str, object]] = []
                    seen_ids: set[str] = set()
                    for candidate in alternatives_payload.get("alternatives", []):
                        candidate_id = str(candidate.get("id") or "")
                        if not candidate_id or candidate_id in seen_ids:
                            continue
                        detail_response = await client.get(
                            f"{product_service}/product",
                            params={"id": candidate_id},
                        )
                        detail_response.raise_for_status()
                        detail = detail_response.json()
                        if not is_valid_swap_candidate(source, candidate, detail):
                            drop("candidate_failed_final_check")
                            continue
                        seen_ids.add(candidate_id)
                        valid.append(
                            {
                                **candidate,
                                "category": detail.get("category"),
                                "foodType": detail.get("foodType"),
                                "serving": detail.get("serving"),
                            }
                        )

                    if valid:
                        return {
                            "status": "AVAILABLE",
                            "mealLogId": str(log_id),
                            "recognizedItem": recognized_name or str(source.get("name") or ""),
                            "current": source,
                            "alternatives": valid[:2],
                        }
    except (httpx.HTTPError, TypeError, ValueError, AttributeError):
        logger.exception("product swap lookup failed for meal_log_id=%s", log_id)
        drop("exception")

    # 정상 흐름으로 NO_MATCH가 나온 경우에도 사유별 카운터를 남긴다.
    logger.info(
        "swap NO_MATCH meal_log_id=%s items=%d drops=%s",
        log_id,
        len(meal_items),
        drops or {"no_meal_items": len(meal_items) == 0},
    )
    return {"status": "NO_MATCH", "mealLogId": str(log_id), "alternatives": []}


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
        # 프론트 삭제(RC-0115 DELETE /diet/records/{id})용 — itemId는 상품/레시피
        # 원본 참조라 삭제 대상 식별에 못 쓴다. recordId가 실제 meal_log_id.
        "recordId": str(log.meal_log_id),
        # 사진 기록 하나(meal_log 1개)에서 음식이 여러 개 인식되면 meal_item이
        # 여러 행이라 recordId(meal_log_id)가 그 행들 전부 동일하다 — 프론트가
        # 이 값을 리스트 렌더링 key/삭제 대상 식별자로 같이 쓰면 항목별로 구분이
        # 안 돼서 삭제가 엉뚱하게 동작(또는 안 먹힘)하는 문제가 있었다. entryId는
        # meal_item 고유 PK라 항상 유일하다 — 삭제 API 호출에는 여전히 recordId를 쓴다.
        "entryId": str(item.meal_item_id),
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
    payload: dict = Depends(get_current_user),
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
    payload: dict = Depends(get_current_user),
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
    payload: dict = Depends(get_current_user),
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
    payload: dict = Depends(get_current_user),
) -> dict[str, object]:
    user_id: int = payload["user_id"]

    if date:
        start = _parse_date(date)
        end = datetime.combine(start.date(), time.max, tzinfo=timezone.utc)
        rows = await get_records_for_range(db, user_id, start, end)
        sugar_total = sum(float(item.sugars) for _, item in rows if item.sugars is not None)
        calories_total = sum(float(item.calories) for _, item in rows if item.calories is not None)
        return {
            "date": start.strftime("%Y-%m-%d"),
            "sugar-total": sugar_total,
            "calories-total": calories_total,
            "list": [_record_item_dict(log, item) for log, item in rows],
        }

    if year and month:
        # PRODUCTION_HANDOFF.md P1-3 — 캘린더 집계: 날짜별 합계 + 음식 목록을 한
        # 응답에 담아서, 프론트가 날짜마다 /diet/records?date=...를 또 호출하는
        # N+1 없이 한 번에 월 전체를 그릴 수 있게 한다.
        _, last_day = calendar.monthrange(year, month)
        start = datetime(year, month, 1, tzinfo=timezone.utc)
        end = datetime(year, month, last_day, 23, 59, 59, tzinfo=timezone.utc)
        rows = await get_records_for_range(db, user_id, start, end)

        days: dict[str, list] = {}
        for log, item in rows:
            days.setdefault(log.eaten_at.strftime("%Y-%m-%d"), []).append((log, item))

        return {
            "list": [
                {
                    "date": day,
                    "sugar-total": sum(float(item.sugars) for _, item in day_rows if item.sugars is not None),
                    "calories-total": sum(float(item.calories) for _, item in day_rows if item.calories is not None),
                    "list": [_record_item_dict(log, item) for log, item in day_rows],
                }
                for day, day_rows in sorted(days.items())
            ]
        }

    raise HTTPException(status_code=422, detail="date 또는 year+month 파라미터가 필요합니다.")


# RC-0117: 업로드 취소 (확정 전 draft 상태의 사진 업로드만 삭제 가능)
@router.delete("/upload/{id}")
async def cancel_diet_upload(
    id: str,
    db: AsyncSession = Depends(get_db),
    payload: dict = Depends(get_current_user),
) -> dict[str, object]:
    user_id: int = payload["user_id"]
    log_id = _to_uuid(id, "업로드 ID")

    try:
        log = await get_meal_log_for_user(db, log_id, user_id)
    except MealLogNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    if log.analysis_status == "COMPLETED":
        raise HTTPException(status_code=409, detail="이미 확정된 기록입니다. /diet/records/{id}로 삭제해주세요.")


def _verify_internal_secret(x_internal_service_secret: str | None) -> None:
    # admin_signup_secret과 같은 이유로 빈 값이면 무조건 거부한다 — 값이
    # 비어있는데 헤더도 없는 요청을 통과시키면 "설정을 깜빡함"이 "누구나 통과"가
    # 되는 사고로 이어진다.
    if not settings.internal_service_secret or x_internal_service_secret != settings.internal_service_secret:
        raise HTTPException(status_code=403, detail="internal service 인증에 실패했습니다.")


# 얌로그(rooms) 전용 서버간 내부 엔드포인트 — community-service만 호출한다.
# 사용자 자신의 JWT로 인가되는 게 아니라 임의의 user_id 목록을 받아서 그
# 사용자들의 식단을 반환하므로, 공개 게이트웨이(infra/b-gateway/nginx.conf)에서
# /b/diet/internal은 /b/diet(/.*)? 와일드카드보다 먼저 명시적으로 차단해야
# 한다 - 그쪽 주석 참고. 여기서도 공유 시크릿으로 한 번 더 막는다(방어 계층 이중화).
@router.get("/internal/meal-records")
async def internal_meal_records(
    userIds: str = Query(..., description="콤마로 구분된 user_id 목록"),
    date: str = Query(..., description="YYYY-MM-DD (Asia/Seoul 기준 날짜)"),
    includePhotos: bool = Query(True, description="false면 업로드 사진 서명 URL을 만들지도, 내려주지도 않는다"),
    db: AsyncSession = Depends(get_db),
    x_internal_service_secret: str | None = Header(None),
) -> dict[str, object]:
    _verify_internal_secret(x_internal_service_secret)

    try:
        user_ids = [int(part) for part in userIds.split(",") if part.strip()]
    except ValueError:
        raise HTTPException(status_code=422, detail="userIds는 콤마로 구분된 정수여야 합니다.")
    if not user_ids:
        raise HTTPException(status_code=422, detail="userIds가 비어 있습니다.")

    try:
        day = date_cls.fromisoformat(date[:10])
    except ValueError:
        raise HTTPException(status_code=422, detail="date 형식이 올바르지 않습니다 (YYYY-MM-DD).")

    start_kst = datetime.combine(day, time.min, tzinfo=_KST)
    end_kst = datetime.combine(day, time.max, tzinfo=_KST)
    rows = await get_records_for_users_on_date(db, user_ids, start_kst.astimezone(timezone.utc), end_kst.astimezone(timezone.utc))

    # (user_id, meal_type) 별로 여러 meal_log(사진/레시피/저당픽이 각각 별도
    # 행일 수 있음, 얌로그 문서 §2 참고)를 하나로 묶는다.
    groups: dict[tuple[int, str], list[tuple]] = {}
    for log, item in rows:
        groups.setdefault((log.user_id, log.meal_type), []).append((log, item))

    product_ids = [item.product_id for _, item in rows if item.product_id is not None]
    recipe_ids = [int(item.external_recipe_id) for _, item in rows if item.external_recipe_id is not None]
    products = await get_product_refs_bulk(db, product_ids)
    recipes = await get_recipe_refs_bulk(db, recipe_ids)

    records = []
    for (user_id, meal_type), group_rows in groups.items():
        # meal_log_id -> object_key, 처음 본 순서 유지(dict는 삽입 순서 보존).
        photo_object_keys: dict[uuid.UUID, str] = {}
        # 같은 사진(meal_log)에 딸린 비전 인식 음식 이름들 - 레시피/저당픽으로
        # 연결 안 된 항목(item.product_id도 external_recipe_id도 없음)은
        # Vision이 그 사진에서 직접 인식한 음식이라는 뜻이다.
        photo_item_names: dict[uuid.UUID, list[str]] = {}
        recipe_items: list[dict[str, object]] = []
        product_items: list[dict[str, object]] = []
        sugar_total = 0.0
        calories_total = 0.0

        for log, item in group_rows:
            if log.image_object_key and log.meal_log_id not in photo_object_keys:
                photo_object_keys[log.meal_log_id] = log.image_object_key

            sugar_total += float(item.sugars) if item.sugars is not None else 0.0
            calories_total += float(item.calories) if item.calories is not None else 0.0

            if item.product_id is not None:
                product = products.get(item.product_id)
                product_items.append({
                    "source": "product",
                    "id": str(item.product_id),
                    "name": product.product_name if product else item.item_name,
                    "imageUrl": product.image_url if product else None,
                })
            elif item.external_recipe_id is not None:
                recipe = recipes.get(int(item.external_recipe_id))
                recipe_items.append({
                    "source": "recipe",
                    "id": item.external_recipe_id,
                    "name": recipe.name if recipe else item.item_name,
                    "imageUrl": _recipe_thumbnail_url(recipe) if recipe else None,
                })
            elif log.meal_log_id in photo_object_keys and item.item_name:
                photo_item_names.setdefault(log.meal_log_id, []).append(item.item_name)

        # 얌로그 요청사항 - 비전(사진) → 레시피 → 저당픽 순으로 넘겨볼 수 있게
        # 하나의 정렬된 리스트로도 내려준다. photoUrls/connectedItems는 기존
        # 소비자(다른 화면)와의 호환을 위해 그대로 둔다.
        connected_items = recipe_items + product_items
        # 사진 넘겨보기 캐러셀이 사진마다 맞는 이름을 보여줄 수 있게, 사진
        # 하나하나에 그 사진에서 인식된 음식 이름을 같이 실어 보낸다(이전엔
        # imageUrl만 있어서 프론트가 전부 같은 이름 하나로만 보여줬다).
        photo_entries = await _resolve_photo_entries(photo_object_keys, photo_item_names, includePhotos)
        photo_urls = [entry["imageUrl"] for entry in photo_entries]
        ordered_photos: list[dict[str, object]] = (
            [{"source": "photo", "imageUrl": entry["imageUrl"], "name": entry["name"]} for entry in photo_entries]
            + [
                {"source": item["source"], "imageUrl": item["imageUrl"], "name": item["name"]}
                for item in connected_items if item.get("imageUrl")
            ]
        )

        records.append({
            "userId": user_id,
            "mealType": meal_type,
            "sugar": sugar_total,
            "calories": calories_total,
            # 만료 5분짜리 서명 URL - 캐시하지 말고 매 조회마다 새로 받아써야 한다.
            "photoUrls": photo_urls,
            "connectedItems": connected_items,
            "orderedPhotos": ordered_photos,
        })

    return {"date": day.isoformat(), "records": records}

    await delete_meal_log(db, log)
    return {"status": "SUCCESS"}
