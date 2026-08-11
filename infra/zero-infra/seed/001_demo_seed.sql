-- infra/zero-infra/seed/001_demo_seed.sql
-- 발표/데모용 시드 데이터 — 실사용자 데이터가 아니다.
--
-- 만드는 것: 약 3개월 전부터 꾸준히 기록해 온 유저 100명 + 그들이 참여 중인 모임.
-- 랭킹/모임 화면이 비어 보이는 문제를 채우는 게 목적이다.
--
-- 격리 규칙 (제거를 쉽게 하려고 둘 다 건다):
--   1) 시드 유저는 id 900001~900100 대역만 쓴다. users_id_seq 는 건드리지 않으므로
--      실제 가입 흐름과 id 가 겹치지 않는다.
--   2) public.users.is_seed_data = true 로 표시한다.
-- 시드가 만든 meal_logs/room_members/user_health_profiles 는 전부 users FK 가
-- ON DELETE CASCADE 라 유저만 지우면 같이 사라진다. community.rooms 만
-- owner_id 가 ON DELETE RESTRICT 여서 teardown 에서 먼저 지운다.
--
-- 재실행 안전: 앞부분에서 기존 시드를 정리하고 다시 만든다.
-- 되돌리기: 001_demo_seed_teardown.sql

BEGIN;

-- ---------------------------------------------------------------------------
-- 0) 시드 표시용 컬럼
-- ---------------------------------------------------------------------------
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS is_seed_data boolean NOT NULL DEFAULT false;
COMMENT ON COLUMN public.users.is_seed_data IS
  '발표/데모용 시드 계정 표시. 실사용자 집계·분석에서 제외해야 한다.';

CREATE INDEX IF NOT EXISTS users_is_seed_data_idx ON public.users (is_seed_data) WHERE is_seed_data;

-- ---------------------------------------------------------------------------
-- 1) 기존 시드 제거 (재실행 대비)
-- ---------------------------------------------------------------------------
DELETE FROM community.rooms WHERE owner_id BETWEEN 900001 AND 900100;
DELETE FROM public.users    WHERE id       BETWEEN 900001 AND 900100;

-- 난수 고정 — 매번 같은 결과가 나오게 한다.
SELECT setseed(0.42);

-- ---------------------------------------------------------------------------
-- 2) 시드 유저 100명
--    가입일을 92~104일 전으로 밀어서 "3개월쯤 써 온 사람"이 되게 한다.
-- ---------------------------------------------------------------------------
CREATE TEMP TABLE seed_users ON COMMIT DROP AS
WITH pool AS (
  SELECT
    ARRAY['김','이','박','최','정','강','조','윤','장','임','한','신','오','서','권','황','안','송','류','전'] AS sur,
    ARRAY['서연','지우','서윤','하은','민서','지유','채원','수아','지아','다은',
          '은우','도윤','시우','하준','지호','예준','주원','건우','현우','우진',
          '유나','소율','예린','가은','시은','윤아','다연','하율','서아','아린'] AS given
),
g AS (SELECT generate_series(1, 100) AS i)
SELECT
  900000 + g.i                                     AS id,
  (SELECT sur[1 + ((g.i * 7)  % 20)] FROM pool)
    || (SELECT given[1 + ((g.i * 13) % 30)] FROM pool)
    || CASE WHEN g.i % 4 = 0 THEN g.i::text ELSE '' END  AS display_name,
  format('seed%03s@demo.invalid', g.i)             AS email,
  -- 60명 여성 / 40명 남성, 그중 70명을 20대에 몰아준다.
  CASE WHEN g.i <= 60 THEN 'FEMALE' ELSE 'MALE' END    AS gender,
  CASE WHEN g.i <= 70 THEN 1997 + (g.i % 10)           -- 20대
       WHEN g.i <= 88 THEN 1987 + (g.i % 10)           -- 30대
       ELSE              1977 + (g.i % 10)             -- 40대
  END                                              AS birth_year,
  (now() - make_interval(days => 92 + (g.i % 13)))  AS joined_at,
  -- 기록 성실도: 유저마다 0.55 ~ 0.95
  (0.55 + (g.i % 41) * 0.01)::numeric              AS record_rate,
  -- 평균 당 섭취 성향 배수
  (0.80 + (g.i % 27) * 0.02)::numeric              AS sugar_factor
FROM g;

INSERT INTO public.users (id, email, display_name, birthday, favorite_categories,
                          is_allergic, optional_agree, tall, weight,
                          created_at, updated_at, is_seed_data)
