# 상품 이미지 MinIO 자체 호스팅 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 상품 썸네일을 외부 핫링크 대신 우리 MinIO(공개 버킷 `product-images`)에 저장·서빙해, 원본 사이트가 이미지를 내려도 깨지지 않게 한다.

**Architecture:** product-service에 이미지 스토리지 모듈(boto3, 이미 의존성 있음)을 추가한다. 외부 URL을 받아 다운로드→content-type 검증→`product-images/{uuid}.{ext}`로 put_object→`/b/product-images/{key}` 경로 반환. 1회성 백필 스크립트가 기존 `products.image_url`을 이 경로로 UPDATE하고, admin 상품 등록/수정도 같은 모듈을 거치게 훅한다. 프론트 프록시(`app/b/[...path]`)에 `product-images` 분기를 추가해 MinIO로 중계한다.

**Tech Stack:** Python 3 / FastAPI / SQLAlchemy async / boto3 (S3 호환 MinIO) / httpx (다운로드) — boto3·httpx 모두 product-service에 이미 설치됨. 프론트: Next.js 16 route handler.

## Global Constraints

- 대상은 **상품만** (레시피 이미지는 범위 밖).
- 버킷 `product-images`는 **공개(public-read)** 전제 — presigned 안 씀. 버킷 생성·정책은 팀(인프라) 몫이며 이 계획의 코드는 그 전제 위에서 동작한다.
- DB `image_url` 새 값 형식: **`/b/product-images/{uuid}.{ext}`** (앞에 슬래시 포함).
- content-type 화이트리스트: `image/jpeg`→`jpg`, `image/png`→`png`, `image/webp`→`webp`. 그 외는 저장하지 않고 원본 URL 유지.
- MinIO 자격증명은 **환경변수**: `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, 버킷명 `MINIO_PRODUCT_BUCKET`(기본 `product-images`). 코드에 값 하드코딩 금지.
- 멱등: 이미 `/b/product-images/`로 시작하는 image_url은 재처리하지 않는다.
- 실패(다운로드 404/타임아웃/미지원 형식/MinIO 오류)는 **원본 URL 유지 + 로그**, 절대 예외로 상품 등록·백필을 중단시키지 않는다.
- product-service에는 기존 테스트·conftest가 없다. 이 계획이 `pytest`/`pytest-asyncio`를 dev 의존성으로 추가하고, MinIO·DB·네트워크 없이 도는 순수/mock 단위 테스트만 쓴다.

---

## File Structure

- `backend/product-service/app/core/config.py` (수정) — MinIO 설정 4개 추가.
- `backend/product-service/app/services/image_storage.py` (신규) — 이미지 다운로드·업로드·경로 판별. 순수 헬퍼 + boto3/httpx I/O.
- `backend/product-service/app/routers/admin.py` (수정) — 상품 등록/수정 시 image_url을 스토리지 모듈에 통과.
- `backend/product-service/scripts/backfill_product_images.py` (신규) — 1회성 백필(멱등, dry-run 지원).
- `backend/product-service/tests/test_image_storage.py` (신규) — 스토리지 순수 헬퍼 단위 테스트.
- `backend/product-service/requirements-dev.txt` (신규) — pytest, pytest-asyncio.
- `frontend/app/b/[...path]/route.ts` (수정) — `product-images` 프록시 분기.
- `docs/ops/product-images-minio-runbook.md` (신규) — 인프라 실행 가이드(팀이 복붙 실행).

---

## Task 1: MinIO 설정 추가 (config)

**Files:**
- Modify: `backend/product-service/app/core/config.py`

**Interfaces:**
- Produces: `settings.minio_endpoint: str`, `settings.minio_access_key: str`, `settings.minio_secret_key: str`, `settings.minio_product_bucket: str` (기본 `"product-images"`).

- [ ] **Step 1: 설정 필드 추가**

`backend/product-service/app/core/config.py`의 `Settings` 클래스에 `ai_provider`/`bedrock_*` 블록 아래, `database_url` property 위에 추가:

```python
    # 상품 이미지 자체 호스팅(MinIO). diet-service와 같은 MinIO를 쓰되 버킷만
    # 다르다(product-images, 공개 read). 비어있으면 이미지 저장을 시도하지 않고
    # 원본 URL을 그대로 둔다 — 잘못된 설정으로 조용히 실패하지 않도록.
    minio_endpoint: str = ""
    minio_access_key: str = ""
    minio_secret_key: str = ""
    minio_product_bucket: str = "product-images"
