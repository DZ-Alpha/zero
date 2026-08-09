-- kafka/migrations/007_columns_recipes_products.sql
-- service 스키마(데이터팀 소유)에 컬럼을 추가한다. 전부 nullable 이라
-- PostgreSQL 11+ 에서 테이블 재작성 없이 즉시 끝난다(기본값 없는 ADD COLUMN).
-- 기존 행/제약/트리거에 영향이 없다.
--
-- 1) recipes.category / cook_time_min
--    PRODUCTION_HANDOFF.md P1-2 에서 "명세엔 있는데 service.recipes 에 컬럼이
--    없어서 카드에 못 채운다"고 남아 있던 항목이다. 컬럼만 만들어두면 크롤러가
--    수집 항목을 늘릴 때 바로 채울 수 있다. 기존 1,722건은 NULL 로 남는다
--    (백필은 별도 배치 — 지금 값을 지어내지 않는다).
--
-- 2) products.source / last_verified_at
--    2026-07-16 재설계에서 created_at/updated_at 이 삭제되면서 "이 값이 언제
--    확인된 것인가"를 알 수 없게 됐다(그래서 최신순 정렬을 이름순으로 대체했다).
--    소스가 여러 개(식약처/제조사/크롤링/AI 추정)로 늘어날 예정이라 출처 구분이
--    필요하다 — product_tags.evidence_source 가 태그 단위로 하던 것을 상품
--    본체로 넓히는 것이다. 건강 데이터에서 "이 숫자 어디서 왔나"에 답할 수 있어야 한다.

ALTER TABLE service.recipes
    ADD COLUMN IF NOT EXISTS category      TEXT,
    ADD COLUMN IF NOT EXISTS cook_time_min SMALLINT;

COMMENT ON COLUMN service.recipes.category IS
    '레시피 분류. 기능명세 RC-0107 카드 필드. 크롤러가 채운다(2026-08-09 기준 전량 NULL).';
COMMENT ON COLUMN service.recipes.cook_time_min IS
    '조리시간(분). 기능명세 RC-0107 카드 필드. 크롤러가 채운다(2026-08-09 기준 전량 NULL).';

ALTER TABLE service.products
    ADD COLUMN IF NOT EXISTS source           TEXT,
    ADD COLUMN IF NOT EXISTS last_verified_at TIMESTAMPTZ;

COMMENT ON COLUMN service.products.source IS
    '영양·표기 값의 출처. 예: MFDS(식약처 공표), MAKER(제조사 표기), CRAWL, AI_ESTIMATE. NULL 은 미확인.';
COMMENT ON COLUMN service.products.last_verified_at IS
    '출처와 대조해 마지막으로 확인한 시각. created_at/updated_at 삭제(2026-07-16)로 잃은 신선도 추적을 대신한다.';
