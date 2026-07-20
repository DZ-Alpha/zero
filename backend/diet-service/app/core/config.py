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

    product_service_url: str = "http://localhost:8016"

    # RC-0103 동기 분석 경로(PRODUCTION_HANDOFF.md P0-3) — GET /diet/ai-analyze가
    # Claude Vision을 직접 호출한다. 비어있으면 기존처럼 PREPARING을 반환한다
    # (app/services/vision_service.py).
    anthropic_api_key: str = ""

    # zero-db 이벤트 파이프라인(Kafka/MinIO/Vision worker, 2026-07-20) 연동용 —
    # POST /uploads/diet-photo 경로. 비어있으면 사진 업로드 엔드포인트는 501을
    # 반환한다 — 값이 없는 채로 MinIO를 그냥 통과시키면 잘못된 요청을 조용히
    # 받아버리게 된다.
    minio_endpoint: str = ""
    minio_access_key: str = ""
    minio_secret_key: str = ""
    minio_bucket: str = "diet-photos"

    # 개발팀 요청서 정정 1(2026-07-20) — worker는 HTTP callback을 호출하지 않고
    # diet.photo.completed/diet.photo.failed를 Kafka로 발행한다. diet-service가
    # 전용 consumer group으로 직접 구독한다 (app/services/vision_consumer.py).
    # 비어있으면 컨슈머를 시작하지 않는다.
    kafka_brokers: str = ""
    kafka_consumer_group: str = "diet-service"

    @property
    def database_url(self) -> str:
        user = quote_plus(self.postgres_user)
        password = quote_plus(self.postgres_password)
        return f"postgresql+asyncpg://{user}:{password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"


settings = Settings()
