import asyncio
import logging
import uuid

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import settings

logger = logging.getLogger("ai_service.chat_photo_storage")

_EXTENSIONS = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/gif": "gif",
}

# 대화 메모리(ConversationStore, conversation_ttl_seconds)와 같은 24시간만
# 보관한다 - 감사·재현용일 뿐 분석에는 필요 없다(Bedrock에는 바이트를 직접
# 보낸다). 실제 삭제는 버킷 lifecycle 규칙이 하루 단위 배치로 처리하므로,
# "정확히 업로드 후 24시간"이 아니라 "생성일 다음 만료 주기"에 지워진다 -
# S3/MinIO lifecycle이 시간 단위가 아닌 날짜 단위 TTL만 지원하는 태생적 한계.
_EXPIRATION_DAYS = 1


def _configured() -> bool:
    return bool(settings.minio_endpoint and settings.minio_access_key and settings.minio_secret_key)


def _client():
    return boto3.client(
        "s3",
        endpoint_url=settings.minio_endpoint,
        aws_access_key_id=settings.minio_access_key,
        aws_secret_access_key=settings.minio_secret_key,
        config=Config(signature_version="s3v4"),
    )


def _ensure_lifecycle_sync() -> None:
    _client().put_bucket_lifecycle_configuration(
        Bucket=settings.minio_bucket,
        LifecycleConfiguration={
            "Rules": [{
                "ID": "expire-chat-photos-24h",
                "Status": "Enabled",
                "Filter": {"Prefix": ""},
                "Expiration": {"Days": _EXPIRATION_DAYS},
            }],
        },
    )


async def ensure_lifecycle() -> None:
    """서비스 기동 시 1회 호출 - 버킷에 24시간(하루) 만료 규칙이 있는지 보장한다.
    MinIO/버킷이 아직 준비 안 됐어도 부가 기능이라 서비스 기동 자체는 막지 않는다."""
    if not _configured():
        return
    try:
        await asyncio.to_thread(_ensure_lifecycle_sync)
    except (BotoCoreError, ClientError):
        logger.warning(
            "chat photo 버킷 lifecycle 설정 실패 - 사진 저장은 계속되지만 자동 만료가 안 걸릴 수 있다",
            exc_info=True,
        )


def _store_sync(object_key: str, media_type: str, image_bytes: bytes) -> None:
    _client().put_object(
        Bucket=settings.minio_bucket,
        Key=object_key,
        Body=image_bytes,
        ContentType=media_type,
    )


async def store_best_effort(user_id: int, media_type: str, image_bytes: bytes) -> None:
    """챗봇에 첨부된 사진 원본을 감사·재현 목적으로 저장한다. 분석 결과와는
    무관한 부가 기능이라, 저장에 실패해도 챗봇 응답 자체는 막지 않는다."""
    if not _configured():
        return
    extension = _EXTENSIONS.get(media_type)
    if extension is None:
        return
    object_key = f"{user_id}/{uuid.uuid4()}.{extension}"
    try:
        await asyncio.to_thread(_store_sync, object_key, media_type, image_bytes)
    except (BotoCoreError, ClientError):
        logger.warning("chat photo 저장 실패: user_id=%s", user_id, exc_info=True)
