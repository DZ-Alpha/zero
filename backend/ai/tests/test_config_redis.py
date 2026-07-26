from app.core.config import settings


def test_redis_settings_have_defaults():
    assert settings.redis_host  # non-empty default
    assert settings.redis_port == 6379
    assert settings.conversation_ttl_seconds == 86400
    # 비밀번호는 빈 문자열 기본 허용(로컬 개발)
    assert isinstance(settings.redis_password, str)
    # 타임아웃 필수(장애 시 무한 대기 방지 — login-service P0-1 이력)
    assert settings.redis_connect_timeout_seconds == 3.0
    assert settings.redis_socket_timeout_seconds == 3.0
