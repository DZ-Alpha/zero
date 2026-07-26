from urllib.parse import quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

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

    anthropic_api_key: str = ""

    # "anthropic"(다이렉트 API) 또는 "bedrock". PR-0301/0302/0303의 _call_claude만
    # 이 값을 본다 - 챗봇(backend/ai)과 diet-service의 Vision 분석은 각자 자기
    # .env/설정을 따로 쓰므로 이 값의 영향을 받지 않는다.
    ai_provider: str = "anthropic"
    bedrock_model_id: str = "anthropic.claude-haiku-4-5-20251001-v1:0"
    bedrock_region: str = "us-east-1"

    @property
    def database_url(self) -> str:
        user = quote_plus(self.postgres_user)
        password = quote_plus(self.postgres_password)
        return f"postgresql+asyncpg://{user}:{password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"


settings = Settings()
