import os
from kafka.common.env import find_and_load_env

# .env 위치를 상위로 탐색해 로드(로컬 zero_data/, 서버 opt/zero-infra/ 모두 대응)
find_and_load_env()

BOOTSTRAP_SERVERS = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/1")

TOPIC_PARSED = "recipe.parsed"
TOPIC_DLQ = "recipe.dlq"

GROUP_MAIN = "recipe-main"
GROUP_THUMBNAIL = "thumbnail"

CURSOR_KEY = "recipe:pipeline:last_fetched_at"

# 한 레시피 처리 시간 실측(2026-07-18, 재료 4개): 총 26초
#   - 적재 0.03초 / common 영양 3.8초 / substituted 매칭+영양+합산+base 22.3초
# 재료 12~13개 레시피는 더 걸릴 수 있어(substituted가 병목) 여유 있게 10분 유지.
# 기본값 5분(300000)은 재료 많은 레시피에서 리밸런싱 위험이 있어 상향한 것.
MAX_POLL_INTERVAL_MS = 600000