```

- [ ] **Step 2: import 검증 (문법)**

Run: `cd backend/product-service && python -c "from app.core.config import settings; print(settings.minio_product_bucket)"`
Expected: `product-images` 출력 (에러 없음)

- [ ] **Step 3: Commit**

```bash
git add backend/product-service/app/core/config.py
git commit -m "feat(product): MinIO 상품 이미지 버킷 설정 추가"
```

---

## Task 2: 이미지 스토리지 모듈 — 순수 헬퍼 + 테스트

이 태스크는 네트워크·MinIO 없이 테스트 가능한 **순수 함수**만 먼저 만든다: 이미 우리 경로인지 판별, content-type→확장자 매핑, object key/공개경로 생성. boto3/httpx I/O는 Task 3에서.

**Files:**
- Create: `backend/product-service/app/services/image_storage.py`
- Create: `backend/product-service/requirements-dev.txt`
- Create: `backend/product-service/tests/__init__.py`
- Create: `backend/product-service/tests/test_image_storage.py`

**Interfaces:**
- Produces:
  - `SELF_HOSTED_PREFIX: str = "/b/product-images/"`
  - `is_self_hosted(image_url: str | None) -> bool` — 이미 우리 경로면 True.
  - `extension_for_content_type(content_type: str) -> str | None` — jpg/png/webp, 아니면 None (파라미터의 `;charset` 등 꼬리표 무시).
  - `build_object_key(extension: str, *, key_uuid: str) -> str` — `f"product-images/{key_uuid}.{extension}"`. (uuid를 인자로 받아 테스트 가능하게)
  - `public_path_for_key(object_key: str) -> str` — `f"/b/{object_key}"`.

- [ ] **Step 1: dev 의존성 파일 생성**

Create `backend/product-service/requirements-dev.txt`:

```
pytest==8.3.4
pytest-asyncio==0.25.2
```

- [ ] **Step 2: dev 의존성 설치**

Run: `cd backend/product-service && python -m pip install -r requirements-dev.txt`
Expected: pytest 설치 성공

- [ ] **Step 3: 실패하는 테스트 작성**

Create `backend/product-service/tests/__init__.py` (빈 파일).

Create `backend/product-service/tests/test_image_storage.py`:

```python
from app.services import image_storage as st


def test_is_self_hosted_true_for_our_prefix():
    assert st.is_self_hosted("/b/product-images/abc.jpg") is True


def test_is_self_hosted_false_for_external_url():
    assert st.is_self_hosted("https://example.com/x.jpg") is False


def test_is_self_hosted_false_for_none():
    assert st.is_self_hosted(None) is False


def test_extension_for_content_type_maps_known_types():
    assert st.extension_for_content_type("image/jpeg") == "jpg"
    assert st.extension_for_content_type("image/png") == "png"
    assert st.extension_for_content_type("image/webp") == "webp"


def test_extension_for_content_type_ignores_charset_suffix():
    assert st.extension_for_content_type("image/jpeg; charset=binary") == "jpg"


def test_extension_for_content_type_unknown_returns_none():
    assert st.extension_for_content_type("image/gif") is None
    assert st.extension_for_content_type("text/html") is None


def test_build_object_key():
    assert st.build_object_key("jpg", key_uuid="1234") == "product-images/1234.jpg"


def test_public_path_for_key():
    assert st.public_path_for_key("product-images/1234.jpg") == "/b/product-images/1234.jpg"
```

- [ ] **Step 4: 테스트 실패 확인**

Run: `cd backend/product-service && python -m pytest tests/test_image_storage.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.image_storage'`

- [ ] **Step 5: 순수 헬퍼 구현**

Create `backend/product-service/app/services/image_storage.py`:

```python
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
```

- [ ] **Step 6: 테스트 통과 확인**

Run: `cd backend/product-service && python -m pytest tests/test_image_storage.py -v`
Expected: PASS (8 passed)

- [ ] **Step 7: Commit**

```bash
git add backend/product-service/app/services/image_storage.py backend/product-service/tests backend/product-service/requirements-dev.txt
git commit -m "feat(product): 이미지 스토리지 순수 헬퍼 + 테스트"
```

---

## Task 3: 스토리지 모듈 — 다운로드·업로드 I/O (mock 테스트)

