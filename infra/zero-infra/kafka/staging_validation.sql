-- staging_validation.sql
-- 개인정보 없는 스테이징 검증 조회. 운영 DB에서 실행하지 않는다.

SELECT 'v_product_display' AS object_name, count(*) AS row_count
FROM service.v_product_display
UNION ALL
SELECT 'v_product_swap_pick', count(*) FROM service.v_product_swap_pick
UNION ALL
SELECT 'v_recipe_swap_ranking', count(*) FROM service.v_recipe_swap_ranking
UNION ALL
SELECT 'product.product_alternatives', count(*) FROM product.product_alternatives
UNION ALL
SELECT 'service.mv_category_sugar_stats', count(*) FROM service.mv_category_sugar_stats
UNION ALL
SELECT 'service.mv_sweetener_catalog', count(*) FROM service.mv_sweetener_catalog
UNION ALL
SELECT 'public collections', count(*) FROM content.collections WHERE is_published
UNION ALL
SELECT 'articles with body and published', count(*)
FROM content.articles WHERE is_published AND body_md IS NOT NULL;

SELECT product_id, display_name, brand_name, sugars, variant_count, variant_brands
FROM service.v_product_swap_pick
WHERE variant_count > 1
ORDER BY report_no, product_id
LIMIT 5;

SELECT product_id, alt_product_id, rank, similarity, sugar_delta_g
FROM product.product_alternatives
ORDER BY product_id, rank
LIMIT 3;

-- 반드시 0이어야 한다: 사진/상품 스왑의 비교 세부군·수량·단위 불일치.
SELECT count(*) AS invalid_swap_unit_or_food_type_count
FROM product.product_alternatives a
JOIN service.products base ON base.product_id = a.product_id
JOIN service.products alt  ON alt.product_id = a.alt_product_id
WHERE base.food_type IS DISTINCT FROM alt.food_type
   OR base.serving_value IS DISTINCT FROM alt.serving_value
   OR lower(btrim(base.serving_unit)) IS DISTINCT FROM lower(btrim(alt.serving_unit));

-- 반드시 0이어야 한다: 이미 저당·제로로 분류된 원본에 만들어진 대안.
SELECT count(*) AS already_low_source_with_alternative_count
FROM product.product_alternatives a
JOIN service.products base ON base.product_id = a.product_id
WHERE base.product_name ~* '(저당|제로|무가당|무설탕|sugar[ -]?free)'
   OR EXISTS (
       SELECT 1
       FROM service.product_tags pt
       JOIN service.tags t ON t.tag_id = pt.tag_id
       WHERE pt.product_id = base.product_id
         AND t.tag_type = 'HEALTH_LABEL'
         AND t.tag_code IN ('SUGAR_FREE', 'ZERO_SUGAR', 'LOW_SUGAR', 'ZERO_GENERAL')
   );

-- report_no가 없는 상품도 각각 한 행씩 보존되어야 한다.
SELECT
    (SELECT count(*) FROM service.v_product_display WHERE report_no IS NULL OR btrim(report_no) = '') AS display_null_report_count,
    (SELECT count(*) FROM service.v_product_swap_pick WHERE report_no IS NULL OR btrim(report_no) = '') AS swap_pick_null_report_count;

-- 운영 앱 계정 권한. 모든 값이 true여야 한다.
SELECT object_name, has_table_privilege('yesman', object_name, 'SELECT') AS can_select
FROM (VALUES
    ('service.v_product_display'),
    ('service.v_product_swap_pick'),
    ('service.v_recipe_swap_ranking'),
    ('service.mv_category_sugar_stats'),
    ('product.product_alternatives'),
    ('content.articles')
) AS required_objects(object_name);

SELECT p.product_id, p.display_name, p.sugars
FROM service.v_product_display p
WHERE p.sugars = 0
  AND NOT EXISTS (
      SELECT 1 FROM product.product_alternatives a
      WHERE a.product_id = p.product_id
  )
ORDER BY p.product_id
LIMIT 3;

SELECT count(*) AS seed_review_count
FROM product.product_reviews
WHERE is_seed;

SELECT product_id, review_count, includes_seed
FROM product.product_review_sentiment
WHERE includes_seed;

SELECT ml.meal_log_id, ml.user_id, mi.product_id, mi.item_name
FROM service.meal_logs ml
JOIN service.meal_items mi ON mi.meal_log_id = ml.meal_log_id
WHERE ml.meal_log_id = '00000000-0000-0000-0000-00000000e301'::uuid;

SELECT preference_id, user_id, preference_type, tag_id
FROM service.user_preferences
WHERE preference_id = '00000000-0000-0000-0000-00000000e303'::uuid;
