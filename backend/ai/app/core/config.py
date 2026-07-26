from urllib.parse import quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # login-service와 반드시 동일한 시크릿. 이 서비스는 토큰을 발급하지 않고
    # 검증만 하되, 갱신 토큰은 같은 시크릿으로 재서명한다(core/security.py).
    jwt_secret: str = "dev-secret-change-me"
    jwt_expire_minutes: int = 180

    frontend_url: str = "http://localhost:3000"

    # dummy | backend — 사용자 맥락을 더미로 줄지 실제 백엔드에서 가져올지.
    user_context_source: str = "dummy"
    login_service_url: str = "http://localhost:8000"
    main_service_url: str = "http://localhost:8010"

    bedrock_region: str = "us-east-1"
    bedrock_model_id: str = ""

    # 챗봇 사진 첨부 분석(product_analysis) 전용 - 비용 협의(2026-07-26)로 이
    # 경로만 Bedrock이 아니라 Anthropic API를 직접 호출한다. 일반 텍스트 질의는
    # 여전히 Bedrock(위 bedrock_model_id)을 쓴다 - 이 키는 사진 분석에만 쓰인다.
    # (식사 사진 분석과는 별개다 - 그쪽은 zero-db Vision worker 파이프라인만 쓴다.)
    # 비어있으면 사진 분석은 "준비 중" 안내로 폴백한다(기존 무비용 폴백과 동일 패턴).
    anthropic_api_key: str = ""

    # Cohere Embed v4 리전 — 상품벡터를 만든 기존 파이프라인과 동일(ap-northeast-2).
    embed_region: str = "ap-northeast-2"
    # pgvector 연결이 준비됐을 때만 실제 Retriever 사용. 기본은 NullRetriever(폴백).
    rag_enabled: bool = False

    # 챗봇 사진 첨부(product_analysis) 원본을 감사·재현 목적으로 24시간만
    # 보관한다 - 대화 메모리(conversation_ttl_seconds)와 같은 수명. Vision 분석
    # 자체엔 필요 없다(Anthropic API에 바이트를 직접 보낸다) - 그래서 비어있으면
    # 저장만 건너뛰고 분석 기능은 그대로 동작한다.
    minio_endpoint: str = ""
    minio_access_key: str = ""
    minio_secret_key: str = ""
    minio_bucket: str = "chat-photos"

    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "test_db"
    postgres_user: str = ""
    postgres_password: str = ""

    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: str = ""
    # 타임아웃 필수 — 없으면 Redis 연결 실패 시 요청이 무한정 멈춘다
    # (login-service PRODUCTION_HANDOFF P0-1 이력). best-effort 폴백의 전제.
    redis_connect_timeout_seconds: float = 3.0
    redis_socket_timeout_seconds: float = 3.0
    conversation_ttl_seconds: int = 86400  # 24h, 대화 시마다 갱신

    @property
    def database_url(self) -> str:
        user = quote_plus(self.postgres_user)
        password = quote_plus(self.postgres_password)
        return f"postgresql+asyncpg://{user}:{password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"


settings = Settings()
