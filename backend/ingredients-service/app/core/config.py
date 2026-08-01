from urllib.parse import quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # 2026-08-01 보안 점검 - 스테이징 백엔드 9개가 사내망에서 인증 없이
    # /docs(OpenAPI 자동 문서)까지 그대로 노출된 게 확인됐다. secure-by-default로
    # 기본은 꺼둔다 - 로컬 개발은 .env.example의 ENABLE_API_DOCS=true로 켜져 있다.
    enable_api_docs: bool = False

    frontend_url: str = "http://localhost:3000"

    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "test_db"
    postgres_user: str = ""
    postgres_password: str = ""

    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    # Must match login-service's JWT_EXPIRE_MINUTES (sliding-session refresh).
    jwt_expire_minutes: int = 180

    @property
    def database_url(self) -> str:
        user = quote_plus(self.postgres_user)
        password = quote_plus(self.postgres_password)
        return f"postgresql+asyncpg://{user}:{password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"


settings = Settings()
