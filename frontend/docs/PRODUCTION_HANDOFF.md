# 당당 프론트·백엔드 연동 인수인계

작성일: 2026-07-17
기준: 프론트엔드는 수정 가능, 백엔드와 PostgreSQL 데이터는 읽기 확인만 수행

## 1. 현재 결론

공개 데이터 조회는 실제 백엔드와 연결되어 있습니다. 브라우저는 같은 출처의 `/b/*`만 호출하고, Next.js가 `BACKEND_GATEWAY_URL`의 `/b/*`로 전달합니다.

2026-07-17 확인 결과:

| 호출 | 결과 | 의미 |
| --- | --- | --- |
| `GET /b/search?page=1` | 200, 상품 20개 | 상품 목록 연결 정상 |
| `GET /b/recipes` | 200, 레시피 1,697개 | 레시피 목록 연결 정상 |
| `GET /b/tags/category` | 200 | DB 분류 연결 정상 |
| `GET /b/home/rank/item` | 200, `PREPARING`, 0개 | 경로는 연결됐지만 백엔드 기능 준비 중 |
| `GET /b/social-access/naver/login` | 8초 내 응답 없음 | 로그인 서비스의 OAuth state/Redis 연결 확인 필요 |
| `GET /b/social-access/kakao/login` | 8초 내 응답 없음 | 로그인 서비스의 OAuth state/Redis 연결 확인 필요 |

로그인 후 호출되는 마이페이지, 개인 목표, 개인 추천, 식단 기록 API는 정상 OAuth 토큰을 얻은 뒤 최종 통합 테스트가 필요합니다.

## 2. 프론트에서 완료한 작업

- 상품 목록은 `/b/search` 응답으로 카드를 만들고, 서버 호출 실패 때만 로컬 catalog를 사용합니다.
- 상품 상세는 UUID로 열 수 있으며 기본 정보·AI 한 줄 요약·감미료·개인화 API를 연결했습니다.
- 레시피 목록은 `/b/recipes`, 상세는 `/b/recipes/{id}`를 우선 사용합니다.
- 서버 이미지가 없거나 깨지면 대체 이미지를 보여줍니다.
- 상품 목록의 카드마다 상세 API를 호출하던 N+1 요청을 제거했습니다. 상세 정보는 사용자가 항목을 고를 때만 한 번 요청합니다.
- 실제 JWT가 있을 때만 로그인 상태로 판단합니다. 데모 플래그와 URL 쿼리로 로그인된 것처럼 보이던 처리를 제거했습니다.
- 사용자 설정과 로컬 식단 기록을 JWT 사용자별 저장소로 분리해 다른 계정의 기록이 섞이지 않게 했습니다.
- 회원가입 설정 저장이 실패하면 성공 화면으로 넘어가지 않고 화면 안에서 재시도를 안내합니다.
- 마이페이지 수정은 서버 저장 함수를 사용하며, 서버 저장 실패 안내를 모달 안에서 보여줍니다.
- 서버 사진 기록과 로컬 기록을 합치되 홈 게이지에서 같은 서버 기록을 두 번 더하지 않도록 분리했습니다.
- 사진 분석 API가 `PREPARING`이면 임의의 당류·칼로리를 만들지 않고 분석 대기 상태로 표시합니다.
- 로딩, 빈 결과, 오류, 재시도, 이미지 오류, 삭제 확인, 로그인 유도 등 서비스 상태 UI를 추가했습니다.
- 프록시 연결 제한 시간을 8초로 두고 OAuth 서버가 응답하지 않으면 로그인 화면으로 돌아오게 했습니다.
- Node 22.15.0 기반 standalone Dockerfile, 프론트 Compose, 헬스체크와 기본 보안 헤더를 추가했습니다.
- 업로드 URL은 현재 LAN 테스트용 `http://192.168.0.159:3001`로 설정했습니다.

## 3. 백엔드 팀에 먼저 요청할 작업

### P0 — 실제 사용 전에 필요

1. OAuth 시작 요청 멈춤 해결
   - `login-service` 로그 확인
   - 컨테이너에서 `REDIS_HOST:REDIS_PORT` 연결 확인
   - `state_store.create_state()`의 Redis `SET`이 완료되는지 확인
   - Redis 인증이 필요한 환경이라면 비밀번호/SSL 설정을 코드와 env에 추가

