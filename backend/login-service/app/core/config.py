from urllib.parse import quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    naver_client_id: str = ""
    naver_client_secret: str = ""
    naver_redirect_uri: str = "http://localhost:8000/social-access/naver/callback"

    kakao_client_id: str = ""
    kakao_client_secret: str = ""
    kakao_redirect_uri: str = "http://localhost:8000/social-access/kakao/callback"

    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/social-access/google/callback"

    # "Services ID" from the Apple Developer portal. Apple login additionally needs
    # a Team ID / Key ID / private key to sign the client assertion JWT for the
    # token exchange — not modeled yet, see app/services/oauth/apple.py.
    apple_client_id: str = ""
    apple_redirect_uri: str = "http://localhost:8000/social-access/apple/callback"

    jwt_secret: str = "dev-secret-change-me"
    jwt_expire_minutes: int = 180

    frontend_url: str = "http://localhost:3000"

    turnstile_secret_key: str = ""

    admin_signup_secret: str = ""

    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "test_db"
    postgres_user: str = ""
    postgres_password: str = ""

    # 세션/OAuth state/rate-limit 저장용 (app/services/*_store.py, rate_limiter.py)
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: str = ""
    # PRODUCTION_HANDOFF.md P0-1 - Redis 클라이언트에 타임아웃이 없어서, 방화벽/네트워크
    # 문제로 Redis에 연결이 안 되면 create_state() 호출이 끝없이 멈춰 OAuth 로그인
    # 시작 요청 자체가 응답을 안 하는 것처럼 보였다(프론트 8초 타임아웃으로만 감지됨).
    # 초 단위 - 방화벽이 SYN을 그냥 드롭하면 실패까지 이 시간만큼 걸린다.
    redis_connect_timeout_seconds: float = 3.0
    redis_socket_timeout_seconds: float = 3.0

    @property
    def database_url(self) -> str:
        user = quote_plus(self.postgres_user)
        password = quote_plus(self.postgres_password)
        return f"postgresql+asyncpg://{user}:{password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"


settings = Settings()
