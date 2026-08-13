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
    # 기본은 꺼둔다(깜빡하고 안 켜는 실수가 "그래도 안전한" 쪽이 되도록) - 로컬
    # 개발은 .env.example의 ENABLE_API_DOCS=true로 켜져 있다.
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

    product_service_url: str = "http://localhost:8016"

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
