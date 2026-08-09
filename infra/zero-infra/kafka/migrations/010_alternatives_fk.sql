-- kafka/migrations/010_alternatives_fk.sql
-- product.product_alternatives 에 FK 를 건다.
--
-- 사고 배경(2026-08-09): 상품 정제 작업으로 service.products 에서 비식품 11건을
-- 삭제했는데, product_alternatives 에 FK 가 없어서 연쇄 삭제가 안 됐다.
-- 삭제된 '제로스킨 MD 크림'을 기준 상품으로 하는 대안 행 1건이 고아로 남았고,
-- 그 상태로 API 가 조회하면 존재하지 않는 상품을 참조하게 된다.
--
-- 005b 재실행으로 고아는 정리했지만, 재실행을 잊으면 같은 일이 반복된다.
-- 구조로 막는다 — 상품이 지워지면 그 상품의 대안 행도 함께 지워진다.
--
-- service.recipe_ingredient_products 와 service.product_embeddings 는 이미
-- 같은 방식(ON DELETE CASCADE)으로 걸려 있다. 그 패턴을 맞춘다.

ALTER TABLE product.product_alternatives
    DROP CONSTRAINT IF EXISTS fk_alt_base_product,
    DROP CONSTRAINT IF EXISTS fk_alt_target_product;

ALTER TABLE product.product_alternatives
    ADD CONSTRAINT fk_alt_base_product
        FOREIGN KEY (product_id)
        REFERENCES service.products(product_id) ON DELETE CASCADE,
    ADD CONSTRAINT fk_alt_target_product
        FOREIGN KEY (alt_product_id)
        REFERENCES service.products(product_id) ON DELETE CASCADE;
