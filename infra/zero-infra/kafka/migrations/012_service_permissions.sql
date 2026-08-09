-- kafka/migrations/012_service_permissions.sql
--
-- 현재 운영·스테이징 애플리케이션 접속 role은 yesman 하나이며,
-- 새 오브젝트의 owner(postgres)와 분리되어 있다. 이 파일은 비밀번호를
-- 다루지 않고 백엔드가 필요한 최소 객체 권한만 부여한다.
-- 대안 재생성·matview refresh는 별도 운영 Job/계정으로 수행해야 한다.

GRANT USAGE ON SCHEMA service, product, content TO yesman;

GRANT SELECT ON
    service.v_product_display,
    service.v_product_swap_pick,
    service.v_recipe_swap_ranking,
    service.mv_category_sugar_stats,
    service.mv_sweetener_catalog,
    product.product_alternatives,
    product.product_review_sentiment,
    service.search_miss_queue,
    content.articles,
    content.collections,
    content.collection_products
TO yesman;

GRANT SELECT, INSERT, UPDATE, DELETE
    ON product.product_reviews TO yesman;

GRANT INSERT ON service.event_outbox TO yesman;

-- REFRESH MATERIALIZED VIEW는 일반 GRANT로 위임되지 않고 owner 권한이
-- 필요하다. 전용 Job/계정이 확정되면 그 계정에만 owner 또는 제한된
-- SECURITY DEFINER 실행 경로를 별도로 부여한다. 앱 role을 matview owner로
-- 올리지 않는다.
