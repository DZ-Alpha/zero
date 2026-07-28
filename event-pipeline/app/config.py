from __future__ import annotations

import os
from dataclasses import dataclass


def _required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"required environment variable is missing: {name}")
    return value


@dataclass(frozen=True)
class Settings:
    database_url: str
    kafka_bootstrap_servers: str
    kafka_consumer_group: str
    minio_endpoint: str
    minio_access_key: str
    minio_secret_key: str
    minio_secure: bool
    minio_bucket: str
    minio_public_endpoint: str
    request_topic: str
    completed_topic: str
    failed_topic: str
    processor_version: str
    outbox_poll_seconds: float
    outbox_retention_days: int
    outbox_cleanup_interval_seconds: float
    db_pool_min_size: int
    db_pool_max_size: int
    db_pool_timeout_seconds: float
    vision_provider: str
    vision_timeout_seconds: float
    vision_max_image_bytes: int
    vision_max_attempts: int
    vision_retry_backoff_seconds: float
    gemini_api_key: str | None
    gemini_model: str
    gemini_thinking_budget: int
    gemini_max_output_tokens: int
    foodlens_api_url: str | None
    foodlens_token: str | None
    foodlens_token_header: str
    foodlens_token_prefix: str
    foodlens_image_field: str
    vision_confidence_threshold: float
    activity_topic: str
    zero_database_url: str | None
    zero_outbox_poll_seconds: float
    zero_outbox_max_publish_attempts: int
    activity_consumer_group: str
    mongodb_uri: str | None
    activity_mongodb_database: str
    activity_mongodb_collection: str


def load_settings() -> Settings:
    return Settings(
        database_url=_required("DATABASE_URL"),
        kafka_bootstrap_servers=_required("KAFKA_BOOTSTRAP_SERVERS"),
        kafka_consumer_group=os.getenv("KAFKA_CONSUMER_GROUP", "dangdang-vision-worker-v1"),
        minio_endpoint=_required("MINIO_ENDPOINT"),
        minio_access_key=_required("MINIO_ACCESS_KEY"),
        minio_secret_key=_required("MINIO_SECRET_KEY"),
        minio_secure=os.getenv("MINIO_SECURE", "false").lower() == "true",
        minio_bucket=os.getenv("MINIO_BUCKET", "diet-photos"),
        minio_public_endpoint=os.getenv("MINIO_PUBLIC_ENDPOINT", "http://10.10.20.10:9000"),
        request_topic=os.getenv("REQUEST_TOPIC", "diet.photo.requested"),
        completed_topic=os.getenv("COMPLETED_TOPIC", "diet.photo.completed"),
        failed_topic=os.getenv("FAILED_TOPIC", "diet.photo.failed"),
        processor_version=os.getenv("PROCESSOR_VERSION", "stub-v1"),
        outbox_poll_seconds=float(os.getenv("OUTBOX_POLL_SECONDS", "0.5")),
        outbox_retention_days=int(os.getenv("OUTBOX_RETENTION_DAYS", "30")),
        outbox_cleanup_interval_seconds=float(os.getenv("OUTBOX_CLEANUP_INTERVAL_SECONDS", "3600")),
        db_pool_min_size=int(os.getenv("DB_POOL_MIN_SIZE", "1")),
        db_pool_max_size=int(os.getenv("DB_POOL_MAX_SIZE", "8")),
        db_pool_timeout_seconds=float(os.getenv("DB_POOL_TIMEOUT_SECONDS", "20")),
        vision_provider=os.getenv("VISION_PROVIDER", "stub"),
        vision_timeout_seconds=float(os.getenv("VISION_TIMEOUT_SECONDS", "30")),
        vision_max_image_bytes=int(os.getenv("VISION_MAX_IMAGE_BYTES", str(10 * 1024 * 1024))),
        vision_max_attempts=max(1, int(os.getenv("VISION_MAX_ATTEMPTS", "3"))),
        vision_retry_backoff_seconds=float(os.getenv("VISION_RETRY_BACKOFF_SECONDS", "2")),
        gemini_api_key=os.getenv("GEMINI_API_KEY"),
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-flash-latest"),
        gemini_thinking_budget=int(os.getenv("GEMINI_THINKING_BUDGET", "512")),
        gemini_max_output_tokens=int(os.getenv("GEMINI_MAX_OUTPUT_TOKENS", "4096")),
        foodlens_api_url=os.getenv("FOODLENS_API_URL"),
        foodlens_token=os.getenv("FOODLENS_TOKEN"),
        foodlens_token_header=os.getenv("FOODLENS_TOKEN_HEADER", "Authorization"),
        foodlens_token_prefix=os.getenv("FOODLENS_TOKEN_PREFIX", "Bearer "),
        foodlens_image_field=os.getenv("FOODLENS_IMAGE_FIELD", "image"),
        vision_confidence_threshold=float(os.getenv("VISION_CONFIDENCE_THRESHOLD", "0.75")),
        activity_topic=os.getenv("ACTIVITY_TOPIC", "user.activity.raw"),
        zero_database_url=os.getenv("ZERO_DATABASE_URL"),
        zero_outbox_poll_seconds=float(os.getenv("ZERO_OUTBOX_POLL_SECONDS", "0.5")),
        zero_outbox_max_publish_attempts=int(os.getenv("ZERO_OUTBOX_MAX_PUBLISH_ATTEMPTS", "50")),
        activity_consumer_group=os.getenv("ACTIVITY_CONSUMER_GROUP", "dangdang-activity-mongodb-v1"),
        mongodb_uri=os.getenv("MONGODB_URI"),
        activity_mongodb_database=os.getenv("ACTIVITY_MONGODB_DATABASE", "dangdang_analytics"),
        activity_mongodb_collection=os.getenv("ACTIVITY_MONGODB_COLLECTION", "user_activity_events"),
    )
