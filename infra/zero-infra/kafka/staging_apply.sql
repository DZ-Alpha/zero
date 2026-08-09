-- staging_apply.sql
-- psql -v ON_ERROR_STOP=1 -f staging_apply.sql 로 실행하는 스테이징 전용 진입점.
-- 001~002는 기존 베이스 스키마에 이미 적용되어 있다는 전제다.
-- 운영 DB에서는 실행하지 않는다.

\set ON_ERROR_STOP on

\ir migrations/003_swap_indexes.sql
\ir migrations/004_swap_views.sql
\ir migrations/005_product_alternatives.sql
\ir migrations/005b_fill_product_alternatives.sql
\ir migrations/006_queue_and_reviews.sql
\ir migrations/007_columns_recipes_products.sql
\ir migrations/008_fill_tag_metadata.sql
\ir migrations/009_content_schema.sql
\ir migrations/010_alternatives_fk.sql
\ir migrations/011_product_display_views.sql
\ir migrations/013_fix_swap_pick_null_report.sql
\ir migrations/012_service_permissions.sql
\ir staging_sample_data.sql
