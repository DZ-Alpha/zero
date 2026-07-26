import uuid
from urllib.parse import urlsplit

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


def _client(endpoint_url: str | None = None):
    if not (settings.minio_endpoint and settings.minio_access_key and settings.minio_secret_key):
        raise StorageNotConfiguredError("MINIO_ENDPOINT/MINIO_ACCESS_KEY/MINIO_SECRET_KEY가 설정되지 않았습니다.")
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url or settings.minio_endpoint,
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


def presign_diet_photo_url(object_key: str, expires_in: int = 300) -> str:
    """얌로그(rooms)가 다른 사용자의 식단 사진을 보여줄 때 쓴다 — 버킷이
    비공개라 object_key를 그대로 내려주면 브라우저가 못 연다. 짧은 만료
    시간의 서명 URL로 매 요청 새로 발급한다(캐시 안 함 — room_meal_threads.md
    설계 메모의 "짧은 만료 signed URL" 요구사항과 일치).

    항상 minio_endpoint(내부 주소)로 서명한다 - 이 URL을 브라우저에 그대로
    내려주지 않고, 경로+쿼리만 떼어 "/b"를 붙인 상대경로로 내려준다
    (프론트의 app/b/[...path]/route.ts가 이 요청을 서버사이드(Node fetch)로
    받아 MINIO_URL로 그대로 중계한다). SigV4 서명은 host와 경로 전체를
    포함하므로(SignedHeaders=host), 중간에 경로를 한 글자라도 바꾸면
    (예: b-gateway/nginx의 "/b" rewrite) 서명이 깨진다(실사용 중 재현된
    SignatureDoesNotMatch 버그) - 그래서 경로를 안 건드리는 이 프론트
    프록시로만 내보낸다."""
    raw = _client().generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.minio_bucket, "Key": object_key},
        ExpiresIn=expires_in,
    )
    parsed = urlsplit(raw)
    return f"/b{parsed.path}?{parsed.query}"


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
