-- staging_sample_data.sql
--
-- 수동 실행 전용. 운영 DB에서 실행하지 않는다.
-- 개인정보·실제 상품 이미지 없이 상품/레시피 대체 흐름만 검증하기 위한
-- deterministic sample이다. 011_product_display_views.sql을 먼저 적용한다.
-- 실행 순서: 003~012 적용 → 이 파일 실행 → 005b 재실행 →
-- mv_category_sugar_stats/mv_sweetener_catalog 갱신 → staging_validation.sql 실행

BEGIN;

INSERT INTO service.tags (tag_id, tag_type, tag_code, tag_name, active)
VALUES
    ('00000000-0000-0000-0000-00000000c001', 'CATEGORY', 'BEVERAGE', '음료', true),
    ('00000000-0000-0000-0000-00000000c002', 'CATEGORY', 'BAKERY_SNACK', '베이커리·간식', true),
    ('00000000-0000-0000-0000-00000000c003', 'CATEGORY', 'SAUCE_SEASONING', '소스·조미', true),
    ('00000000-0000-0000-0000-00000000c004', 'CATEGORY', 'JAM_SPREAD', '잼·스프레드', true),
    ('00000000-0000-0000-0000-00000000c005', 'CATEGORY', 'DAIRY', '유제품', true),
    ('00000000-0000-0000-0000-00000000d001', 'SWEETENER', 'SUCRALOSE', '수크랄로스', true),
    ('00000000-0000-0000-0000-00000000d002', 'SWEETENER', 'ERYTHRITOL', '에리스리톨', true)
ON CONFLICT (tag_type, tag_code) DO NOTHING;

INSERT INTO service.products
    (product_id, report_no, product_name, brand_name, manufacturer_name, food_type,
     serving_value, serving_unit, calories, carbohydrate, sugars, protein, fat,
     sodium, ingredient_text, image_url, purchase_url)
VALUES
 ('00000000-0000-0000-0000-000000000101','STG-BEV-001','콜라 테스트','제로랩','스테이징 제조사','음료',500,'mL',220,55,54,0,0,20,'탄산수, 설탕','https://example.invalid/staging/101',NULL),
 ('00000000-0000-0000-0000-000000000102','STG-BEV-001','콜라 테스트','제로랩 라이트','스테이징 제조사','음료',500,'mL',5,1,0,0,0,20,'탄산수, 수크랄로스','https://example.invalid/staging/102',NULL),
 ('00000000-0000-0000-0000-000000000103','STG-BEV-002','레몬 탄산 테스트','제로랩','스테이징 제조사','음료',350,'mL',90,22,20,0,0,10,'탄산수, 설탕','https://example.invalid/staging/103',NULL),
 ('00000000-0000-0000-0000-000000000104','STG-BEV-002','레몬 탄산 테스트','제로랩 제로','스테이징 제조사','음료',350,'mL',0,0,0,0,0,10,'탄산수, 에리스리톨','https://example.invalid/staging/104',NULL),
 ('00000000-0000-0000-0000-000000000105','STG-BAK-001','초코바 테스트','제로랩','스테이징 제조사','과자',40,'g',160,24,18,2,7,80,'코코아, 설탕','https://example.invalid/staging/105',NULL),
 ('00000000-0000-0000-0000-000000000106','STG-BAK-001','초코바 테스트','제로랩 로우','스테이징 제조사','과자',40,'g',110,16,3,3,6,80,'코코아, 에리스리톨','https://example.invalid/staging/106',NULL),
 ('00000000-0000-0000-0000-000000000107','STG-SAU-001','소스 테스트','제로랩','스테이징 제조사','소스',30,'g',90,15,12,1,0,300,'간장, 설탕','https://example.invalid/staging/107',NULL),
 ('00000000-0000-0000-0000-000000000108','STG-SAU-001','소스 테스트','제로랩 라이트','스테이징 제조사','소스',30,'g',55,8,2,1,0,300,'간장, 수크랄로스','https://example.invalid/staging/108',NULL),
 ('00000000-0000-0000-0000-000000000109','STG-JAM-001','딸기잼 테스트','제로랩','스테이징 제조사','잼',20,'g',50,12,10,0,0,0,'딸기, 설탕','https://example.invalid/staging/109',NULL),
 ('00000000-0000-0000-0000-000000000110','STG-JAM-001','딸기잼 테스트','제로랩 로우','스테이징 제조사','잼',20,'g',40,8,4,0,0,0,'딸기, 에리스리톨','https://example.invalid/staging/110',NULL),
 ('00000000-0000-0000-0000-000000000111','STG-DAI-001','요거트 테스트','제로랩','스테이징 제조사','유제품',150,'g',100,12,8,5,2,70,'원유, 설탕','https://example.invalid/staging/111',NULL),
 ('00000000-0000-0000-0000-000000000112','STG-DAI-001','요거트 테스트','제로랩 라이트','스테이징 제조사','유제품',150,'g',80,6,2,5,2,70,'원유, 에리스리톨','https://example.invalid/staging/112',NULL),
 ('00000000-0000-0000-0000-000000000113','STG-BEV-003','복숭아 탄산 테스트','제로랩','스테이징 제조사','음료',350,'mL',0,0,0,0,0,0,'탄산수, 수크랄로스','https://example.invalid/staging/113',NULL)
