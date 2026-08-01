# 상품 이미지 MinIO 자체 호스팅 설계

- 작성일: 2026-08-01
- 대상: 상품(`products`) 썸네일 이미지를 외부 핫링크 → 우리 MinIO 서빙으로 전환
- 브랜치: `feature/product-images-minio`

## 배경 / 문제

현재 상품 썸네일은 DB `products.image_url`에 **외부 URL 문자열**(식약처/네이버/마켓컬리 등)만
저장돼 있고, 브라우저가 그 외부 URL로 **직접 핫링크**한다. 원본 사이트가 이미지를 내리거나
URL을 바꾸거나 핫링크를 차단하면 우리 앱에서 이미지가 깨진다. 이를 막기 위해 이미지를 한 번
받아서 우리 MinIO에 저장하고, 우리 것을 서빙한다.

## 조사 결과 (현재 로직)

### 상품 이미지 흐름 (지금)
```
외부 사이트 이미지
 → products.image_url (외부 URL 문자열, NOT NULL)  [backend/product-service/app/models/product.py:42]
 → product-service 응답에 그대로 (imageUrl/image/url)
     - product.py:76  "imageUrl": p.image_url
     - product.py:234 "image": p.image_url
     - search.py:36   "image": p.image_url
     - search.py:29   "url": p.image_url or ""   ← url 필드에 이미지 URL을 넣는 특이 케이스
 → 브라우저가 외부 사이트로 직접 핫링크
```
상품 크롤러(마켓컬리/네이버/식약처)는 이 repo에 없다. 새 상품이 코드 경로로 들어오는 유일한
지점은 **admin 상품 등록 API**(`backend/product-service/app/routers/admin.py`, `image_url` 입력받음).

### 재사용할 MinIO 패턴 (diet 사진)
- `backend/diet-service/app/services/storage.py` — boto3 s3 client, `put_object`, content-type
  화이트리스트(jpg/png/webp), object_key 생성 패턴.
- diet-photos 버킷은 **완전 비공개**로 확인됨(2026-08-01 실측): 서명 없는 익명 GET → HTTP 403
  (없는 객체도 404 아닌 403 = 인증 자체 거부). 그래서 diet는 presigned URL을 쓴다.
- 프론트 프록시 `frontend/app/b/[...path]/route.ts:110` — `parts[0] === "diet-photos" && minioUrl`
  일 때만 `MINIO_URL`로 중계. 다른 경로는 백엔드 서비스로.

### 상품 이미지는 diet와 성격이 다름
diet 사진은 유저 프라이버시 때문에 비공개+presigned지만, 상품 이미지는 **공개 카탈로그**라
숨길 게 없고 캐시가 중요하다. 따라서 **공개 버킷 + 고정 URL**을 쓴다.

## 결정 사항 (확정)

- 대상: **상품만** (레시피 이미지는 이번 범위 밖).
- 서빙: **공개 버킷 `product-images` (public-read) + 고정 URL**. presigned 안 씀.
- 백필: **1회성 스크립트** (기존 전부) + **admin 등록 시 자동** (앞으로).
- DB `image_url` 값: 외부 URL → **`/b/product-images/{key}`** 상대경로로 교체.
- 자격증명: **환경변수 주입** (`MINIO_ENDPOINT/ACCESS_KEY/SECRET_KEY`), secret은 팀 관리.

## 작업 경계

| 영역 | 담당 |
|------|------|
| MinIO `product-images` 버킷 생성 + public-read 정책 | **사용자(팀)** |
| product-service에 MINIO_* env/secret 연결, 프론트 MINIO_URL 확인 | **사용자(팀)** |
| 코드 4가지(스토리지 모듈·백필·admin 훅·프론트 프록시) | **Claude** |
| 인프라 실행용 가이드/명령어 문서 (복붙용 준비물) | **Claude 작성, 사용자 실행** |

## 전체 구조

```
[백필: 1회성]                         [앞으로: admin 등록 시 자동]
기존 image_url(외부 URL)               새 상품 등록(image_url 입력)
 → 다운로드                             → 다운로드
 → product-images 버킷 업로드           → product-images 버킷 업로드
 → image_url = /b/product-images/{key}  → image_url = /b/product-images/{key}
   로 UPDATE                              (실패 시 원본 유지)

[서빙: 브라우저]
product API 응답 imageUrl = "/b/product-images/{key}"
 → 프론트 app/b/[...path] 프록시 (product-images 분기)
 → MINIO_URL/product-images/{key} (공개 버킷, 서명 불필요)
 → 이미지 반환
```
API 응답·프론트 렌더 코드는 `image_url`을 그대로 쓰므로 값(경로)만 바뀌고 로직 변경은 거의 없다.

