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

    anthropic_api_key: str = ""

    # "anthropic"(다이렉트 API) 또는 "bedrock". PR-0301/0302/0303의 _call_claude만
    # 이 값을 본다 - 챗봇(backend/ai)과 diet-service의 Vision 분석은 각자 자기
    # .env/설정을 따로 쓰므로 이 값의 영향을 받지 않는다.
    ai_provider: str = "anthropic"
    bedrock_model_id: str = "anthropic.claude-haiku-4-5-20251001-v1:0"
    bedrock_region: str = "us-east-1"

    # 상품 이미지 자체 호스팅(MinIO). diet-service와 같은 MinIO를 쓰되 버킷만
    # 다르다(product-images, 공개 read). 비어있으면 이미지 저장을 시도하지 않고
    # 원본 URL을 그대로 둔다 — 잘못된 설정으로 조용히 실패하지 않도록.
    minio_endpoint: str = ""
    minio_access_key: str = ""
    minio_secret_key: str = ""
    minio_product_bucket: str = "product-images"

    @property
    def database_url(self) -> str:
        user = quote_plus(self.postgres_user)
        password = quote_plus(self.postgres_password)
        return f"postgresql+asyncpg://{user}:{password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"


settings = Settings()
