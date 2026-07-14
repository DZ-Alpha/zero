from pydantic import BaseModel, Field
from fastapi import APIRouter

router = APIRouter(prefix="/api")


class Item(BaseModel):
    id: str
    title: str
    summary: str
    created_at: str = Field(serialization_alias="createdAt")


_ITEMS: list[Item] = [
    Item(id="item-1", title="오늘의 인기 게시물", summary="Backend에서 내려주는 더미 아이템입니다.", created_at="2026-07-12T00:00:00Z"),
    Item(id="item-2", title="새로 올라온 이슈", summary="Backend에서 내려주는 더미 아이템입니다.", created_at="2026-07-11T00:00:00Z"),
    Item(id="item-3", title="주간 트렌드 리포트", summary="Backend에서 내려주는 더미 아이템입니다.", created_at="2026-07-10T00:00:00Z"),
    Item(id="item-4", title="추천 콘텐츠", summary="Backend에서 내려주는 더미 아이템입니다.", created_at="2026-07-09T00:00:00Z"),
    Item(id="item-5", title="실시간 급상승 키워드", summary="Backend에서 내려주는 더미 아이템입니다.", created_at="2026-07-08T00:00:00Z"),
    Item(id="item-6", title="이번 주 하이라이트", summary="Backend에서 내려주는 더미 아이템입니다.", created_at="2026-07-07T00:00:00Z"),
]


@router.get("/items")
def list_items() -> list[Item]:
    return _ITEMS
