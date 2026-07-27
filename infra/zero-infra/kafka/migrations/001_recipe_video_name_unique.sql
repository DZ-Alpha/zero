-- kafka/migrations/001_recipe_video_name_unique.sql
-- 버전 분리(같은 video_id + 다른 name)는 허용하고, 완전 중복(같은 video_id + 같은 name)만
-- 거부한다. 경쟁 조건에서도 DB가 원자적으로 두 번째 INSERT를 막는다.
CREATE UNIQUE INDEX IF NOT EXISTS uq_recipe_video_name
    ON service.recipes (video_id, name);
