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
    # presigned GET URL은 서명에 host가 포함돼서(V4 SignedHeaders=host), 발급
    # 시 쓴 endpoint_url의 호스트가 그대로 URL에 박힌다 - minio_endpoint는
    # 서버간 통신용 내부 주소(예: http://10.10.20.10:9000)라 브라우저가
    # 못 여는 문제가 있었다(실사용 중 재현). 브라우저가 실제로 열 수 있는
    # 공개 주소로 별도로 서명해야 하고, 이 값은 게이트웨이(infra/b-gateway
    # /nginx.conf)의 /b/diet-photos 라우트와 짝이 맞아야 한다. 비어있으면
    # minio_endpoint로 폴백한다(기존 동작 유지, 여전히 내부 IP로 서명됨).
    minio_public_endpoint: str = ""

    # 개발팀 요청서 정정 1(2026-07-20) — worker는 HTTP callback을 호출하지 않고
    # diet.photo.completed/diet.photo.failed를 Kafka로 발행한다. diet-service가
    # 전용 consumer group으로 직접 구독한다 (app/services/vision_consumer.py).
    # 비어있으면 컨슈머를 시작하지 않는다.
    kafka_brokers: str = ""
    kafka_consumer_group: str = "diet-service"

    # 얌로그(rooms) 연동용 — community-service가 서버간 호출로 사용자·날짜·
    # 끼니별 식단을 조회하는 GET /diet/internal/meal-records의 인증. 이 값이
    # 비어있으면 그 엔드포인트는 항상 403을 반환한다(공백 값으로 "누구나 통과"가
    # 되는 사고를 막기 위해 명시적으로 막아둠 — admin_signup_secret과 같은 패턴).
    # community-service의 동일 이름 설정과 값이 같아야 한다.
    internal_service_secret: str = ""

    # 얌로그(rooms) 연동용 — 식단 기록이 실제로 완료되는 시점에(Vision 분석
    # 완료/사용자 확정/레시피·저당픽 직접 등록) community-service의
    # POST /rooms/internal/meal-recorded를 호출해, 그 유저가 속한 방들의 오늘
    # 스레드를 즉시 만든다(room_meal_thread가 방 화면을 열어봐야만 생기던
    # 문제 해결 - app/services/room_notify.py 참고).
    community_service_url: str = "http://community-service:8012"

    @property
    def database_url(self) -> str:
        user = quote_plus(self.postgres_user)
        password = quote_plus(self.postgres_password)
        return f"postgresql+asyncpg://{user}:{password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"


settings = Settings()
