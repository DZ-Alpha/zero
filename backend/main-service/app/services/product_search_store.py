from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product_display import ProductDisplay


async def search_products_in_db(db: AsyncSession, keyword: str) -> list[dict]:
    # 상품명 부분검색. 데이터팀 ElasticSearch 색인 연동 전까지 products 테이블 조회로 대체.
    # 사용자 입력(keyword)은 ORM 파라미터 바인딩(ilike)으로만 전달 — 값으로만 취급되어
    # SQL 구조에 끼어들 수 없다(SQL Injection 불가). 응답 키는 프론트 계약(id/name/desc/url).
    stmt = (
        select(
            ProductDisplay.product_id,
            ProductDisplay.display_name,
            ProductDisplay.brand_name,
            ProductDisplay.image_url,
        )
        .where(
            ProductDisplay.display_name.ilike(f"%{keyword}%")
            | ProductDisplay.brand_name.ilike(f"%{keyword}%")
        )
        .limit(20)
    )
    rows = await db.execute(stmt)
    return [
        {
            "id": str(row.product_id),
            "name": row.display_name,
            "desc": row.brand_name,
            "url": row.image_url,
        }
        for row in rows
    ]
