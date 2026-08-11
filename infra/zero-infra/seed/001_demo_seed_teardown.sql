-- infra/zero-infra/seed/001_demo_seed_teardown.sql
-- 001_demo_seed.sql 이 만든 데모 데이터를 전부 제거한다.
--
-- 시드 유저(id 900001~900100)를 지우면 meal_logs / meal_items / room_members /
-- user_health_profiles / favorites 는 FK ON DELETE CASCADE 로 함께 사라진다.
-- community.rooms 만 owner_id 가 ON DELETE RESTRICT 라 먼저 지운다.

BEGIN;

DELETE FROM community.rooms WHERE owner_id BETWEEN 900001 AND 900100;
DELETE FROM public.users    WHERE id       BETWEEN 900001 AND 900100;

-- 플래그 컬럼까지 되돌리려면 아래 주석을 푼다.
-- ALTER TABLE public.users DROP COLUMN IF EXISTS is_seed_data;

COMMIT;

SELECT 'remaining seed users' AS what, count(*) FROM public.users WHERE id BETWEEN 900001 AND 900100
UNION ALL SELECT 'remaining seed rooms', count(*) FROM community.rooms WHERE owner_id >= 900000
UNION ALL SELECT 'orphan meal logs',     count(*) FROM service.meal_logs WHERE user_id >= 900000;