순수 헬퍼 위에 실제 I/O(`store_external_image`)를 얹는다. httpx로 다운로드, boto3로 put_object. 네트워크·MinIO 없이 mock으로 테스트한다.

**Files:**
- Modify: `backend/product-service/app/services/image_storage.py`
- Modify: `backend/product-service/tests/test_image_storage.py`

**Interfaces:**
- Consumes: `is_self_hosted`, `extension_for_content_type`, `build_object_key`, `public_path_for_key` (Task 2), `settings.minio_*` (Task 1).
- Produces: `store_external_image(image_url: str | None) -> str | None` — 성공 시 `/b/product-images/{key}` 반환. 이미 self-hosted면 그 값 그대로. 실패(설정 없음/다운로드 실패/미지원 타입/업로드 실패)면 `None`.
- Produces: `MAX_IMAGE_BYTES: int = 10 * 1024 * 1024`.

- [ ] **Step 1: 실패하는 테스트 추가**

`backend/product-service/tests/test_image_storage.py` 끝에 추가:

```python
from unittest.mock import MagicMock, patch


def test_store_external_image_returns_input_when_already_self_hosted():
    # 이미 우리 경로면 다운로드/업로드 없이 그대로 반환(멱등)
    assert st.store_external_image("/b/product-images/x.jpg") == "/b/product-images/x.jpg"


def test_store_external_image_returns_none_when_not_configured():
    with patch.object(st.settings, "minio_endpoint", ""):
        assert st.store_external_image("https://ext/x.jpg") is None


def test_store_external_image_happy_path_uploads_and_returns_path():
    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_resp.headers = {"content-type": "image/jpeg"}
    fake_resp.content = b"\xff\xd8\xff" + b"0" * 100  # jpeg-ish bytes
    fake_client = MagicMock()
    fake_s3 = MagicMock()

    with patch.object(st.settings, "minio_endpoint", "http://minio:9000"), \
         patch.object(st.settings, "minio_access_key", "k"), \
         patch.object(st.settings, "minio_secret_key", "s"), \
         patch.object(st, "_download", return_value=("image/jpeg", fake_resp.content)), \
         patch.object(st, "_s3_client", return_value=fake_s3), \
         patch.object(st.uuid, "uuid4", return_value="fixed-uuid"):
        result = st.store_external_image("https://ext/x.jpg")

    assert result == "/b/product-images/fixed-uuid.jpg"
    fake_s3.put_object.assert_called_once()
    kwargs = fake_s3.put_object.call_args.kwargs
    assert kwargs["Bucket"] == "product-images"
    assert kwargs["Key"] == "product-images/fixed-uuid.jpg"
    assert kwargs["ContentType"] == "image/jpeg"


def test_store_external_image_returns_none_on_unsupported_type():
    with patch.object(st.settings, "minio_endpoint", "http://minio:9000"), \
         patch.object(st.settings, "minio_access_key", "k"), \
         patch.object(st.settings, "minio_secret_key", "s"), \
         patch.object(st, "_download", return_value=("image/gif", b"gif")):
        assert st.store_external_image("https://ext/x.gif") is None


def test_store_external_image_returns_none_on_download_failure():
    with patch.object(st.settings, "minio_endpoint", "http://minio:9000"), \
         patch.object(st.settings, "minio_access_key", "k"), \
         patch.object(st.settings, "minio_secret_key", "s"), \
         patch.object(st, "_download", side_effect=RuntimeError("boom")):
        assert st.store_external_image("https://ext/x.jpg") is None
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `cd backend/product-service && python -m pytest tests/test_image_storage.py -v`
Expected: FAIL — `AttributeError: module 'app.services.image_storage' has no attribute 'store_external_image'` (또는 `_download`)

- [ ] **Step 3: I/O 구현**

`backend/product-service/app/services/image_storage.py`에 추가 (상단 import에 `httpx`, `boto3`, `Config`, `settings` 추가):

```python
import httpx
import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import settings
```

파일 하단에 추가:

```python
MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10MB — diet 업로드 상한과 동일


def _is_configured() -> bool:
    return bool(settings.minio_endpoint and settings.minio_access_key and settings.minio_secret_key)


def _s3_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.minio_endpoint,
        aws_access_key_id=settings.minio_access_key,
        aws_secret_access_key=settings.minio_secret_key,
        config=Config(signature_version="s3v4"),
    )


