# API 라우팅 명세 (Istio 전환용)

- 작성: 2026-07-30 · 백엔드/프론트 담당 → 운영팀(Istio 전환 요청서 회신)
- 목적: Istio Ingress Gateway가 `/b/*`를 각 backend Service로 직접 전달할 수 있도록,
  경로별 소유 서비스·프리픽스 규칙·예외를 한 곳에 기록한다.
- 관련 코드: `frontend/app/b/[...path]/route.ts`(호환 계층),
  `frontend-admin/app/b/[...path]/route.ts`, `infra/b-gateway/nginx.conf`(구 게이트웨이)

## 1. 프리픽스 규칙

**외부 `/b/{path}` → 내부 `/{path}`** (Istio에서 `/b` prefix 제거 후 전달).
모든 백엔드 서비스가 이 규칙을 따른다. 예외는 §3 두 개뿐이다.

## 2. 경로별 소유 서비스

| 외부 경로 | 서비스 (k8s Service:port) | 비고 |
|---|---|---|
| `/b/social-access/*` | login-service:8000 | OAuth 시작/콜백 |
| `/b/user/*` | login-service:8000 | |
| `/b/administrator-login`, `/b/administrator-signup` | login-service:8000 | |
| `/b/webhooks/*` | login-service:8000 | |
| `/b/api/*` | login-service:8000 | |
| `/b/admin/me` | admin-service:8008 | |
| `/b/admin/products`, `/b/admin/products/*` | product-service:8016 | §4 신규 |
| `/b/admin/tags`, `/b/admin/tags/*` | ingredients-service:8018 | §4 신규 |
| `POST /b/admin` (정확히 이 경로) | **[레거시]** menu 값 분기 | §4 참고, 제거 예정 |
| `/b/home/user-sugar-calorie` (정확히 이 경로) | diet-service:8020 | 오늘 당/칼로리 게이지 |
| `/b/home/*` (위 제외) | main-service:8010 | |
| `/b/search/*`, `/b/product/*` | product-service:8016 | |
| `/b/community/*` | community-service:8012 | gam-list/notice 포함 |
| `/b/recipes/*` | recipe-service:8014 | `receipe` 오타 경로는 프론트가 `recipes`로 정규화 |
| `/b/diet/internal/*` | **차단 (404)** | §5 내부 전용 |
| `/b/diet/*` (위 제외) | diet-service:8020 | |
| `/b/rooms/internal/*` | **차단 (404)** | §5 내부 전용 |
| `/b/rooms/*` (위 제외) | community-service:8012 | 얌로그 |
| `/b/uploads/*` | diet-service:8020 | §6 업로드 정책 |
| `/b/tags/*` | ingredients-service:8018 | |
| `/b/ingredients/gam-list`, `/b/ingredients/gam-detail` | ingredients-service:8018 | §3 경로 예외 |
| `/b/ai/*` | ai:8022 | §7 SSE 정책 |
| `/b/diet-photos/*` | MinIO (dang-minio:9000) | §8 서명 URL — **`/b` 제거 금지** |
| 그 외 | main-service:8010 | 폴백 |

## 3. 프리픽스 규칙 예외 (2개)

1. **`/b/ingredients/gam-list` → ingredients-service의 `/community/gam-list`**
   (`gam-detail`도 동일). `/b`만 벗기면 `/ingredients/gam-list`인데 실제 라우트는
   `/community/gam-list`다(ingredients-service `app/routers/tags.py`). 구 게이트웨이
   시절의 매핑을 그대로 유지 중. 프론트는 이 경로를 쓰지 않으므로(community 쪽
   `/b/community/gam-list`를 사용) **Istio 전환 시 deprecate 후보**다 — 남길 거면
   Istio에서 rewrite `/b/ingredients/gam-* → /community/gam-*` 필요.
2. **`/b/diet-photos/*` → MinIO로 경로 무변형 전달** (§8).

## 4. 관리자 API — menu 분기 제거

기존 `POST /b/admin` + JSON body `menu` 분기를 기능별 URL로 분리했다 (2026-07-30):

| 신규 API | 소유 서비스 | 구 menu 값 |
|---|---|---|
| `GET /b/admin/me` | admin-service | (기존 유지) |
| `POST /b/admin/products` | product-service | manage-item (id 없이) |
| `PATCH /b/admin/products/{id}` | product-service | manage-item (id 포함) |
| `POST /b/admin/products/{id}/nutrients` | product-service | manage-nutrients |
| `POST /b/admin/products/{id}/ingredients` | product-service | manage-ingredients |
| `POST /b/admin/tags` | ingredients-service | create-tag |
| `PATCH /b/admin/tags/{id}` | ingredients-service | update-tag |
| `DELETE /b/admin/tags/{id}` | ingredients-service | deactivate-tag (soft delete) |

