from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.product_search_store import search_products_in_db

router = APIRouter()


@router.get("/search")
async def search_products(
    query: str,
    page: int = 1,
    category: str | None = None,
    warning: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    # 상품명 부분검색. 데이터팀 ES 연동 전까지 products 테이블을 직접 조회한다.
    # 요청 파라미터/응답 스키마(items의 id/name/desc/url)는 기능명세서 API-Spec(MN-0102)과 맞춰뒀다.
    # (DAST 게이트 재검증: 이 서비스를 빌드 대상에 포함시키기 위한 트리거 주석)
    items = await search_products_in_db(db, query)
    return {"items": items, "page": page}