def _download(image_url: str) -> tuple[str, bytes]:
    """외부 이미지 다운로드 → (content_type, data). 실패 시 예외를 올린다.
    10MB를 넘으면 예외(대용량/오응답 방지)."""
    with httpx.Client(timeout=15.0, follow_redirects=True) as client:
        resp = client.get(image_url)
        resp.raise_for_status()
        data = resp.content
        if len(data) > MAX_IMAGE_BYTES:
            raise ValueError(f"이미지가 너무 큽니다: {len(data)} bytes")
        content_type = resp.headers.get("content-type", "")
        return content_type, data


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
    except (BotoCoreError, ClientError) as error:
        logger.warning("MinIO 업로드 실패(%s): %s", image_url, error)
        return None

    return public_path_for_key(object_key)
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `cd backend/product-service && python -m pytest tests/test_image_storage.py -v`
Expected: PASS (13 passed)

- [ ] **Step 5: 문법·import 검증**

Run: `cd backend/product-service && python -c "from app.services.image_storage import store_external_image; print('ok')"`
Expected: `ok`

- [ ] **Step 6: Commit**

```bash
git add backend/product-service/app/services/image_storage.py backend/product-service/tests/test_image_storage.py
git commit -m "feat(product): 외부 이미지 다운로드→MinIO 업로드 store_external_image"
```

---

## Task 4: admin 등록/수정 훅

상품 등록/수정 시 입력 image_url을 `store_external_image`로 통과시켜, 성공하면 우리 경로로, 실패하면 원본 URL로 저장한다.

**Files:**
- Modify: `backend/product-service/app/routers/admin.py`

**Interfaces:**
- Consumes: `store_external_image(image_url) -> str | None` (Task 3).

- [ ] **Step 1: import 추가**

`backend/product-service/app/routers/admin.py` 상단 import 블록(`from app.services.product_store import ...` 아래)에 추가:

```python
from app.services.image_storage import store_external_image
```

- [ ] **Step 2: 등록 훅 — `_handle_create_product` 수정**

`_handle_create_product`에서 required 검증 직후, `create_product` 호출 전에 image_url을 치환한다. 아래 블록을 `category_tag_id = _parse_uuid(...)` 줄 **위**에 삽입:

```python
    # 외부 이미지를 우리 MinIO로 옮긴다(공개 버킷). 실패하면 원본 URL을 그대로
    # 쓴다 — 등록 자체는 막지 않는다(나중에 백필로 재시도 가능).
    stored = store_external_image(body["image_url"])
    if stored:
        body = {**body, "image_url": stored}
```

- [ ] **Step 3: 수정 훅 — `_handle_update_product` 수정**

`_handle_update_product`에서 `fields` dict를 만들기 전에, image_url이 들어온 경우에만 치환:

```python
    if body.get("image_url"):
        stored = store_external_image(body["image_url"])
        if stored:
            body = {**body, "image_url": stored}
```

이 블록을 `pid = _parse_uuid(body["id"], "상품 ID")` 줄 **아래**, `fields = {...}` **위**에 삽입.

- [ ] **Step 4: 문법 검증**

Run: `cd backend/product-service && python -m py_compile app/routers/admin.py && echo OK`
Expected: `OK`

- [ ] **Step 5: 훅이 이미 self-hosted 값을 통과시키는지 확인(회귀 방지)**

이미 `/b/product-images/`인 값이 들어오면 `store_external_image`가 그 값을 그대로 반환하므로 재업로드가 없다(Task 3에서 검증). 별도 코드 불필요 — 확인만.

- [ ] **Step 6: Commit**

```bash
git add backend/product-service/app/routers/admin.py
git commit -m "feat(product): admin 상품 등록/수정 시 이미지 MinIO 자체 호스팅"
```

---

## Task 5: 백필 스크립트 (1회성, 멱등, dry-run)

기존 `products.image_url` 중 외부 URL인 것을 다운로드→업로드→UPDATE한다. `--dry-run`, `--limit`, 진행 로그, 실패 건 건너뜀.

**Files:**
- Create: `backend/product-service/scripts/__init__.py`
- Create: `backend/product-service/scripts/backfill_product_images.py`

**Interfaces:**
- Consumes: `store_external_image`, `is_self_hosted` (image_storage), `settings.database_url`.

- [ ] **Step 1: 스크립트 작성**

Create `backend/product-service/scripts/__init__.py` (빈 파일).

