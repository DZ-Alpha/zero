-- kafka/migrations/011_product_display_views.sql
--
-- 003~010과 별개로 데이터 정제 작업에서 먼저 만들어졌던 상품 표시 뷰를
-- 버전 관리한다. 운영의 실제 정의를 그대로 옮겼으며, 스테이징처럼
-- curation 스키마가 없는 DB에서도 재현할 수 있도록 빈 감사 테이블만 만든다.
-- removed_products에 상품 원본을 넣는 정제 작업 자체는 이 파일의 책임이 아니다.

CREATE SCHEMA IF NOT EXISTS curation;

CREATE TABLE IF NOT EXISTS curation.removed_products (
    product_id  UUID PRIMARY KEY,
    product_row JSONB NOT NULL,
    tag_rows    JSONB NOT NULL DEFAULT '[]'::jsonb,
    reason      TEXT NOT NULL,
    removed_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    removed_by  TEXT NOT NULL DEFAULT 'data-audit-20260809'
);

CREATE OR REPLACE VIEW service.v_product_display AS
SELECT
    product_id,
    CASE
        WHEN brand_name IS NULL OR btrim(brand_name) = '' THEN product_name
        WHEN POSITION(btrim(brand_name) IN product_name) > 0 THEN product_name
        ELSE btrim(brand_name) || ' ' || product_name
    END AS display_name,
    product_name,
    brand_name,
    report_no,
    food_type,
    sugars,
    calories,
    image_url,
    brand_name IS NOT NULL
        AND btrim(brand_name) <> ''
        AND POSITION(btrim(brand_name) IN product_name) = 0 AS brand_prefixed,
    serving_value,
    serving_unit
FROM service.products p
WHERE NOT EXISTS (
    SELECT 1
    FROM curation.removed_products r
    WHERE r.product_id = p.product_id
);

CREATE OR REPLACE VIEW service.v_product_swap_pick AS
SELECT DISTINCT ON (report_no)
    product_id,
    display_name,
    product_name,
    brand_name,
    report_no,
    food_type,
    sugars,
    calories,
    image_url,
    count(*) OVER (PARTITION BY report_no) AS variant_count,
    array_agg(brand_name) FILTER (WHERE brand_name IS NOT NULL)
        OVER (PARTITION BY report_no) AS variant_brands,
    serving_value,
    serving_unit
FROM service.v_product_display d
ORDER BY report_no, (brand_name IS NULL), length(product_name), brand_name;