- frontend-admin은 신규 경로만 사용하도록 전환 완료.
- 레거시 `POST /b/admin`(menu 분기)은 배포 전환기 구버전 클라이언트 호환용으로
  양 서비스에 남아 있다. **frontend-admin 신버전 배포 확인 후 제거 예정** —
  Istio에는 레거시 경로를 아예 등록하지 않아도 된다(호환은 프론트 프록시가 담당).

## 5. 내부 전용 API (외부 차단 필수)

| 경로 | 실제 사용처 | 인증 |
|---|---|---|
| `GET /b/diet/internal/meal-records` | community→diet 서버간 | `X-Internal-Service-Secret` 헤더 (공유 시크릿) |
| `POST /b/rooms/internal/meal-recorded` | diet→community 서버간 | 동일 |

- 진입 계층(현재 프론트 프록시, 이후 Istio)에서 **404로 차단** + 백엔드 공유
  시크릿 검사(시크릿 없으면 403)의 이중 방어.
- 서버간 호출은 `/b`를 거치지 않고 k8s Service DNS로 직접 간다
  (`http://diet-service:8020/diet/internal/...`) — Istio AuthorizationPolicy로
  community-service/diet-service workload만 허용하면 된다.

## 6. 업로드 (`/b/uploads/*`)

- 구 게이트웨이: `client_max_body_size 12m`.
- 백엔드 검증(diet-service `app/routers/uploads.py`): **10MB 초과 413**,
  MIME 화이트리스트(jpeg/png/webp) 외 422. → 진입 계층 제한은 12m 유지하면 됨
  (백엔드가 더 엄격).
- 프론트 프록시는 업로드 body를 **스트리밍 전달**한다(메모리 적재 없음, 2026-07-30).
- 프록시 타임아웃: 업로드 60s.

## 7. AI / SSE (`/b/ai/*`)

- `POST /b/ai/chatbot/stream`은 SSE — 응답이 수십 초 이어진다.
- 정책: **read timeout ≥ 120s, 응답 버퍼링 금지**(구 nginx `proxy_buffering off;
  proxy_read_timeout 120s`와 동일). 프론트 프록시는 130s + 무버퍼 통과 +
  클라이언트 연결 종료 시 upstream 요청 취소로 맞춰둠.
- Istio 전환 시 `/b/ai/*` VirtualService에 별도 timeout(≥120s) 적용 필요.

## 8. MinIO 서명 URL (`/b/diet-photos/*`)

- diet-service가 **내부 MinIO 주소(host) 기준으로 SigV4 서명**한 presigned URL의
  경로+쿼리만 `/b/diet-photos/...?X-Amz-...` 상대경로로 브라우저에 내려준다.
- SigV4 서명은 **host 헤더와 경로 전체**를 포함한다. 따라서 중계 계층은:
  1. `/b`만 벗기고 경로·쿼리를 **한 글자도 바꾸지 않고** MinIO로 전달해야 하고
     (서명된 경로는 `/diet-photos/...`),
  2. MinIO로 나가는 요청의 **Host 헤더가 diet-service의 `MINIO_ENDPOINT` host와
     일치**해야 한다(불일치 시 SignatureDoesNotMatch).
- 현재 프론트 프록시가 이 역할을 한다(`MINIO_URL` env = diet-service의
  `MINIO_ENDPOINT`와 동일 값 필수). Istio로 옮길 경우 `/b/diet-photos/*`
  VirtualService에 **prefix rewrite(`/b` 제거) + host rewrite(내부 MinIO host)**
  를 함께 걸고, 얌로그 사진 표시로 실측 검증할 것.
- 업로드는 이 경로를 쓰지 않는다(§6의 `/b/uploads/*` → diet-service가 저장).

## 9. 검증 체크리스트 (요청서 §8 대응)

```
공개 조회: GET /b/recipes, /b/tags/category, /b/community/gam-list, /b/search, /b/home/user-sugar-calorie
인증: /b/social-access/{provider}/login → callback → 프론트 복귀, /b/user/*, /b/administrator-login, /b/admin/me
관리자: POST/PATCH /b/admin/products(/{id}), POST .../nutrients, POST/PATCH/DELETE /b/admin/tags(/{id})
파일: POST /b/uploads/diet-photo (12MB 초과 413), GET /b/diet-photos/*(얌로그 사진 표시)
AI: POST /b/ai/chatbot, POST /b/ai/chatbot/stream(8초 이상 유지), 사진 첨부, GET /b/ai/chatbot/history(imageUrl)
보안: GET /b/diet/internal/* → 404, POST /b/rooms/internal/* → 404
```
