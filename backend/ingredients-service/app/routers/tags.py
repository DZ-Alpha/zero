import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.tag_store import TagNotFoundError, get_tag, get_tag_with_product_count, list_tags_by_type

logger = logging.getLogger("ingredients_service.tags")

router = APIRouter()

_VALID_TAG_TYPES = {"CATEGORY", "ALLERGEN", "SWEETENER", "HEALTH_LABEL"}


def _to_uuid(value: str, label: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"유효하지 않은 {label} UUID 형식입니다.")


def _tag_summary(tag) -> dict:
    return {
        "id": str(tag.tag_id),
        "name": tag.tag_name,
        "code": tag.tag_code,
    }


def _tag_detail(tag) -> dict:
    return {
        "id": str(tag.tag_id),
        "name": tag.tag_name,
        "code": tag.tag_code,
        "desc": tag.description,
        "caution": tag.caution_text,
        "url": tag.source_url,
    }


# CM-0107: 감미료 목록 (/community/gam-list)
@router.get("/community/gam-list")
async def sweetener_list(db: AsyncSession = Depends(get_db)) -> dict[str, object]:
    """CM-0107: 감미료(SWEETENER) 태그 목록."""
    tags = await list_tags_by_type(db, "SWEETENER", active_only=True)
    return {
        "list-gam": [
            {"id": str(t.tag_id), "list": [{"name": t.tag_name}]}
            for t in tags
        ]
    }


# CM-0108: 감미료 상세
@router.get("/community/gam-detail")
async def sweetener_detail(
    id: str = Query(..., description="감미료 태그 UUID"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    """CM-0108: 감미료 상세 (설명, 주의사항, 출처)."""
    tid = _to_uuid(id, "태그 ID")
    try:
        tag = await get_tag(db, tid)
    except TagNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    if tag.tag_type != "SWEETENER":
        raise HTTPException(status_code=404, detail="해당 ID는 감미료 태그가 아닙니다.")

    return {
        "list-gam": [
            {
                "id": str(tag.tag_id),
                "list": [
                    {"name": tag.tag_name, "desc": tag.description}
                ],
            }
        ]
    }


# PR-0104: 알레르기/주의 성분 필터 목록 (Product Service가 필터 UI 구성에 사용)
@router.get("/tags/allergen")
async def allergen_list(db: AsyncSession = Depends(get_db)) -> dict[str, object]:
    """PR-0104: 알레르기(ALLERGEN) 태그 목록 — Product Service 검색 필터 UI용."""
    tags = await list_tags_by_type(db, "ALLERGEN", active_only=True)
    return {
        "list": [
            {
                **_tag_summary(t),
                "desc": t.description,
                "caution": t.caution_text,
                "url": t.source_url,
            }
            for t in tags
        ]
    }


# 카테고리 목록 (내부 편의 용도 — Product Service 검색 필터 카테고리)
@router.get("/tags/category")
async def category_list(db: AsyncSession = Depends(get_db)) -> dict[str, object]:
    """카테고리(CATEGORY) 태그 목록."""
    tags = await list_tags_by_type(db, "CATEGORY", active_only=True)
    return {"list": [_tag_summary(t) for t in tags]}


@router.get("/tags/health-label")
async def health_label_list(db: AsyncSession = Depends(get_db)) -> dict[str, object]:
    """User preference choices backed by active HEALTH_LABEL tags."""
    tags = await list_tags_by_type(db, "HEALTH_LABEL", active_only=True)
    return {
        "list": [
            {
                **_tag_summary(tag),
                "desc": tag.description,
                "caution": tag.caution_text,
                "url": tag.source_url,
            }
            for tag in tags
        ]
    }


# 관리자용: 태그 상세 (product_count 포함)
@router.get("/tags/detail")
async def tag_detail_admin(
    id: str = Query(..., description="태그 UUID"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    """관리자 화면용 태그 상세 (연결 상품 수 포함)."""
    tid = _to_uuid(id, "태그 ID")
    try:
        return await get_tag_with_product_count(db, tid)
    except TagNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
