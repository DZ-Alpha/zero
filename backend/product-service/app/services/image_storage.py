"""상품 이미지 자체 호스팅 — 외부 이미지 URL을 우리 MinIO(product-images 버킷,
공개 read)로 옮기고 /b/product-images/{key} 경로를 돌려준다.

diet-service/app/services/storage.py 패턴을 따르되, 상품 이미지는 공개
카탈로그라 presigned 없이 공개 버킷 고정 URL을 쓴다.
"""
import logging
import uuid

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