SELECT
  s.id,
  s.email,
  s.display_name,
  make_date(s.birth_year, 1 + (s.id % 12), 1 + (s.id % 27)),
  CASE WHEN s.gender = 'FEMALE'
       THEN ARRAY['음료','간식','유제품'] ELSE ARRAY['간식','면류','음료'] END,
  (s.id % 11 = 0),
  true,
  CASE WHEN s.gender = 'FEMALE' THEN 156 + (s.id % 14) ELSE 168 + (s.id % 16) END,
  CASE WHEN s.gender = 'FEMALE' THEN 48 + (s.id % 15) ELSE 62 + (s.id % 20) END,
  s.joined_at,
  s.joined_at,
  true
FROM seed_users s;

-- 건강 프로필 — gender/birth_year 가 여기 있어서 연령·성별 코호트는 이 테이블로 잡는다.
-- ck_health_consent 때문에 값을 채우면 health_data_consent_at 이 반드시 있어야 한다.
INSERT INTO service.user_health_profiles
  (user_id, birth_year, gender, height_cm, weight_kg, activity_level, health_goal,
   daily_calorie_target, daily_sugar_target_g, target_source,
   health_data_consent_at, updated_at)
SELECT
  s.id,
  s.birth_year,
  s.gender,
  CASE WHEN s.gender = 'FEMALE' THEN 156 + (s.id % 14) ELSE 168 + (s.id % 16) END,
  CASE WHEN s.gender = 'FEMALE' THEN 48 + (s.id % 15) ELSE 62 + (s.id % 20) END,
  (ARRAY['LOW','MODERATE','HIGH'])[1 + (s.id % 3)],
  (ARRAY['SUGAR_REDUCTION','WEIGHT_LOSS','MAINTENANCE'])[1 + (s.id % 3)],
  CASE WHEN s.gender = 'FEMALE' THEN 1800 ELSE 2200 END,
  25,
  'CALCULATED',
  s.joined_at,
  s.joined_at
FROM seed_users s;

-- ---------------------------------------------------------------------------
-- 3) 시드 모임 6개 — 랭킹 화면을 채우는 용도
-- ---------------------------------------------------------------------------
CREATE TEMP TABLE seed_rooms ON COMMIT DROP AS
WITH spec(idx, name, emoji, size, days_ago) AS (
  VALUES (1, '천천히 달게',   '🐢', 12, 96),
         (2, '샐러드 연구소', '🥬',  8, 88),
         (3, '아침 여섯 시',  '🌤️',  9, 74),
         (4, '꾸준한 한입',   '🥄', 17, 91),
         (5, '직장인 점심단', '💼', 14, 63),
         (6, '밥심으로',      '🍙', 11, 55)
)
SELECT
  gen_random_uuid() AS room_id,
  spec.*,
  -- 방장: 시드 유저 중 하나를 순서대로 배정
  900000 + spec.idx AS owner_id
FROM spec;

INSERT INTO community.rooms (id, name, emoji, owner_id, started_at,
                             ranking_opt_in, created_at, updated_at)
SELECT r.room_id, r.name, r.emoji, r.owner_id,
       now() - make_interval(days => r.days_ago),
       true,
       now() - make_interval(days => r.days_ago),
       now()
FROM seed_rooms r;

-- 방장 등록
INSERT INTO community.room_members (room_id, user_id, role, joined_at,
                                    nudge_notifications, activity_notifications)
SELECT r.room_id, r.owner_id, 'owner',
       now() - make_interval(days => r.days_ago), true, true
FROM seed_rooms r;

-- 나머지 멤버 채우기 — 유저를 방에 라운드로빈으로 배정한다.
INSERT INTO community.room_members (room_id, user_id, role, joined_at,
                                    nudge_notifications, activity_notifications)
SELECT r.room_id,
       u.id,
       'member',
       now() - make_interval(days => (r.days_ago - 3 - (u.id % 20))),
       (u.id % 3 <> 0),
       true
FROM seed_rooms r
JOIN LATERAL (
  SELECT s.id
  FROM seed_users s
  WHERE s.id <> r.owner_id
    AND (s.id % 6) = (r.idx % 6)
  ORDER BY s.id
  LIMIT r.size - 1
) u ON true
ON CONFLICT DO NOTHING;

-- 실제 팀이 만든 기존 모임에도 시드 멤버를 몇 명씩 넣어 사람 사는 방처럼 보이게 한다.
INSERT INTO community.room_members (room_id, user_id, role, joined_at,
                                    nudge_notifications, activity_notifications)
