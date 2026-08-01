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
