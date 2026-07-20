import uuid

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import settings


class StorageNotConfiguredError(Exception):
    pass


class StorageUploadError(Exception):
    pass


_ALLOWED_CONTENT_TYPES = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}


def _client():
    if not (settings.minio_endpoint and settings.minio_access_key and settings.minio_secret_key):
        raise StorageNotConfiguredError("MINIO_ENDPOINT/MINIO_ACCESS_KEY/MINIO_SECRET_KEY가 설정되지 않았습니다.")
    return boto3.client(
        "s3",
        endpoint_url=settings.minio_endpoint,
        aws_access_key_id=settings.minio_access_key,
        aws_secret_access_key=settings.minio_secret_key,
        config=Config(signature_version="s3v4"),
    )


def upload_diet_photo(user_id: int, content_type: str, data: bytes) -> str:
    """diet-photos 버킷에 업로드하고 object_key를 반환한다.

    object_key는 항상 diet-photos/{user_id}/... 형태로 생성한다 — 이 접두사가
    /diet/upload에서 소유자 검증 기준이 된다(다른 사용자의 object_key를 대신
    제출해도 통과하지 못하도록).
    """
    extension = _ALLOWED_CONTENT_TYPES.get(content_type)
    if extension is None:
        raise StorageUploadError(f"지원하지 않는 이미지 형식입니다: {content_type}")

    object_key = f"diet-photos/{user_id}/{uuid.uuid4()}.{extension}"

    try:
        _client().put_object(
            Bucket=settings.minio_bucket,
            Key=object_key,
            Body=data,
            ContentType=content_type,
        )
    except (BotoCoreError, ClientError) as error:
        raise StorageUploadError(f"이미지 업로드에 실패했습니다: {error}") from error

    return object_key


def validate_diet_photo_key(object_key: str, user_id: int) -> str:
    """diet-service /diet/upload가 받은 object_key가 이 사용자 소유인지 확인.

    남의 object_key를 body에 대신 넣어 제출하는 걸 막는다 — upload_diet_photo가
    항상 diet-photos/{user_id}/... 형태로만 키를 만들기 때문에, 접두사 검증만
    으로 충분하다(실제 존재 여부까지는 확인하지 않음 — worker가 못 읽으면
    분석 단계에서 FAILED로 자연히 드러난다).
    """
    expected_prefix = f"diet-photos/{user_id}/"
    if not object_key.startswith(expected_prefix):
        raise StorageUploadError("본인이 업로드한 사진의 object_key가 아닙니다.")
    return object_key