ON CONFLICT (product_id) DO NOTHING;

INSERT INTO service.product_tags (product_id, tag_id, evidence_source, matched_text)
VALUES
 ('00000000-0000-0000-0000-000000000101','00000000-0000-0000-0000-00000000c001','NAME','staging'),
 ('00000000-0000-0000-0000-000000000102','00000000-0000-0000-0000-00000000c001','NAME','staging'),
 ('00000000-0000-0000-0000-000000000103','00000000-0000-0000-0000-00000000c001','NAME','staging'),
 ('00000000-0000-0000-0000-000000000104','00000000-0000-0000-0000-00000000c001','NAME','staging'),
 ('00000000-0000-0000-0000-000000000105','00000000-0000-0000-0000-00000000c002','NAME','staging'),
 ('00000000-0000-0000-0000-000000000106','00000000-0000-0000-0000-00000000c002','NAME','staging'),
 ('00000000-0000-0000-0000-000000000107','00000000-0000-0000-0000-00000000c003','NAME','staging'),
 ('00000000-0000-0000-0000-000000000108','00000000-0000-0000-0000-00000000c003','NAME','staging'),
 ('00000000-0000-0000-0000-000000000109','00000000-0000-0000-0000-00000000c004','NAME','staging'),
 ('00000000-0000-0000-0000-000000000110','00000000-0000-0000-0000-00000000c004','NAME','staging'),
 ('00000000-0000-0000-0000-000000000111','00000000-0000-0000-0000-00000000c005','NAME','staging'),
 ('00000000-0000-0000-0000-000000000112','00000000-0000-0000-0000-00000000c005','NAME','staging'),
 ('00000000-0000-0000-0000-000000000113','00000000-0000-0000-0000-00000000c001','NAME','staging')
ON CONFLICT (product_id, tag_id) DO NOTHING;

INSERT INTO service.product_tags (product_id, tag_id, evidence_source, matched_text)
VALUES
 ('00000000-0000-0000-0000-000000000102','00000000-0000-0000-0000-00000000d001','INGREDIENT','수크랄로스'),
 ('00000000-0000-0000-0000-000000000104','00000000-0000-0000-0000-00000000d002','INGREDIENT','에리스리톨'),
 ('00000000-0000-0000-0000-000000000106','00000000-0000-0000-0000-00000000d002','INGREDIENT','에리스리톨'),
 ('00000000-0000-0000-0000-000000000108','00000000-0000-0000-0000-00000000d001','INGREDIENT','수크랄로스'),
 ('00000000-0000-0000-0000-000000000110','00000000-0000-0000-0000-00000000d002','INGREDIENT','에리스리톨'),
 ('00000000-0000-0000-0000-000000000112','00000000-0000-0000-0000-00000000d002','INGREDIENT','에리스리톨')
ON CONFLICT (product_id, tag_id) DO NOTHING;