2. 식단 기록 CRUD 계약 확정
   - 레시피·상품·사진을 같은 기록 모델로 저장해야 합니다.
   - 최소 필드: `date`, `mealType`, `itemType`, `itemId`, `serving`, `sugar`, `calories`
   - 필요 API: 생성, 수정, 삭제, 날짜별 조회
   - 지금 레시피/상품 선택 기록은 사용자별 localStorage에만 남습니다.

3. 사진 업로드 흐름 보완
   - `/diet/upload`가 `mealType`, `eatenAt`을 받아야 합니다.
   - 업로드 직후 확정 기록을 만들지 말고 draft → 분석 → 사용자 확인 → 저장 흐름이 필요합니다.
   - 취소한 업로드를 삭제할 API가 필요합니다.
   - `/diet/ai-analyze`의 실제 분석 구현이 필요합니다.

4. 인증 전달 방식 개선
   - 현재 여러 API가 `usr` 쿼리에 JWT를 넣고 OAuth 콜백도 URL에 토큰을 전달합니다.
   - 운영 전 `Authorization: Bearer` 또는 `HttpOnly + Secure + SameSite` 쿠키로 바꾸는 것을 권장합니다.
   - OAuth 콜백은 JWT 대신 짧게 만료되는 일회용 code를 프론트에 전달하는 편이 안전합니다.

5. 운영 OAuth 주소 등록
   - `FRONTEND_URL=https://서비스도메인`
   - `NAVER_REDIRECT_URI=https://서비스도메인/b/social-access/naver/callback`
   - `KAKAO_REDIRECT_URI=https://서비스도메인/b/social-access/kakao/callback`
   - 네이버·카카오 개발자 콘솔에도 같은 HTTPS 주소를 등록해야 합니다.

### P1 — 목록 품질과 성능

1. `/search` 응답에 카드 필드 포함
   - `brand`, `category`, `serving`, `sugar`, `calories`, `image`, `tags`
   - `total`, `page`, `pageSize`, `hasNext`
   - 현재 응답만으로는 목록에서 영양정보를 사실대로 표시할 수 없습니다.

2. `/recipes` 페이지네이션과 필터
   - `source=10000recipe`, category, sort, page/pageSize
   - 카드에 thumbnail, category, time, sugar, calories, source 포함
   - 현재 한 번에 1,697개를 내려주며 유튜브 출처를 서버에서 거르지 못합니다.

3. 캘린더 집계 응답 개선
   - 날짜별 합계와 음식 목록을 한 응답에 포함
   - 현재는 캘린더 목록 이후 기록마다 `/diet/other-foods`를 호출하는 N+1 구조입니다.

4. 찜/즐겨찾기 API
   - 레시피·상품 찜 생성/삭제/목록이 필요합니다.
   - 지금 하트 상태는 사용자별 브라우저 저장입니다.

5. 실제 랭킹과 추천
   - `/home/rank/item`의 `PREPARING` 해제
   - 추천 응답에는 프론트 상세로 이동 가능한 상품 UUID를 포함해야 합니다.

6. 상품 데이터 품질 확인
   - 현재 일부 상품명이 `딸기`, `망고`, `제로`처럼 검색 키워드 수준으로 저장돼 있습니다.
   - 운영 노출 전 상품명·브랜드·분류·1회 제공량·이미지·구매 URL을 정규화해야 합니다.

### P2 — 명세에 있으나 미구현 또는 별도 결정 필요

- OCR 상품 검색 `/search/lens`
- 식단 OCR `/diet/ocr-analyze`
- 챗봇 `/ai/chatbot`
- 저당 레시피 전용 목록과 AI 비교 요약
- 상품 리뷰, 대용량 상품, 상품 그룹 기능
- 알레르기 개별 성분, 알림 설정, 마케팅 동의의 서버 저장 필드
- 커뮤니티·공지·관리자 화면의 프론트 구현 범위 결정

## 4. 프론트에서 후속으로 할 작업

