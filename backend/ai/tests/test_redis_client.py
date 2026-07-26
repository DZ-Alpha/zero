from app.core.redis_client import redis_client


def test_redis_client_decodes_responses():
    kwargs = redis_client.connection_pool.connection_kwargs
    assert kwargs.get("decode_responses") is True


def test_redis_client_has_timeouts():
    # 타임아웃 없으면 Redis 장애 시 요청이 무한정 멈춘다(login-service P0-1).
    kwargs = redis_client.connection_pool.connection_kwargs
    assert kwargs.get("socket_connect_timeout") == 3.0
    assert kwargs.get("socket_timeout") == 3.0
