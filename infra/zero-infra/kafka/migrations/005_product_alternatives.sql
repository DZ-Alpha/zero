-- kafka/migrations/005_product_alternatives.sql
-- 상품 -> 상품 저당 대안 테이블. SwapCard 의 상품/사진/기록 문맥 입력을 담당한다.
--
-- 설계 원칙은 service.recipe_ingredient_products 와 동일하다:
--   "배치가 미리 채우고, API 는 읽기만 한다."
-- product-service 가 요청 시점에 벡터 유사도를 계산하지 않는다.
--
-- 재료(2026-08-09 실측):
--   - service.product_embeddings 2,438건 = products 100% 커버, vector(1024),
--     HNSW cosine 인덱스 존재
--   - 상품당 CATEGORY 태그가 정확히 1개 (DEFERRABLE 트리거가 보장)
--
-- 후보 규칙:
--   1. 같은 CATEGORY 안에서만 찾는다(음료의 대안은 음료여야 한다)
--   2. 당류가 실제로 더 낮아야 한다
--   3. 노이즈 컷 — 최소 0.5g 이상 낮고, 그러면서 20% 이상 줄거나 2g 이상 줄어야 한다.
--      미세한 차이를 "대안"이라고 우기면 신뢰만 깎인다.
--   4. 상품당 상위 5개까지만 저장
--
-- 당류가 이미 0g 인 상품은 대안이 생기지 않는다 — 의도된 동작이다.
-- 그런 상품에는 카드 대신 "이미 저당 기준을 만족" 배지를 띄우면 된다.

CREATE TABLE IF NOT EXISTS product.product_alternatives (
    product_id      UUID        NOT NULL,
    alt_product_id  UUID        NOT NULL,
    rank            SMALLINT    NOT NULL,
    similarity      NUMERIC(6,4) NOT NULL,
    sugar_delta_g   NUMERIC(10,2) NOT NULL,
    sugar_delta_pct NUMERIC(6,2),
    kcal_delta      NUMERIC(10,2),
    computed_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (product_id, alt_product_id),
    CONSTRAINT ck_alt_not_self CHECK (product_id <> alt_product_id),
    CONSTRAINT ck_alt_improves CHECK (sugar_delta_g < 0)
);

CREATE INDEX IF NOT EXISTS idx_prod_alt_lookup
    ON product.product_alternatives (product_id, rank);

COMMENT ON TABLE product.product_alternatives IS
    'SwapCard 용 상품->상품 저당 대안. 배치가 채우고 API 는 읽기만 한다. 채우는 SQL 은 kafka/migrations/005 참조.';
COMMENT ON COLUMN product.product_alternatives.sugar_delta_g IS
    '음수 = 당류가 줄어드는 양(g). CHECK 로 항상 음수임을 강제한다.';
COMMENT ON COLUMN product.product_alternatives.similarity IS
    'pgvector 코사인 유사도(1 - distance). product_embeddings 기준.';
