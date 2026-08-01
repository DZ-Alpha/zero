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
    # Must match login-service's JWT_EXPIRE_MINUTES — used when reissuing a
    # refreshed token so the sliding-session lifetime is consistent everywhere.
    jwt_expire_minutes: int = 180

    frontend_url: str = "http://localhost:3000"


settings = Settings()
