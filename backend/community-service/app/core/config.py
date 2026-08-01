from urllib.parse import quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # 2026-08-01 보안 점검 - 스테이징 백엔드 9개가 사내망에서 인증 없이
    # /docs(OpenAPI 자동 문서)까지 그대로 노출된 게 확인됐다. secure-by-default로
    # 기본은 꺼둔다 - 로컬 개발은 .env.example의 ENABLE_API_DOCS=true로 켜져 있다.
    enable_api_docs: bool = False

    # Must match login-service's JWT_SECRET — this service only verifies
    # tokens issued by login-service, it never issues its own (it does
    # re-sign refreshed tokens with the same secret, see core/security.py).
    jwt_secret: str = "dev-secret-change-me"
    # Must match login-service's JWT_EXPIRE_MINUTES (sliding-session refresh).
    jwt_expire_minutes: int = 180

    frontend_url: str = "http://localhost:3000"

    # Same Postgres instance as login-service/main-service. Unlike the `service`
    # schema (data-team managed), this service owns and self-migrates its own
    # `community` schema — see app/core/database.py.
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "test_db"
    postgres_user: str = ""
    postgres_password: str = ""

    # 얌로그(rooms) 연동용 — Diet Service 내부 조회 엔드포인트
    # (GET /diet/internal/meal-records)를 서버간 호출로 사용한다.
    diet_service_url: str = "http://diet-service:8020"
    # diet-service의 동일 이름 설정과 값이 같아야 한다 — 그쪽 config.py 주석 참고.
    internal_service_secret: str = ""

    @property
    def database_url(self) -> str:
        user = quote_plus(self.postgres_user)
        password = quote_plus(self.postgres_password)
        return f"postgresql+asyncpg://{user}:{password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"


settings = Settings()
