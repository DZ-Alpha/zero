from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def search_products_in_db(db: AsyncSession, keyword: str) -> list[dict]:
    # 데이터팀 ElasticSearch 색인 연동 전까지 products 테이블 LIKE 부분검색으로 대체.
    # 컬럼 별칭을 프론트 계약(id/name/desc/url)에 맞춰 내려준다.
    sql = (
        "SELECT product_id::text AS id, product_name AS name, "
        "brand_name AS desc, image_url AS url "
        "FROM service.products "
        f"WHERE product_name LIKE '%{keyword}%' "
        "LIMIT 20"
    )
    rows = await db.execute(text(sql))
    return [dict(row._mapping) for row in rows]
