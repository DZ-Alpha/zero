from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product


async def search_products_in_db(db: AsyncSession, keyword: str) -> list[dict]:
    # 상품명 부분검색. 데이터팀 ElasticSearch 색인 연동 전까지 products 테이블 조회로 대체.
    # 사용자 입력(keyword)은 ORM 파라미터 바인딩(ilike)으로만 전달 — 값으로만 취급되어
    # SQL 구조에 끼어들 수 없다(SQL Injection 불가). 응답 키는 프론트 계약(id/name/desc/url).
    stmt = (
        select(
            Product.product_id,
            Product.product_name,
            Product.brand_name,
            Product.image_url,
        )
        .where(Product.product_name.ilike(f"%{keyword}%"))
        .limit(20)
    )
    rows = await db.execute(stmt)
    return [
        {
            "id": str(row.product_id),
            "name": row.product_name,
            "desc": row.brand_name,
            "url": row.image_url,
        }
        for row in rows
    ]
