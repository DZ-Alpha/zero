-- 상품명/브랜드 검색의 오타·유사 문자열 매칭용 확장 및 pg_trgm 인덱스.
--
-- 이미 운영 중인 DB에 적용하는 마이그레이션이다. CREATE INDEX CONCURRENTLY는
-- 트랜잭션 블록 안에서 실행할 수 없으므로 psql -f로 단독 실행해야 한다.
-- 새 DB는 config/postgresql/init/01-create-extension.sql에서 확장을 함께 만든다.

CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS fuzzystrmatch;

CREATE INDEX CONCURRENTLY IF NOT EXISTS products_product_name_trgm_idx
    ON service.products USING gin (product_name gin_trgm_ops);

CREATE INDEX CONCURRENTLY IF NOT EXISTS products_brand_name_trgm_idx
    ON service.products USING gin (brand_name gin_trgm_ops)
    WHERE brand_name IS NOT NULL;

ANALYZE service.products;
