-- kafka/migrations/003_swap_indexes.sql
-- 저당 대안(Swap) 축을 위한 인덱스 3종.
--
-- 배경(2026-08-09 실측):
--   1) sort=sugar_asc 를 지원하려면 sugars 정렬이 필요한데 인덱스가 없어 2,438건
--      전체 Seq Scan + Sort 가 된다.
--   2) product_tags PK 가 (product_id, tag_id) 라서 "이 카테고리에 속한 상품"
--      역방향 조회(tag_id 단독)에 인덱스가 없다. 카테고리 필터·대안 후보 추출의
--      기본 경로다.
--   3) 레시피 당 감소율 랭킹(v_recipe_swap_ranking)은 sugar_reduction_pct DESC
--      정렬이 핵심이다. NULL 은 랭킹에서 제외하므로 부분 인덱스로 둔다.
--
-- CREATE INDEX CONCURRENTLY 는 트랜잭션 블록 안에서 실행할 수 없다.
-- psql -f 로 단독 실행할 것(002 와 동일).

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_products_sugars
    ON service.products (sugars);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_product_tags_tag
    ON service.product_tags (tag_id);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_recipes_reduction
    ON service.recipes (sugar_reduction_pct DESC)
    WHERE sugar_reduction_pct IS NOT NULL;

ANALYZE service.products;
ANALYZE service.product_tags;
ANALYZE service.recipes;
