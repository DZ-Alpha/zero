-- kafka/migrations/006_queue_and_reviews.sql
-- 아직 백엔드 구현이 없는 두 기능의 "착지점"을 DB 쪽에 먼저 만들어 둔다.
-- 테이블이 있으면 백엔드는 INSERT/SELECT 만 붙이면 된다.
--
-- 1) service.search_miss_queue
--    검색 결과 0건인 검색어를 모아 "사용자가 찾았는데 우리에게 없는 상품" 목록을
--    만든다. product-service 의 /search 는 이미 results 개수를 로그로 찍고 있고
--    (search.py), user.activity.raw.v1 계약과 Mongo 소비자도 이미 있다.
--    빠진 것은 생산자(Kafka 발행)뿐이다. 그게 붙으면 야간 배치가 이 테이블을 채운다.
--    이 큐가 곧 상품 수집·정규화의 우선순위가 된다.
--
-- 2) product.product_reviews / product_review_sentiment
--    PR-0306 은 스키마 자체가 없어 미구현으로 남아 있었다.
--    service 스키마(데이터팀 소유)를 건드리지 않고 product 스키마에 둔다 —
--    product.product_favorites / product.product_ai_summaries 와 같은 패턴.
--
--    is_seed: 데모·시연용으로 넣은 행을 실제 사용자 리뷰와 구분한다.
--    운영 노출 시 is_seed=true 를 걸러내거나 "예시" 라벨을 붙일 수 있어야 한다.
--    감정분석 결과는 원문과 수명주기가 다르므로(모델 교체 시 재계산) 분리한다.

CREATE TABLE IF NOT EXISTS service.search_miss_queue (
    query_norm          TEXT        PRIMARY KEY,
    miss_count          INTEGER     NOT NULL DEFAULT 0,
    first_seen_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    status              TEXT        NOT NULL DEFAULT 'OPEN',
    resolved_product_id UUID,
    note                TEXT,
    CONSTRAINT ck_miss_status CHECK (status IN ('OPEN','SOURCING','ADDED','REJECTED'))
);

CREATE INDEX IF NOT EXISTS idx_search_miss_open
    ON service.search_miss_queue (miss_count DESC)
    WHERE status = 'OPEN';

COMMENT ON TABLE service.search_miss_queue IS
    '검색 결과 0건 검색어 집계. 수집/정규화 우선순위 큐. 생산자는 product-service 검색 이벤트 발행(미구현).';

CREATE TABLE IF NOT EXISTS product.product_reviews (
    review_id  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    product_id UUID        NOT NULL,
    user_id    INTEGER     NOT NULL,
    rating     SMALLINT    NOT NULL,
    content    TEXT        NOT NULL,
    is_seed    BOOLEAN     NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_review_rating  CHECK (rating BETWEEN 1 AND 5),
    CONSTRAINT ck_review_content CHECK (length(btrim(content)) >= 5),
    CONSTRAINT uq_review_user_product UNIQUE (product_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_reviews_product
    ON product.product_reviews (product_id, created_at DESC);

COMMENT ON COLUMN product.product_reviews.is_seed IS
    '데모/시연용으로 넣은 행. 실사용자에게 노출할 때는 걸러내거나 "예시"로 표기해야 한다.';

CREATE TABLE IF NOT EXISTS product.product_review_sentiment (
    product_id     UUID        PRIMARY KEY,
    review_count   INTEGER     NOT NULL,
    positive_count INTEGER     NOT NULL DEFAULT 0,
    neutral_count  INTEGER     NOT NULL DEFAULT 0,
    negative_count INTEGER     NOT NULL DEFAULT 0,
    summary        TEXT,
    model_id       TEXT,
    includes_seed  BOOLEAN     NOT NULL DEFAULT false,
    computed_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_sentiment_counts
        CHECK (positive_count + neutral_count + negative_count <= review_count)
);

COMMENT ON COLUMN product.product_review_sentiment.includes_seed IS
    '집계에 is_seed 리뷰가 포함됐는지. true 면 화면에서 실제 사용자 의견처럼 보여서는 안 된다.';