Create `backend/product-service/scripts/backfill_product_images.py`:

```python
"""기존 products.image_url(외부 핫링크)을 우리 MinIO로 1회성 백필한다.

멱등: 이미 /b/product-images/ 인 행은 건너뛴다. 실패한 행은 원본 URL을
그대로 두고 계속 진행한다(중단 없음).

실행 전 준비(팀): product-images 버킷 생성 + public-read, product-service에
MINIO_ENDPOINT/ACCESS_KEY/SECRET_KEY env 주입. docs/ops/product-images-minio-runbook.md 참고.

사용:
  python -m scripts.backfill_product_images --dry-run            # 대상만 세어봄
  python -m scripts.backfill_product_images --limit 20           # 20건만
  python -m scripts.backfill_product_images                      # 전체
"""
import argparse
import asyncio
import logging

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.models.product import Product
from app.services.image_storage import is_self_hosted, store_external_image

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("backfill_product_images")


async def run(dry_run: bool, limit: int | None) -> None:
    engine = create_async_engine(settings.database_url)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Session() as session:
        stmt = select(Product.product_id, Product.image_url)
        result = await session.execute(stmt)
        rows = result.all()

    targets = [(pid, url) for pid, url in rows if url and not is_self_hosted(url)]
    logger.info("전체 %d건 중 백필 대상 %d건 (이미 self-hosted: %d건)",
                len(rows), len(targets), len(rows) - len(targets))
    if limit is not None:
        targets = targets[:limit]
        logger.info("--limit %d 적용 → %d건 처리", limit, len(targets))

    if dry_run:
        logger.info("[dry-run] 실제 저장/UPDATE 없이 종료")
        await engine.dispose()
        return

    ok = 0
    failed = 0
    async with Session() as session:
        for i, (pid, url) in enumerate(targets, 1):
            # store_external_image는 blocking(httpx/boto3) — 이벤트 루프 블로킹을
            # 피하려고 스레드로 넘긴다.
            stored = await asyncio.to_thread(store_external_image, url)
            if stored and stored != url:
                await session.execute(
                    update(Product).where(Product.product_id == pid).values(image_url=stored)
                )
                ok += 1
            else:
                failed += 1
                logger.warning("건너뜀(원본 유지) product_id=%s url=%s", pid, url)
            if i % 50 == 0:
                await session.commit()
                logger.info("진행 %d/%d (성공 %d, 실패 %d)", i, len(targets), ok, failed)
        await session.commit()

    logger.info("완료: 성공 %d, 실패(원본 유지) %d, 총 %d", ok, failed, len(targets))
    await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="대상만 세고 저장/UPDATE 안 함")
    parser.add_argument("--limit", type=int, default=None, help="처리할 최대 건수")
    args = parser.parse_args()
    asyncio.run(run(dry_run=args.dry_run, limit=args.limit))


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 문법 검증**

Run: `cd backend/product-service && python -m py_compile scripts/backfill_product_images.py && echo OK`
Expected: `OK`

- [ ] **Step 3: --help 동작 확인 (DB 미접속으로도 argparse는 동작)**

Run: `cd backend/product-service && python -m scripts.backfill_product_images --help`
Expected: usage 출력에 `--dry-run`, `--limit` 표시

- [ ] **Step 4: Commit**

```bash
git add backend/product-service/scripts
git commit -m "feat(product): 상품 이미지 MinIO 백필 스크립트(멱등, dry-run)"
```

---

## Task 6: 프론트 프록시 `product-images` 분기

`/b/product-images/{key}` 요청을 MinIO로 중계한다. diet-photos 분기 바로 옆에 추가하되 서명은 없다(공개 버킷).

**Files:**
- Modify: `frontend/app/b/[...path]/route.ts`

**Interfaces:**
- Consumes: 기존 `minioUrl` 상수(이미 파일에 있음, `process.env.MINIO_URL`).

- [ ] **Step 1: `buildUpstream`에 분기 추가**

`frontend/app/b/[...path]/route.ts`의 `buildUpstream` 함수에서, 기존

```typescript
  if (parts[0] === "diet-photos" && minioUrl) {
    return new URL(`/${encodedPath}`, minioUrl);
  }
