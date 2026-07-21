from redis.asyncio import Redis

from app.core.config import settings

# 앱 전역에서 공유하는 async Redis 연결. login-service와 같은 방식(모듈 싱글턴).
# 실제 연결은 첫 명령 시 lazy로 맺어진다(임포트만으로 Redis 필요 없음).
# 타임아웃 필수 — 없으면 연결 실패 시 명령이 끝없이 멈춘다(P0-1 이력).
redis_client: Redis = Redis(
    host=settings.redis_host,
    port=settings.redis_port,
    password=settings.redis_password or None,
    decode_responses=True,
    socket_connect_timeout=settings.redis_connect_timeout_seconds,
    socket_timeout=settings.redis_socket_timeout_seconds,
)
