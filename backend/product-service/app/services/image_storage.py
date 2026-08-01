"""상품 이미지 자체 호스팅 — 외부 이미지 URL을 우리 MinIO(product-images 버킷,
공개 read)로 옮기고 /b/product-images/{key} 경로를 돌려준다.

diet-service/app/services/storage.py 패턴을 따르되, 상품 이미지는 공개
카탈로그라 presigned 없이 공개 버킷 고정 URL을 쓴다.
"""
import logging
import uuid

import httpx
import boto3
from botocore.config import Config

from app.core.config import settings

logger = logging.getLogger("product_service.image_storage")

SELF_HOSTED_PREFIX = "/b/product-images/"

_CONTENT_TYPE_EXT = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}


def is_self_hosted(image_url: str | None) -> bool:
    """이미 우리 MinIO 경로면 True — 백필 재실행/중복 저장 방지(멱등)."""
    return bool(image_url) and image_url.startswith(SELF_HOSTED_PREFIX)


def extension_for_content_type(content_type: str) -> str | None:
    """Content-Type 헤더 → 확장자. 미지원이면 None. 'image/jpeg; charset=..'
    처럼 파라미터가 붙어와도 앞부분만 본다."""
    main = content_type.split(";", 1)[0].strip().lower()
    return _CONTENT_TYPE_EXT.get(main)


def build_object_key(extension: str, *, key_uuid: str | None = None) -> str:
    """product-images/{uuid}.{ext} object key 생성."""
    key_uuid = key_uuid or str(uuid.uuid4())
    return f"product-images/{key_uuid}.{extension}"


def public_path_for_key(object_key: str) -> str:
    """object key → 브라우저가 쓸 경로(/b 프록시 경유, 공개 버킷)."""
    return f"/b/{object_key}"


MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10MB — diet 업로드 상한과 동일


def _is_configured() -> bool:
    return bool(settings.minio_endpoint and settings.minio_access_key and settings.minio_secret_key)


# boto3 Client는(Session과 달리) 스레드 세이프해서 재사용해도 된다 - AWS 공식
# 권장 패턴. diet-service/app/services/storage.py와 같은 이유로 캐시한다:
# 매 호출마다 새로 만들면 botocore가 서비스 모델을 다시 파싱하는 CPU 낭비가
# 반복된다(2026-07-31 diet-svc 부하테스트 사고 원인 중 하나).
_cached_s3_client = None


def _s3_client():
    global _cached_s3_client
    if _cached_s3_client is None:
        _cached_s3_client = boto3.client(
            "s3",
            endpoint_url=settings.minio_endpoint,
            aws_access_key_id=settings.minio_access_key,
            aws_secret_access_key=settings.minio_secret_key,
            config=Config(signature_version="s3v4"),
        )
    return _cached_s3_client


def _download(image_url: str) -> tuple[str, bytes]:
    """외부 이미지 다운로드 → (content_type, data). 실패 시 예외를 올린다.
    10MB를 넘으면 예외(대용량/오응답 방지)."""
    headers = {"User-Agent": "Mozilla/5.0 (compatible; ZeroBot/1.0; +https://zerodang.org)"}
    with httpx.Client(timeout=15.0, follow_redirects=True, headers=headers) as client:
        with client.stream("GET", image_url) as resp:
            resp.raise_for_status()
            content_type = resp.headers.get("content-type", "")
            declared = resp.headers.get("content-length")
            if declared is not None and declared.isdigit() and int(declared) > MAX_IMAGE_BYTES:
                raise ValueError(f"이미지가 너무 큽니다(Content-Length): {declared} bytes")
            chunks: list[bytes] = []
            total = 0
            for chunk in resp.iter_bytes():
                total += len(chunk)
                if total > MAX_IMAGE_BYTES:
                    raise ValueError(f"이미지가 너무 큽니다: {total}+ bytes")
                chunks.append(chunk)
            return content_type, b"".join(chunks)


def store_external_image(image_url: str | None) -> str | None:
    """외부 이미지 URL을 product-images 버킷에 저장하고 /b/product-images/{key}를
    반환한다. 이미 self-hosted면 그대로 반환. 어떤 이유로든 실패하면 None을
    돌려주고(로그만) — 호출부가 원본 URL을 유지하게 한다."""
    if not image_url:
        return None
    if is_self_hosted(image_url):
        return image_url
    if not _is_configured():
        logger.warning("MinIO 미설정 — 이미지 자체 호스팅 건너뜀: %s", image_url)
        return None

    try:
        content_type, data = _download(image_url)
    except Exception as error:  # noqa: BLE001 — 다운로드는 어떤 예외든 원본 유지로 흡수
        logger.warning("이미지 다운로드 실패(%s): %s", image_url, error)
        return None

    extension = extension_for_content_type(content_type)
    if extension is None:
        logger.warning("지원하지 않는 이미지 형식(%s): %s", content_type, image_url)
        return None

    object_key = build_object_key(extension)
    try:
        _s3_client().put_object(
            Bucket=settings.minio_product_bucket,
            Key=object_key,
            Body=data,
            ContentType=f"image/{'jpeg' if extension == 'jpg' else extension}",
        )
    except Exception as error:  # noqa: BLE001 — 업로드/클라이언트 생성의 어떤 예외든 원본 유지로 흡수
        logger.warning("MinIO 업로드 실패(%s): %s", image_url, error)
        return None

    return public_path_for_key(object_key)