INSERT INTO service.product_embeddings (product_id, embedding, source_text)
VALUES
 ('00000000-0000-0000-0000-000000000101',('['||'1'||repeat(',0',1023)||']')::vector,'staging:cola'),
 ('00000000-0000-0000-0000-000000000102',('['||'0.99,0.01'||repeat(',0',1022)||']')::vector,'staging:cola-zero'),
 ('00000000-0000-0000-0000-000000000103',('['||'1'||repeat(',0',1023)||']')::vector,'staging:lemon'),
 ('00000000-0000-0000-0000-000000000104',('['||'0.99,0.01'||repeat(',0',1022)||']')::vector,'staging:lemon-zero'),
 ('00000000-0000-0000-0000-000000000105',('['||'1'||repeat(',0',1023)||']')::vector,'staging:choco'),
 ('00000000-0000-0000-0000-000000000106',('['||'0.99,0.01'||repeat(',0',1022)||']')::vector,'staging:choco-low'),
 ('00000000-0000-0000-0000-000000000107',('['||'1'||repeat(',0',1023)||']')::vector,'staging:sauce'),
 ('00000000-0000-0000-0000-000000000108',('['||'0.99,0.01'||repeat(',0',1022)||']')::vector,'staging:sauce-low'),
 ('00000000-0000-0000-0000-000000000109',('['||'1'||repeat(',0',1023)||']')::vector,'staging:jam'),
 ('00000000-0000-0000-0000-000000000110',('['||'0.99,0.01'||repeat(',0',1022)||']')::vector,'staging:jam-low'),
 ('00000000-0000-0000-0000-000000000111',('['||'1'||repeat(',0',1023)||']')::vector,'staging:yogurt'),
 ('00000000-0000-0000-0000-000000000112',('['||'0.99,0.01'||repeat(',0',1022)||']')::vector,'staging:yogurt-low'),
 ('00000000-0000-0000-0000-000000000113',('['||'0.98,0.02'||repeat(',0',1022)||']')::vector,'staging:peach-zero')
ON CONFLICT (product_id) DO NOTHING;

INSERT INTO service.recipes
    (id, video_id, name, steps, total_sugar_g, total_kcal, base_sugar_g,
     base_kcal, sugar_reduction_pct, comparison_status, published_at, source,
     kcal_reduction_pct, category, cook_time_min)
VALUES
 (900001,'stg-recipe-001','스테이징 콜라 레시피','[]'::jsonb,0,5,54,220,100,'ready',now(),'staging',97.7,'음료',2),
 (900002,'stg-recipe-002','스테이징 초코바 레시피','[]'::jsonb,3,110,18,160,83.33,'ready',now(),'staging',31.25,'간식',5)
ON CONFLICT (id) DO NOTHING;

INSERT INTO service.recipe_ingredients
    (id, recipe_id, name, amount, ingredient_type, sugar_g, kcal, core_keyword, base_sugar_g, base_kcal)
VALUES
 (910001,900001,'콜라','500mL','substituted',0,5,'콜라',54,220),
 (910002,900002,'초코바','1개','substituted',3,110,'초코바',18,160)
ON CONFLICT (id) DO NOTHING;

INSERT INTO service.recipe_ingredient_products
    (recipe_ingredient_id, product_id, match_score, is_primary)
VALUES
 (910001,'00000000-0000-0000-0000-000000000102',0.990,true),
 (910002,'00000000-0000-0000-0000-000000000106',0.990,true)
ON CONFLICT DO NOTHING;

-- 리뷰 기능 샘플. user_id는 스테이징에 이미 존재하는 테스트 계정 중 가장 작은
-- ID를 사용하며, 실제 사용자 식별정보를 새로 만들거나 저장하지 않는다.
INSERT INTO product.product_reviews
    (review_id, product_id, user_id, rating, content, is_seed)
SELECT seed.review_id, seed.product_id, u.id, seed.rating, seed.content, true
FROM (
    VALUES
      ('00000000-0000-0000-0000-00000000e201'::uuid,
       '00000000-0000-0000-0000-000000000101'::uuid, 5::smallint,
       '당류 비교 화면 확인용 시드 리뷰입니다.'::text),
      ('00000000-0000-0000-0000-00000000e202'::uuid,
       '00000000-0000-0000-0000-000000000103'::uuid, 4::smallint,
       '스테이징 대체 추천 흐름 확인용 시드 리뷰입니다.'::text),
      ('00000000-0000-0000-0000-00000000e203'::uuid,
       '00000000-0000-0000-0000-000000000105'::uuid, 3::smallint,
       '상품 리뷰 CRUD 검증용 시드 리뷰입니다.'::text)
) AS seed(review_id, product_id, rating, content)
CROSS JOIN (SELECT min(id) AS id FROM public.users) AS u
WHERE u.id IS NOT NULL
ON CONFLICT (product_id, user_id) DO UPDATE
SET rating = EXCLUDED.rating,
    content = EXCLUDED.content,
    is_seed = true,
    updated_at = now();

-- 감정 요약 샘플. is_seed 리뷰가 포함되므로 includes_seed=true를 반드시 표시한다.
INSERT INTO product.product_review_sentiment
    (product_id, review_count, positive_count, neutral_count, negative_count,
     summary, model_id, includes_seed)