백엔드 계약이 나온 뒤 아래 순서로 교체합니다.

1. `useDietRecords`의 localStorage 쓰기를 식단 CRUD API로 교체하고, 오프라인 임시 저장만 남깁니다.
2. 찜 상태를 서버 API로 교체합니다.
3. 목록의 `더 불러오기`를 서버 `hasNext` 기준으로 연결합니다.
4. 검색 필터와 정렬을 URL 쿼리와 서버 쿼리에 일치시킵니다.
5. OAuth 토큰 전달 방식이 확정되면 `lib/api/client.ts`의 인증 방식을 한 곳에서 교체합니다.
6. Playwright 기반 로그인→가입 설정→기록→캘린더→삭제 E2E 테스트를 추가합니다.
7. ESLint 규칙과 CI 품질 검사를 추가합니다. 현재 `npm run lint`는 TypeScript 검사와 동일합니다.
8. 운영 오류 수집, 성능 지표, 접근성 자동 검사를 CI에 붙입니다.

## 5. 같은 서버 Docker Compose 권장 구조

```text
인터넷
  -> edge reverse proxy (80/443, TLS)
       -> /               -> frontend:3000
       -> frontend의 /b/* -> b-gateway:8080
  -> b-gateway
       -> login/main/product/recipe/ingredients/diet/community/admin
  -> PostgreSQL / Redis
```

- 외부에는 edge의 80/443만 공개합니다.
- 8000, 8008, 8010, 8012, 8014, 8016, 8018, 8020, 8080은 Compose 내부 네트워크에서만 접근하게 합니다.
- 프론트 환경변수는 `BACKEND_GATEWAY_URL=http://b-gateway:8080`, `PUBLIC_APP_URL=https://서비스도메인`을 사용합니다.
- 현재 `b-gateway`를 `--network host`로 실행한 방식은 LAN 테스트에는 쓸 수 있지만, 통합 Compose에서는 같은 네트워크의 서비스 이름을 upstream으로 쓰는 편이 관리하기 쉽습니다.
- `.env`는 이미지에 복사하지 말고 서버의 Compose secret/env로 주입합니다.
- 모든 서비스의 readiness/healthcheck, 로그 순환, DB migration 작업, PostgreSQL 백업과 복구 점검이 필요합니다.
- `/public/uploads` 볼륨은 임시 테스트용입니다. 여러 컨테이너와 AI 작업자가 사진을 읽어야 하는 운영 환경에서는 S3 호환 오브젝트 스토리지를 권장합니다.

## 6. 배포 전 통합 테스트

- [ ] 네이버·카카오 로그인 시작과 콜백이 HTTPS 도메인에서 끝까지 완료됨
- [ ] 신규 사용자 설정이 DB에 저장되고 새로고침 후 유지됨
- [ ] 다른 사용자로 로그인했을 때 이전 사용자의 설정·식단·찜이 보이지 않음
- [ ] DB에 추가한 상품과 레시피가 프론트 목록에 바로 나타남
- [ ] 상품 UUID와 레시피 ID로 상세 페이지가 열림
- [ ] 사진 업로드 URL을 diet/AI 컨테이너가 읽을 수 있음
- [ ] 아침·점심·저녁·간식과 선택 날짜가 서버에 그대로 저장됨
- [ ] 홈 게이지, 제품 상세 예상치, 캘린더 합계가 같은 목표와 기록을 사용함
- [ ] 기록 수정·삭제 후 홈과 캘린더가 함께 갱신됨
- [ ] API 중단 시 무한 로딩 대신 오류와 다시 시도 버튼이 보임
- [ ] 모바일 키보드·포커스·명도 대비·44px 터치 영역을 확인함

## 7. 로컬 확인 명령

PowerShell 실행 정책 때문에 `npm.ps1`이 막히면 `npm.cmd`를 사용합니다.

```powershell
cd "C:\Users\hi\Documents\Codex\2026-07-15\new-chat\zerofront"
npm.cmd ci
npm.cmd run typecheck
npm.cmd run build
npm.cmd run dev -- -p 3001
```

`.env.local`을 바꾼 뒤에는 개발 서버를 다시 시작해야 합니다.
