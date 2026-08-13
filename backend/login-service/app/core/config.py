from urllib.parse import quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ── DB 접속/기동 정책 (2026-08-13 RDS 이전 준비) ──────────────────────
    # 파드당 커넥션 상한. 코드에 박아두면 이전 시점에 코드 수정 없이는 못 줄인다.
    # 온프렘 zero-pg는 max_connections=200이라 현재 합계(약 128)로 여유가 있어
    # 기본값은 지금 운영값 그대로 두고, RDS(db.t4g.small = 약 225, 백업/모니터링
    # 세션까지 함께 물림)에서는 배포 환경변수로 DB_POOL_SIZE=2, DB_MAX_OVERFLOW=1을
    # 준다(마이그레이션 계획서 A-15: 16파드 x 3 = 48).
    db_pool_size: int = 5
    db_max_overflow: int = 3

    # 앱 기동 시 DDL(CREATE TABLE/SCHEMA, ADD COLUMN)을 실행할지.
    # 지금은 앱 role에 DDL 권한이 있어 동작하지만, RDS에서 최소권한 app role을
    # 쓰면 여기서 InsufficientPrivilege가 나고 기동 자체가 실패한다(계획서 A-01).
    # RDS에서는 DB_AUTO_MIGRATE=false로 두고 db/migrations/*.sql을 배포 전에
    # DBA가 적용한다. 기본값 true는 현재 온프렘 동작을 그대로 유지한다.
    db_auto_migrate: bool = True

    # 2026-08-01 보안 점검 - 스테이징 백엔드 9개가 사내망에서 인증 없이
    # /docs(OpenAPI 자동 문서)까지 그대로 노출된 게 확인됐다. secure-by-default로
    # 기본은 꺼둔다 - 로컬 개발은 .env.example의 ENABLE_API_DOCS=true로 켜져 있다.
    enable_api_docs: bool = False

    # 2026-08-02 부하테스트 인계 — 카카오 인가코드가 1회용·단기만료라 k6로
    # 소셜 로그인 콜백을 재생할 수 없다. 외부 IdP 왕복만 건너뛰고 콜백과 동일한
    # 내부 처리(사용자 조회 + JWT 발급)를 태우는 테스트 전용 로그인이다.
    # secure-by-default로 기본은 꺼둔다 - 스테이징에서만 true로 켠다. 운영에
    # 켜지면 user_id만 알면 누구든 그 계정으로 로그인할 수 있으므로 반드시 false.
    enable_test_login: bool = False

    naver_client_id: str = ""
    naver_client_secret: str = ""
    naver_redirect_uri: str = "http://localhost:8000/social-access/naver/callback"

    kakao_client_id: str = ""
    kakao_client_secret: str = ""
    kakao_redirect_uri: str = "http://localhost:8000/social-access/kakao/callback"

    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/social-access/google/callback"

    # "Services ID" from the Apple Developer portal (client_id).
    apple_client_id: str = ""
    apple_redirect_uri: str = "http://localhost:8000/social-access/apple/callback"
    # client_secret은 고정값이 아니라 이 3개(Team ID/Key ID/.p8 private key)로
    # 매 요청 서명하는 JWT다(app/services/oauth/apple.py). private key는 개행이
    # 있는 PEM이라 .env/compose environment에 그대로 못 넣어서, 실제 개행 대신
    # 리터럴 "\n"으로 이스케이프한 한 줄 문자열로 받아 코드에서 되돌린다.
    apple_team_id: str = ""
    apple_key_id: str = ""
    apple_private_key: str = ""

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
    def apple_private_key_pem(self) -> str:
        return self.apple_private_key.replace("\\n", "\n")

    @property
    def database_url(self) -> str:
        user = quote_plus(self.postgres_user)
        password = quote_plus(self.postgres_password)
        return f"postgresql+asyncpg://{user}:{password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"


settings = Settings()