VALUES
 ('00000000-0000-0000-0000-000000000101', 3, 2, 1, 0,
  '스테이징 시드 리뷰 3건의 감정 요약입니다.', 'staging-rule-v1', true)
ON CONFLICT (product_id) DO UPDATE
SET review_count = EXCLUDED.review_count,
    positive_count = EXCLUDED.positive_count,
    neutral_count = EXCLUDED.neutral_count,
    negative_count = EXCLUDED.negative_count,
    summary = EXCLUDED.summary,
    model_id = EXCLUDED.model_id,
    includes_seed = true,
    computed_at = now();

-- 본문이 있는 공개 읽을거리 샘플. 기존 8건(비공개·본문 없음)은 변경하지 않는다.
INSERT INTO content.articles
    (slug, category, title, summary, body_md, read_minutes, source_note,
     sort_order, is_published)
VALUES
 ('staging-sugar-label-basics', '스테이징 검증', '영양성분표 당류 확인 방법',
  '스테이징 기능 검증을 위한 개인정보 없는 읽을거리 샘플입니다.',
  '## 확인 순서\n\n1. 1회 제공량을 확인합니다.\n2. 당류를 확인합니다.\n3. 비슷한 상품의 대안 여부를 비교합니다.',
  2, '스테이징 검증용 샘플', 990, true)
ON CONFLICT (slug) DO UPDATE
SET body_md = EXCLUDED.body_md,
    summary = EXCLUDED.summary,
    is_published = true,
    updated_at = now();

-- 상품과 연결된 식단 기록 샘플. 기존 스테이징 사용자를 재사용하고, 이미지나
-- 원문 개인정보는 저장하지 않는다.
INSERT INTO service.meal_logs
    (meal_log_id, user_id, input_type, meal_type, image_object_key,
     analysis_status, needs_user_confirmation, eaten_at, created_at)
SELECT '00000000-0000-0000-0000-00000000e301'::uuid, min(id), 'PRODUCT', 'SNACK',
       NULL, 'COMPLETED', false, now(), now()
FROM public.users
ON CONFLICT (meal_log_id) DO UPDATE
SET input_type = EXCLUDED.input_type,
    meal_type = EXCLUDED.meal_type,
    analysis_status = EXCLUDED.analysis_status,
    needs_user_confirmation = false,
    eaten_at = EXCLUDED.eaten_at;

INSERT INTO service.meal_items
    (meal_item_id, meal_log_id, product_id, external_recipe_id, item_name,
     serving_value, serving_unit, calories, sugars, carbohydrate)
VALUES
 ('00000000-0000-0000-0000-00000000e302'::uuid,
  '00000000-0000-0000-0000-00000000e301'::uuid,
  '00000000-0000-0000-0000-000000000102'::uuid, NULL, '콜라 테스트',
  500, 'mL', 5, 0, 1)
ON CONFLICT (meal_item_id) DO UPDATE
SET product_id = EXCLUDED.product_id,
    external_recipe_id = NULL,
    item_name = EXCLUDED.item_name,
    serving_value = EXCLUDED.serving_value,
    serving_unit = EXCLUDED.serving_unit,
    calories = EXCLUDED.calories,
    sugars = EXCLUDED.sugars,
    carbohydrate = EXCLUDED.carbohydrate;

-- 사용자 선호 설정 샘플. 기존 스테이징 테스트 계정과 음료 카테고리를 연결한다.
INSERT INTO service.user_preferences
    (preference_id, user_id, preference_type, tag_id, custom_value)
SELECT '00000000-0000-0000-0000-00000000e303'::uuid, min(u.id),
       'INTEREST_CATEGORY', '00000000-0000-0000-0000-00000000c001'::uuid, NULL
FROM public.users u
ON CONFLICT (preference_id) DO UPDATE
SET user_id = EXCLUDED.user_id,
    preference_type = EXCLUDED.preference_type,
    tag_id = EXCLUDED.tag_id,
    custom_value = NULL;

UPDATE content.collections
SET subtitle = '스테이징 테스트 데이터'
WHERE is_published;

COMMIT;

-- 샘플 원본을 넣은 뒤 005b를 반드시 재실행한다. 이 명령은 psql에서 실행되는
-- 상대 경로 include이며, 운영 DB에서는 이 파일 자체를 실행하지 않는다.
\ir migrations/005b_fill_product_alternatives.sql

-- 파생 데이터는 대안 계산 이후 갱신한다.
REFRESH MATERIALIZED VIEW service.mv_category_sugar_stats;
REFRESH MATERIALIZED VIEW service.mv_sweetener_catalog;

\ir staging_validation.sql
