-- kafka/migrations/005b_fill_product_alternatives.sql
-- product.product_alternatives 를 채우는 배치. 재실행 안전(전량 교체).
--
-- 상품 데이터가 갱신되면(정규화 배치, 신규 적재) product_embeddings 를 먼저
-- upsert 한 뒤 이 스크립트를 다시 돌린다. 순서를 지키지 않으면 낡은 벡터로
-- 대안이 만들어진다.
--
-- 성능: 카테고리 안에서만 비교하므로 최대 부담은 음료(995건)다.
-- LATERAL + HNSW 인덱스로 상품당 상위 후보만 뽑는다. 실측 7초(2,438건 전량).
--
-- 유사도 하한 0.70 의 근거(2026-08-09, 각 구간 무작위 6쌍 육안 검수):
--   0.60~0.65 : 쓸 수 없다. "노니주스 -> 토마토주스", "통밀스콘 -> 녹차양갱"처럼
--               종류가 다른 것이 섞인다. 이름이 비슷해 보여도 실제로는 다른 제품이다.
--   0.70~0.75 : 쓸 만하다. "저당치폴레소스 -> 저당 굴소스",
--               "치즈케이크 -> 초코마들렌"(같은 브랜드 디저트).
--   0.80~     : 매우 정확하다. "저당 스위트 칠리 소스 -> 저칼로리 스위트 칠리 소스".
-- 카테고리가 11종뿐이라 성긴 편이고(토스트소스와 오트밀이 같은 '베이커리·간식'),
-- 카테고리 필터만으로는 못 거른다 — 유사도 하한이 실질적인 안전장치다.

BEGIN;

TRUNCATE product.product_alternatives;

INSERT INTO product.product_alternatives
    (product_id, alt_product_id, rank, similarity, sugar_delta_g, sugar_delta_pct, kcal_delta)
SELECT
    base.product_id,
    cand.product_id,
    cand.rn::smallint,
    cand.similarity,
    cand.sugar_delta_g,
    cand.sugar_delta_pct,
    cand.kcal_delta
FROM (
    SELECT
        p.product_id,
        p.food_type,
        p.serving_value,
        p.serving_unit,
        p.sugars,
        p.calories,
        pe.embedding,
        pt.tag_id AS cat_tag
    FROM service.products p
    JOIN service.product_embeddings pe ON pe.product_id = p.product_id
    JOIN service.product_tags pt       ON pt.product_id = p.product_id
    JOIN service.tags t                ON t.tag_id = pt.tag_id AND t.tag_type = 'CATEGORY'
    WHERE p.sugars > 0            -- 이미 0g 이면 더 낮은 대안이 존재할 수 없다
      AND p.food_type IS NOT NULL
      AND p.serving_value IS NOT NULL
      AND p.serving_unit IS NOT NULL
      AND p.product_name !~* '(저당|제로|무가당|무설탕|sugar[ -]?free)'
      AND NOT EXISTS (
          SELECT 1
          FROM service.product_tags low_pt
          JOIN service.tags low_t ON low_t.tag_id = low_pt.tag_id
          WHERE low_pt.product_id = p.product_id
            AND low_t.tag_type = 'HEALTH_LABEL'
            AND low_t.tag_code IN ('SUGAR_FREE', 'ZERO_SUGAR', 'LOW_SUGAR', 'ZERO_GENERAL')
      )
) AS base
CROSS JOIN LATERAL (
    SELECT
        p2.product_id,
        round((1 - (pe2.embedding <=> base.embedding))::numeric, 4) AS similarity,
        round((p2.sugars - base.sugars)::numeric, 2)                AS sugar_delta_g,
        round((100.0 * (p2.sugars - base.sugars) / base.sugars)::numeric, 2) AS sugar_delta_pct,
        round((p2.calories - base.calories)::numeric, 2)            AS kcal_delta,
        row_number() OVER (
            ORDER BY (1 - (pe2.embedding <=> base.embedding)) DESC, p2.sugars ASC
        ) AS rn
    FROM service.products p2
    JOIN service.product_embeddings pe2 ON pe2.product_id = p2.product_id
    JOIN service.product_tags pt2       ON pt2.product_id = p2.product_id
    JOIN service.tags t2                ON t2.tag_id = pt2.tag_id AND t2.tag_type = 'CATEGORY'
    WHERE t2.tag_id = base.cat_tag                 -- 같은 카테고리
      AND p2.product_id <> base.product_id
      AND p2.food_type = base.food_type             -- 같은 세부 식품군
      AND p2.serving_value = base.serving_value     -- 같은 비교 수량
      AND lower(btrim(p2.serving_unit)) = lower(btrim(base.serving_unit)) -- 같은 g/mL 단위
      AND p2.sugars < base.sugars                  -- 실제로 더 낮아야 한다
      AND (1 - (pe2.embedding <=> base.embedding)) >= 0.70  -- 유사도 하한(아래 근거)
      AND (base.sugars - p2.sugars) >= 0.5         -- 노이즈 컷(절대)
      AND (
            (base.sugars - p2.sugars) >= 2.0                   -- 2g 이상 줄거나
         OR (100.0 * (base.sugars - p2.sugars) / base.sugars) >= 20.0  -- 20% 이상 줄거나
      )
    ORDER BY (1 - (pe2.embedding <=> base.embedding)) DESC, p2.sugars ASC
    LIMIT 5
) AS cand;

COMMIT;

ANALYZE product.product_alternatives;
