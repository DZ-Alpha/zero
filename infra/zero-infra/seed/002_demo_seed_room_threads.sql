-- infra/zero-infra/seed/002_demo_seed_room_threads.sql
-- 001_demo_seed.sql 보완 — 모임 "기록률"이 0% 로 뜨는 문제를 고친다.
--
-- 배경:
--   모임 화면의 기록률은 service.meal_logs 가 아니라 community.room_meal_threads
--   에서 계산된다. 이 테이블은 평소 diet-service 가 식단 기록 완료 시점에
--   community-service 의 POST /rooms/internal/meal-recorded 를 호출해서 채워진다.
--   001 은 meal_logs 에 DB 로 직접 넣었기 때문에 그 호출이 없었고, 그래서
--   평균 당류(meal_items 직접 조회)는 나오는데 기록률만 0% 였다.
--
-- 하는 일:
--   시드 유저의 meal_logs 를, 그 유저가 그 시점에 속해 있던 모든 방에 대해
--   room_meal_threads 로 팬아웃한다. 내부 엔드포인트가 하던 것과 같은 동작이다.
--
-- 되돌리기: 001_demo_seed_teardown.sql (room_id/user_id FK 가 ON DELETE CASCADE)

BEGIN;

INSERT INTO community.room_meal_threads (id, room_id, user_id, record_date, meal_type, created_at)
SELECT
  gen_random_uuid(),
  m.room_id,
  ml.user_id,
  (ml.eaten_at AT TIME ZONE 'Asia/Seoul')::date AS record_date,
  ml.meal_type,
  ml.eaten_at
FROM service.meal_logs ml
JOIN community.room_members m
  ON m.user_id = ml.user_id
 -- 방에 들어오기 전 기록은 그 방에 안 뜬다
 AND m.joined_at <= ml.eaten_at
 AND (m.left_at IS NULL OR m.left_at > ml.eaten_at)
JOIN community.rooms r
  ON r.id = m.room_id AND r.deleted_at IS NULL
WHERE ml.user_id BETWEEN 900001 AND 900100      -- 시드 유저만
  AND ml.analysis_status = 'COMPLETED'
ON CONFLICT ON CONSTRAINT uq_room_meal_thread DO NOTHING;

COMMIT;

-- ---------------------------------------------------------------------------
-- 확인 — 방별 최근 30일 기록률
--   기록률 = (실제 기록한 멤버-일 수) / (멤버 수 x 30일)
-- ---------------------------------------------------------------------------
SELECT
  r.name,
  r.emoji,
  count(DISTINCT m.user_id) AS members,
  round(
    100.0 * count(DISTINCT (t.user_id::text || t.record_date::text))
    / nullif(count(DISTINCT m.user_id) * 30, 0)
  , 0) AS record_rate_pct
FROM community.rooms r
JOIN community.room_members m ON m.room_id = r.id AND m.left_at IS NULL
LEFT JOIN community.room_meal_threads t
  ON t.room_id = r.id
 AND t.record_date > (now() AT TIME ZONE 'Asia/Seoul')::date - 30
WHERE r.deleted_at IS NULL
GROUP BY r.id, r.name, r.emoji
ORDER BY record_rate_pct DESC NULLS LAST;