SELECT rm.id, u.id, 'member',
       greatest(rm.started_at, now() - interval '60 days') + interval '1 day',
       true, true
FROM (SELECT id, started_at, row_number() OVER (ORDER BY started_at) AS rn
      FROM community.rooms
      WHERE deleted_at IS NULL AND owner_id < 900000) rm
JOIN LATERAL (
  SELECT s.id FROM seed_users s
  WHERE (s.id % 9) = (rm.rn % 9)
  ORDER BY s.id LIMIT 4
) u ON true
ON CONFLICT DO NOTHING;

-- ---------------------------------------------------------------------------
-- 4) 3개월치 식단 기록
--    유저별 record_rate 만큼의 날에, 끼니별로 기록을 남긴다.
-- ---------------------------------------------------------------------------
CREATE TEMP TABLE seed_logs ON COMMIT DROP AS
SELECT
  gen_random_uuid() AS meal_log_id,
  s.id              AS user_id,
  s.sugar_factor,
  (date_trunc('day', now()) - make_interval(days => d.day)
     + make_interval(hours => m.hour, mins => (s.id * 7 + d.day) % 60)) AS eaten_at,
  m.meal_type
FROM seed_users s
CROSS JOIN generate_series(0, 89) AS d(day)
CROSS JOIN (VALUES ('BREAKFAST', 8), ('LUNCH', 12), ('DINNER', 19), ('SNACK', 15))
             AS m(meal_type, hour)
WHERE d.day * 86400 < EXTRACT(epoch FROM (now() - s.joined_at))   -- 가입 전 기록은 만들지 않는다
  AND random() < s.record_rate
  AND (m.meal_type <> 'SNACK' OR random() < 0.45);                -- 간식은 가끔만

INSERT INTO service.meal_logs
  (meal_log_id, user_id, eaten_at, meal_type, image_object_key, input_type,
   analysis_status, needs_user_confirmation, vision_confidence, vision_provider,
   created_at, updated_at)
SELECT
  l.meal_log_id, l.user_id, l.eaten_at, l.meal_type,
  NULL,
  (ARRAY['VISION','MANUAL','PRODUCT','RECIPE'])[1 + (abs(hashtext(l.meal_log_id::text)) % 4)],
  'COMPLETED',
  false,
  NULL, NULL,
  l.eaten_at, l.eaten_at
FROM seed_logs l;

-- 기록마다 실제 상품을 하나 붙인다. 영양값은 상품의 실제 값을 그대로 쓴다.
-- 상품 개수에 의존하지 않게 번호를 매겨 두고 해시로 고른다(스테이징은 상품이 적다).
CREATE TEMP TABLE seed_product_pool ON COMMIT DROP AS
SELECT row_number() OVER (ORDER BY product_id) AS rn,
       product_id, product_name, calories, sugars, carbohydrate
FROM service.products
WHERE sugars IS NOT NULL;

INSERT INTO service.meal_items
  (meal_item_id, meal_log_id, product_id, item_name,
   serving_value, serving_unit, calories, sugars, carbohydrate, created_at)
SELECT
  gen_random_uuid(),
  l.meal_log_id,
  p.product_id,
  p.product_name,
  1,
  '인분',
  round(coalesce(p.calories, 250) * 1.0, 2),
  round(coalesce(p.sugars, 5) * l.sugar_factor, 2),
  round(coalesce(p.carbohydrate, 30) * 1.0, 2),
  l.eaten_at
FROM seed_logs l
JOIN seed_product_pool p
  ON p.rn = 1 + (abs(hashtext(l.meal_log_id::text)) % (SELECT count(*) FROM seed_product_pool));

COMMIT;

-- ---------------------------------------------------------------------------
-- 확인
-- ---------------------------------------------------------------------------
SELECT 'seed users'   AS what, count(*) FROM public.users WHERE is_seed_data
UNION ALL SELECT 'seed rooms',   count(*) FROM community.rooms       WHERE owner_id >= 900000
UNION ALL SELECT 'room members', count(*) FROM community.room_members WHERE user_id >= 900000
UNION ALL SELECT 'meal logs',    count(*) FROM service.meal_logs      WHERE user_id >= 900000
UNION ALL SELECT 'meal items',   count(*) FROM service.meal_items mi
                                 JOIN service.meal_logs ml USING (meal_log_id)
                                 WHERE ml.user_id >= 900000;
