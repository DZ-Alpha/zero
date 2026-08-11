-- kafka/migrations/014_perf_indexes.sql
-- 얌로그(rooms) 진입이 느린 문제 — 조인 컬럼 인덱스 누락.
--
-- 증상:
--   얌로그 페이지만 눈에 띄게 느림. 다른 화면은 정상.
--
-- 원인:
--   community-service 는 방 요약을 만들 때 방마다 diet-service 의
--   GET /diet/internal/meal-records 를 부르고, 그 안에서
--   app/services/diet_store.py:get_records_for_users_on_date 가
--   meal_logs ⋈ meal_items 를 meal_log_id 로 조인한다.
--   그런데 service.meal_items 에는 meal_log_id 인덱스가 없었다
--   (있는 건 PK(meal_item_id) 와 product_id 부분 인덱스뿐).
--   그래서 이 조인이 매번 meal_items 전체를 순차 스캔했다.
--
--   실측(2026-08-10, pg_stat_user_tables):
--     meal_items  seq_scan=224,412  seq_tup_read=1,145,672,571  idx_scan=18
--
--   meal_items 가 295행일 때는 순차 스캔이 사실상 공짜라 드러나지 않다가,
--   데모 시드로 19,465행이 되면서(66배) 표면화됐다. 인덱스 누락 자체는
--   시드 이전부터 있던 문제다.
--
-- 효과: 해당 조인 쿼리 13.5ms -> 0.56ms, meal_items 순차 스캔 제거.
--
-- CONCURRENTLY 라 트랜잭션 밖에서 실행해야 한다 (BEGIN/COMMIT 없음).

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_meal_items_meal_log
    ON service.meal_items (meal_log_id);

-- 주간 기록률·연속일수 집계가 room_meal_threads 를 user_id 로도 훑는다.
-- 기존 인덱스는 uq_room_meal_thread(room_id, user_id, record_date, meal_type)
-- 뿐이라 room_id 없이 user_id 로 들어오는 경로를 못 탄다.
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_room_meal_threads_user_date
    ON community.room_meal_threads (user_id, record_date);

-- community.room_members 에는 user_id 단독 인덱스를 만들지 않는다.
-- 123행 / 72kB 짜리 1페이지 테이블이라 순차 스캔이 이미 최적이고,
-- 플래너가 인덱스를 선택하지 않는다. 쓰기 비용만 늘어난다.

ANALYZE service.meal_items;
ANALYZE service.meal_logs;
ANALYZE community.room_meal_threads;
ANALYZE community.rooms;
