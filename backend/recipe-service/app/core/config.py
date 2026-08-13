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

    frontend_url: str = "http://localhost:3000"

    # Same Postgres instance as the other services. This service owns NO
    # tables — recipes/recipe_ingredients/recipe_ingredient_products/
    # raw_ingredient_nutrients are all populated by the data team's YouTube
    # recipe pipeline (receipe_spec_v0.4.xlsx). This app only ever SELECTs
    # from the `service` schema, never DDL.
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "test_db"
    postgres_user: str = ""
    postgres_password: str = ""

    # RC-0111/0112(찜) 전용 — 이 서비스가 처음 인증을 다루는 기능이라 새로 추가.
    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 180

    @property
    def database_url(self) -> str:
        user = quote_plus(self.postgres_user)
        password = quote_plus(self.postgres_password)
        return f"postgresql+asyncpg://{user}:{password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"


settings = Settings()
