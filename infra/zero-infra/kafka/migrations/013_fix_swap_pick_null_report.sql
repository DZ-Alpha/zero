-- v_product_swap_pick의 중복 키 보정과 비교 단위 필드 공개.
--
-- 011의 DISTINCT ON (report_no)는 report_no가 NULL인 모든 상품을 하나의
-- 그룹으로 취급한다. 신고번호가 없는 상품끼리는 동일 상품의 변형이라고 볼
-- 근거가 없으므로 product_id를 개별 키로 사용한다. 대안 API가 동일
-- food_type·serving_value·serving_unit을 DB 조회 단계에서도 검증할 수 있도록
-- 표시 뷰 두 개에 제공량 필드를 포함한다.

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
WITH keyed AS (
    SELECT
        d.*,
        CASE
            WHEN report_no IS NULL OR btrim(report_no) = ''
                THEN 'product:' || product_id::text
            ELSE 'report:' || report_no
        END AS variant_key
    FROM service.v_product_display d
)
SELECT DISTINCT ON (variant_key)
    product_id,
    display_name,
    product_name,
    brand_name,
    report_no,
    food_type,
    sugars,
    calories,
    image_url,
    count(*) OVER (PARTITION BY variant_key) AS variant_count,
    array_agg(brand_name) FILTER (WHERE brand_name IS NOT NULL)
        OVER (PARTITION BY variant_key) AS variant_brands,
    serving_value,
    serving_unit
FROM keyed
ORDER BY variant_key, (brand_name IS NULL), length(product_name), brand_name;