## 코드 변경 상세 (Claude)

### A. 이미지 스토리지 모듈 — `backend/product-service/app/services/image_storage.py` (신규)
- diet `storage.py` 패턴 재사용: boto3 s3 client, env `MINIO_ENDPOINT/ACCESS_KEY/SECRET_KEY`,
  버킷 `product-images`.
- content-type 화이트리스트: image/jpeg→jpg, image/png→png, image/webp→webp.
- `store_external_image(url: str) -> str | None`:
  1. 이미 `/b/product-images/`로 시작하면 그대로 반환(멱등).
  2. 외부 URL 다운로드(timeout, 크기 상한). content-type 검증.
  3. `product-images/{uuid}.{ext}`로 put_object.
  4. 성공 시 `/b/product-images/{uuid}.{ext}` 반환. 실패 시 None(호출부가 원본 유지).
- 공개 버킷이라 presigned 없음.

### B. 백필 스크립트 — `backend/product-service/scripts/backfill_product_images.py` (신규, 1회성·멱등)
- `products`에서 `image_url`이 외부 URL인 행만 대상(`/b/product-images/`로 시작하면 skip).
- 각 행: `store_external_image` → 성공 시 `UPDATE products SET image_url=... WHERE product_id=...`.
- 실패(404/타임아웃/미지원 형식): 원본 URL 유지 + 로그, 계속 진행.
- 진행률 출력, 배치 커밋, 재실행 안전.

### C. admin 등록 훅 — `backend/product-service/app/routers/admin.py` (수정)
- 상품 등록 시 입력 `image_url`이 외부 URL이면 `store_external_image` 호출 →
  성공 시 우리 경로로 저장, 실패 시 원본 URL 그대로 저장(등록 자체는 성공).

### D. 프론트 프록시 — `frontend/app/b/[...path]/route.ts` (수정)
- `buildUpstream`의 `diet-photos` 분기 옆에 `product-images` 분기 추가:
  `parts[0] === "product-images" && minioUrl` → `MINIO_URL/product-images/{key}`로 중계.
- diet와 달리 서명 없음(공개 버킷). 나머지 프록시 로직 그대로.

## 인프라 가이드 문서 (Claude 작성, 사용자 실행)
코드 변경과 함께 아래를 담은 실행 가이드를 남긴다(복붙용):
- `product-images` 버킷 생성 + public-read: `mc mb`, `mc anonymous set download` 예시.
- product-service 배포에 넣을 env 목록(`MINIO_ENDPOINT/ACCESS_KEY/SECRET_KEY`),
  기존 diet-service secret 참조 스니펫.
- 프론트 `MINIO_URL` 설정 확인 방법.
- 백필 실행 순서(버킷·정책·env 준비 → 스크립트 실행 → 검증 쿼리).

## 엣지 케이스

- 다운로드 실패 → 원본 URL 유지(최소한 지금보다 나빠지지 않음).
- 멱등 → 백필 중단·재실행 안전.
- content-type: jpg/png/webp만. 그 외(gif/svg 등) skip, 원본 유지.
- `search.py`의 `_search_item`은 `"url"`과 `"image"` 둘 다 `p.image_url`을 넣는다(28-29, 36줄,
  레거시 — url은 구매 링크가 아니라 image_url의 중복). 백필로 image_url이 `/b/product-images/...`로
  바뀌면 두 필드가 함께 바뀌므로 일관성은 유지된다(이번 변경이 만드는 새 문제 아님). 별도 조치 불필요.
- image_url은 NOT NULL이라 항상 값이 있음(빈 값 걱정 없음).

## 안 하는 것 (YAGNI)
- 레시피 이미지 (상품만 먼저)
- 이미지 리사이징·썸네일 생성·최적화 (원본 그대로 저장)
- CDN 연동
- 상품 크롤러 통합 (repo에 없음 — admin 등록 API에만 훅)
- MinIO 버킷 생성·public 정책 (사용자/팀 몫)

## 검증

- 스토리지 모듈: 외부 URL 다운로드→업로드→object_key 반환 단위 확인(로컬 or mock).
- 백필: dry-run/소량 먼저 → 성공 건 image_url이 `/b/product-images/...`로 바뀌는지,
  실패 건 원본 유지되는지, 재실행 시 skip되는지.
- 프록시: `/b/product-images/{key}` 요청이 MinIO로 중계돼 200 이미지 반환.
- 프론트: 상품 상세/검색 카드 이미지가 우리 MinIO에서 로드되는지(네트워크 탭).
- 백엔드 `py_compile`, 프론트 `tsc --noEmit`.
