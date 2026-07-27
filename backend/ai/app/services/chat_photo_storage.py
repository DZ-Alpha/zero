import asyncio
import logging
import uuid
from urllib.parse import urlsplit

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


async def store_best_effort(user_id: int, media_type: str, image_bytes: bytes) -> str | None:
    """챗봇에 첨부된 사진 원본을 MinIO에 저장하고 object_key를 반환한다.
    부가 기능이라 저장에 실패하면 None을 반환하고 챗봇 응답은 막지 않는다."""
    if not _configured():
        return None
    extension = _EXTENSIONS.get(media_type)
    if extension is None:
        return None
    object_key = f"{user_id}/{uuid.uuid4()}.{extension}"
    try:
        await asyncio.to_thread(_store_sync, object_key, media_type, image_bytes)
    except (BotoCoreError, ClientError):
        logger.warning("chat photo 저장 실패: user_id=%s", user_id, exc_info=True)
        return None
    return object_key


def presign_chat_photo_url(object_key: str, expires_in: int = 300) -> str | None:
    """복원 시 사진을 브라우저에 보여주기 위한 서명 URL. diet-service의
    presign_diet_photo_url과 동일 패턴 - 내부 endpoint로 서명하되 경로+쿼리만
    떼어 "/b" 붙인 상대경로로 내려준다(프론트 app/b/[...path] 프록시가 중계).
    경로를 바꾸면 SigV4 서명이 깨지므로 경로를 건드리지 않는다.
    부가 기능이라 실패하면 None(호출 측이 imageUrl 없이 진행)."""
    if not _configured():
        return None
    try:
        raw = _client().generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.minio_bucket, "Key": object_key},
            ExpiresIn=expires_in,
        )
    except (BotoCoreError, ClientError):
        logger.warning("chat photo presign 실패: key=%s", object_key, exc_info=True)
        return None
    parsed = urlsplit(raw)
    return f"/b{parsed.path}?{parsed.query}"
