from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    environment: str = "development"
    log_level: str = "INFO"
    otel_exporter_endpoint: str = "http://192.168.0.51:4317"


settings = Settings()
