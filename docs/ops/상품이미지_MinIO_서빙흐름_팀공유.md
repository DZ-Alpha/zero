# 상품 이미지 MinIO 자체 호스팅 — 동작 흐름 (팀 공유용)

> 상품 썸네일을 외부 사이트 핫링크 대신 우리 MinIO에서 서빙한다. 원본 사이트가
> 이미지를 내려도 우리 앱에서는 깨지지 않는다. 이 문서는 "어떻게 동작하는지"
> 흐름 중심으로 정리한 것이다.

---

## 1. 한눈에 보기

```
[예전]  브라우저 ──▶ 외부 사이트(마켓컬리/네이버…)에서 이미지 직접 가져옴
                     └ 원본 내려가면 깨짐 ❌

[지금]  브라우저 ──▶ 우리 서버(/b/product-images/…) ──▶ MinIO에서 이미지 반환
                     └ 원본과 무관하게 우리 것 서빙 ✅
```

핵심 아이디어: **이미지 파일을 한 번 우리 MinIO에 복사해두고, DB에는 우리 경로를
저장한다. 그 뒤로는 브라우저가 우리 MinIO만 바라본다.**

---

## 2. 데이터가 어떻게 저장돼 있나

### DB (`service.products.image_url`)
```
예전:  https://product-image.kurly.com/…/xxxx.jpg     (외부 URL)
지금:  /b/product-images/{uuid}.jpg                    (우리 경로)
```

### MinIO
- 버킷: `product-images` (공개 read 정책)
- 객체: `product-images/{uuid}.jpg` (버킷 루트에 uuid로 저장)
- 자격증명: diet-service와 동일한 secret 재사용 (`dang-minio-secret`)

> DB의 `image_url`과 MinIO의 객체는 1:1로 대응한다.
> `/b/product-images/{uuid}.jpg` (DB)  ↔  `product-images/{uuid}.jpg` (MinIO 객체)

---

## 3. 서빙 흐름 (사용자가 페이지를 열 때)

```
① 브라우저: /search 페이지 접속
        │
        ▼
② 검색 API 호출:  GET /b/search
     응답 JSON:  { "image": "/b/product-images/{uuid}.jpg", … }
        │        (DB의 image_url을 그대로 내려줌)
        ▼
③ 브라우저가 <img src="/b/product-images/{uuid}.jpg"> 렌더 → 그 경로로 이미지 요청
        │
        ▼
④ Cloudflare ─▶ Istio Gateway 도착
        │
        ▼
⑤ Istio VirtualService(dang-production)가 경로 보고 라우팅:
        /b/product-images/*  ──▶  MinIO 로 직접 전달
        (authority를 MinIO로 rewrite, "/b" 떼고 /product-images/{uuid}.jpg)
        │
        ▼
⑥ MinIO(공개 버킷)가 서명 없이 이미지 반환 → HTTP 200 image/jpeg
        │
        ▼
   브라우저에 이미지 표시 ✅
```

---

## 4. ⚠️ 라우팅은 프론트가 아니라 Istio가 한다 (중요)

이 프로젝트에서 `/b/*` 경로 라우팅 로직은 **두 군데**에 존재한다:

| 위치 | 실제 운영에서 쓰이나 |
|------|---------------------|
| **Istio VirtualService** (`zero-manifests/istio/production-edge/routing.yaml`) | ✅ **이게 실서비스 라우팅** |
| 프론트 `app/b/[...path]/route.ts` | ❌ 실서비스에선 미사용 (로컬/게이트웨이 모드용) |

**실서비스(zerodang.org)에서는 Istio가 `/b/*`를 가로채 라우팅하므로, 프론트의
프록시 코드는 실행되지 않는다.** 그래서 새 `/b/…` 경로를 추가할 때는
**반드시 Istio routing.yaml에 규칙을 넣어야** 한다.

