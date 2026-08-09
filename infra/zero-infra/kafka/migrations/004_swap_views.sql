-- kafka/migrations/004_swap_views.sql
-- 이미 DB에 있는데 화면에서 안 쓰이던 값들을 조회 가능한 형태로 노출한다.
-- 새 데이터를 만들지 않는다 — 전부 기존 컬럼의 재구성이다.
--
-- 1) v_recipe_swap_ranking
--    service.recipes 1,722건 전부 comparison_status='ready' 이고
--    sugar_reduction_pct 가 채워져 있는데(2026-08-09 실측) 어떤 화면도 이 값으로
--    정렬하지 않았다. /home/rank/item 의 PREPARING 을 이 뷰로 해소할 수 있다.
--
-- 2) mv_category_sugar_stats
--    "이 제품 3.2g, 음료 평균 1.6g" 같은 비교 근거용. 상품 갱신 빈도가 낮아
--    매번 집계하지 않고 매터리얼라이즈로 둔다. REFRESH 는 상품 적재 배치 뒤에 건다.
--
-- 3) mv_sweetener_catalog
--    감미료 20종 × 실제 사용 상품 수. 탐색축(필터)과 감미료 사전 콘텐츠의 원본.
--    description/caution_text/source_url 은 008 에서 채운다.
--
-- 4) v_swap_coverage
--    대체 추천이 몇 %의 레시피/상품을 커버하는지 추적. 2026-08-09 기준 레시피
--    1,722건 중 359건(20.8%)만 커버돼 있어 이 수치를 계속 봐야 한다.
--
-- 전부 CREATE OR REPLACE / IF NOT EXISTS 라 재실행 안전.

CREATE OR REPLACE VIEW service.v_recipe_swap_ranking AS
SELECT
    r.id,
    r.name,
    r.thumbnail_url,
    r.source,
    r.base_sugar_g,
    r.total_sugar_g,
    (r.base_sugar_g - r.total_sugar_g) AS sugar_saved_g,
    r.sugar_reduction_pct,
    r.total_kcal,
    r.base_kcal,
    r.kcal_reduction_pct,
    rank() OVER (ORDER BY r.sugar_reduction_pct DESC, r.base_sugar_g DESC NULLS LAST) AS rnk
FROM service.recipes r
WHERE r.sugar_reduction_pct IS NOT NULL
  AND r.comparison_status = 'ready';

DROP MATERIALIZED VIEW IF EXISTS service.mv_category_sugar_stats;
CREATE MATERIALIZED VIEW service.mv_category_sugar_stats AS
SELECT
    t.tag_id,
    t.tag_code,
    t.tag_name,
    count(*)                                                        AS product_count,
    round(avg(p.sugars), 2)                                         AS avg_sugar,
    percentile_cont(0.5) WITHIN GROUP (ORDER BY p.sugars)::numeric(10,2) AS median_sugar,
    min(p.sugars)                                                   AS min_sugar,
    max(p.sugars)                                                   AS max_sugar,
    count(*) FILTER (WHERE p.sugars = 0)                            AS zero_sugar_count,
    round(avg(p.calories), 1)                                       AS avg_calories
FROM service.products p
JOIN service.product_tags pt ON pt.product_id = p.product_id
JOIN service.tags t ON t.tag_id = pt.tag_id AND t.tag_type = 'CATEGORY'
GROUP BY t.tag_id, t.tag_code, t.tag_name;

CREATE UNIQUE INDEX IF NOT EXISTS mv_category_sugar_stats_code_idx
    ON service.mv_category_sugar_stats (tag_code);

DROP MATERIALIZED VIEW IF EXISTS service.mv_sweetener_catalog;
CREATE MATERIALIZED VIEW service.mv_sweetener_catalog AS
SELECT
    t.tag_id,
    t.tag_code,
    t.tag_name,
    t.description,
    t.caution_text,
    t.source_url,
    count(pt.product_id)                                            AS product_count,
    round(avg(p.sugars), 2)                                         AS avg_sugar_of_products
FROM service.tags t
LEFT JOIN service.product_tags pt ON pt.tag_id = t.tag_id
LEFT JOIN service.products p      ON p.product_id = pt.product_id
WHERE t.tag_type = 'SWEETENER'
GROUP BY t.tag_id, t.tag_code, t.tag_name, t.description, t.caution_text, t.source_url;

CREATE UNIQUE INDEX IF NOT EXISTS mv_sweetener_catalog_code_idx
    ON service.mv_sweetener_catalog (tag_code);

CREATE OR REPLACE VIEW service.v_swap_coverage AS
SELECT
    'recipe'::text AS kind,
    count(DISTINCT ri.recipe_id) FILTER (WHERE rip.recipe_ingredient_id IS NOT NULL) AS covered,
    count(DISTINCT ri.recipe_id)                                                     AS total
FROM service.recipe_ingredients ri
LEFT JOIN service.recipe_ingredient_products rip
       ON rip.recipe_ingredient_id = ri.id;
