from urllib.parse import quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

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