### 실제로 겪은 문제 (참고)
`/b/product-images`를 Istio에 안 넣었더니, `/b/product` 규칙에 잘못 매칭되어
(product-images가 "product"로 시작하니까) product-service로 가서 404가 났다.
→ **`/b/product-images` 규칙을 `/b/product`보다 "앞"에 추가**해서 해결.
Istio는 규칙을 위에서부터 순서대로 매칭하므로 순서가 중요하다.

```yaml
# routing.yaml — /b/product 보다 반드시 앞에!
- name: product-images
  match:
    - uri: { prefix: /b/product-images }
  rewrite:
    uri: /product-images
    authority: dang-minio.dang-db-ns.svc.cluster.local:9000
  route:
    - destination:
        host: dang-minio.dang-db-ns.svc.cluster.local
        port: { number: 9000 }
```

---

## 5. 새 상품이 등록될 때 (admin 경로)

관리자가 상품을 등록/수정하면, 입력한 외부 이미지 URL을 자동으로 우리 MinIO로
옮기도록 훅이 걸려 있다:

```
관리자 상품 등록 (image_url = 외부 URL)
        │
        ▼
admin 훅 → 외부 이미지 다운로드 → MinIO 업로드 → image_url을 우리 경로로 저장
        │
        ▼  (실패 시: 원본 URL 그대로 유지 — 등록 자체는 성공)
```

> 설계 원칙: **어떤 실패도 상품 등록을 막지 않는다.** 이미지 호스팅에 실패하면
> 원본 외부 URL을 그대로 둔다(= 예전과 동일, 나빠지지 않음).

이때 저장되는 경로는 기존 백필과 동일하다:
- MinIO 객체 키: `{uuid}.{ext}` (버킷명은 키에 넣지 않음)
- DB image_url: `/b/product-images/{uuid}.{ext}` (Istio가 이 prefix로 MinIO 라우팅)

---

## 6. 실패·예외 처리 요약

| 상황 | 동작 |
|------|------|
| 외부 다운로드 실패 (연결 끊김 등) | 원본 URL 유지, 로그, 계속 진행 → 재실행으로 흡수 |
| 원본 이미지가 이미 삭제됨 (404) | 자체 호스팅 불가 → 원본 URL 유지 (현재 25건) |
| 10MB 초과 이미지 | 스킵 (원본 URL 유지) |
| MinIO 미설정/오류 | 저장 시도 안 함, 원본 URL 유지 |

**공통 원칙: 실패는 절대 예외로 터지지 않고, 항상 "원본 URL 유지"로 흡수된다.**
즉 최악의 경우에도 예전(외부 핫링크)과 동일하며, 더 나빠지지 않는다.

---

## 7. 현재 상태 (2026-08-01 기준)

| 항목 | 상태 |
|------|------|
| MinIO `product-images` 버킷 + 공개 정책 | ✅ 완료 |
| product-service MinIO 연결(env) | ✅ 완료 |
| 기존 상품 2,413건 자체 호스팅 | ✅ 완료 (99%) |
| Istio 라우팅(`/b/product-images` → MinIO) | ✅ 완료 |
| 브라우저 이미지 서빙 | ✅ 정상 (HTTP 200) |
| admin 훅(새 상품 등록 시 자동 호스팅) | ✅ 코드 수정 완료 — 부하테스트 종료 후 배포 예정 |
| 미처리 25건 (원본 404) | 자체 호스팅 불가, 원본 URL 유지 |

> 배포 대기: `image_storage.py` 수정(object key 경로 정리)이 로컬 브랜치
> `fix/product-image-double-path`에 커밋돼 있다. 부하테스트가 끝나면 push→재배포한다.
> 기존 2,413건은 이미 정상이라 서비스 영향은 없다.

> 참고: Cloudflare가 과거 404 응답을 캐시했을 수 있어, 브라우저에서 안 보이면
> 강력 새로고침(Ctrl+Shift+R) 또는 CF 캐시 만료를 기다려야 할 수 있다.