```

바로 아래에 추가:

```typescript
  // 상품 이미지는 공개 버킷(product-images)이라 서명 없이 그대로 MinIO로 중계한다
  // (diet-photos는 비공개+presigned지만 이건 공개 read). image_url이
  // /b/product-images/{key}로 저장돼 있어 이 경로로 들어온다.
  if (parts[0] === "product-images" && minioUrl) {
    return new URL(`/${encodedPath}`, minioUrl);
  }
```

- [ ] **Step 2: 타입체크**

Run: `cd frontend && npx tsc --noEmit`
Expected: 에러 없음 (exit 0)

- [ ] **Step 3: Commit**

```bash
git add frontend/app/b/[...path]/route.ts
git commit -m "feat(frontend): /b/product-images 프록시 분기(MinIO 공개 버킷 중계)"
```

---

## Task 7: 인프라 실행 가이드(runbook)

팀이 복붙 실행할 준비물. 코드가 아니라 문서.

**Files:**
- Create: `docs/ops/product-images-minio-runbook.md`

- [ ] **Step 1: runbook 작성**

Create `docs/ops/product-images-minio-runbook.md`:

```markdown
# 상품 이미지 MinIO 자체 호스팅 — 실행 가이드 (인프라/팀)

코드는 `feature/product-images-minio`에 있고, 아래 인프라 준비 후 백필을 실행한다.
설계: docs/superpowers/specs/2026-08-01-product-images-minio-selfhost-design.md

## 1. product-images 버킷 생성 + 공개(read) 정책
MinIO Pod(dang-minio-0)에서 mc alias가 설정된 상태 기준. (자격증명은 팀 보관)

    mc mb local/product-images
    mc anonymous set download local/product-images   # 익명 read 허용(공개)

확인: 서명 없는 GET이 이제 열려야 한다(없는 객체는 404).

## 2. product-service에 MinIO env 주입
diet-service가 이미 쓰는 MinIO 자격증명과 같은 값을 product-service 배포에 넣는다.
필요한 env:
- MINIO_ENDPOINT        (예: http://dang-minio:9000)
- MINIO_ACCESS_KEY
- MINIO_SECRET_KEY
- MINIO_PRODUCT_BUCKET  (기본 product-images, 바꿀 때만)

SealedSecret/차트 참조는 diet-service의 MinIO secret 패턴을 그대로 따른다.
env 변경 후 product-service 파드 rollout restart 필요.

## 3. 프론트 MINIO_URL 확인
프론트 프록시가 /b/product-images/{key}를 MinIO로 보내려면 MINIO_URL이 설정돼
있어야 한다(diet-photos용으로 이미 있을 것 — 없으면 추가). 값은 브라우저가 아닌
frontend 서버(Node)가 접근하는 MinIO 주소.

## 4. 백필 실행
product-service 컨테이너(또는 env가 갖춰진 환경)에서:

    python -m scripts.backfill_product_images --dry-run        # 대상 수 확인
    python -m scripts.backfill_product_images --limit 20       # 소량 검증
    # 검증(아래) 통과 후 전체:
    python -m scripts.backfill_product_images

## 5. 검증
- 소량 백필 후 해당 상품 image_url이 /b/product-images/... 로 바뀌었는지 DB 확인:
    SELECT image_url FROM service.products
    WHERE image_url LIKE '/b/product-images/%' LIMIT 5;
- 앱에서 상품 상세/검색 카드 이미지가 정상 로드되는지(네트워크 탭에서 /b/product-images/ 요청 200).
- 실패 건은 원본 URL 유지 — 로그의 "건너뜀(원본 유지)" 확인.

## 롤백
image_url을 되돌리려면 백필 전 값이 필요하다. 대량 UPDATE 전
`pg_dump`로 products 테이블(또는 product_id,image_url)만 백업해두는 것을 권장.
```

- [ ] **Step 2: Commit**

```bash
git add docs/ops/product-images-minio-runbook.md
git commit -m "docs(ops): 상품 이미지 MinIO 자체 호스팅 실행 가이드"
```

---

## 최종 검증 (전체 태스크 후)

- [ ] `cd backend/product-service && python -m pytest tests/ -v` → 전체 PASS
- [ ] `cd backend/product-service && python -m py_compile app/routers/admin.py app/services/image_storage.py scripts/backfill_product_images.py` → 에러 없음
- [ ] `cd frontend && npx tsc --noEmit` → 에러 없음
- [ ] 백필 `--dry-run`이 대상 건수를 정상 출력(env·DB 준비된 환경에서, 팀이 실행)
