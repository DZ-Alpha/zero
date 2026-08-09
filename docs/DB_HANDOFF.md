# 개발팀 전달 — DB 변경분 사용 안내

> 작성 2026-08-09 / 인프라·데이터 파트
> 대상 DB: 프로덕션 `zero-pg` (`dang-db-ns`, CNPG 3인스턴스), database `zero`
> 마이그레이션 파일: `infra/zero-infra/kafka/migrations/003~013`
> 추가 보완: `011_product_display_views.sql`, `012_service_permissions.sql`, `013_fix_swap_pick_null_report.sql`
> 전달 보조 파일: `SHA256SUMS`, `staging_apply.sql`, `staging_sample_data.sql`, `staging_validation.sql`

## 0. 한 줄 요약

DB에는 계산 결과가 있지만 **사진 분석 결과를 상품·레시피에 연결하는 API와 프론트 호출이
함께 배포되어야 기능이 동작합니다.** 마이그레이션만 적용해서는 사진 기반 추천 카드가
동작하지 않습니다. 요청 시점에 벡터 유사도를 다시 계산하지 않고, 미리 계산된 후보를
API에서 세부 식품군·제공량·단위까지 재검증합니다.

### ⚠️ 2026-08-10 운영 검증 정정

기존의 “조회 대상 두 줄만 바꾸면 된다”는 설명은 사실과 달라 폐기합니다. 운영 배포본에는
`/product/alternatives`, 실제 `/diet/recommend-alt`, 레시피 검색, `sugar_asc`,
`/tags/health-label`, 분석 완료 후 프론트 추천 호출이 없습니다. 이 저장소의 현재 변경분에는
해당 구현이 포함되어 있지만, DB 마이그레이션과 서비스 이미지를 함께 배포하고 인증 E2E를
통과하기 전에는 완료로 판단하지 않습니다.

| 필수 항목 | 현재 저장소 | 운영 반영 조건 |
|---|---|---|
| Vision 음식명 → 상품 후보 매핑 | diet-service 구현 | diet/product 이미지 동시 배포 |
| `/product/alternatives` | product-service 구현 | `012·013` 적용 후 배포 |
| `/diet/recommend-alt` | Product Service 연동 구현 | 두 서비스 동시 배포 |
| 분석 완료 후 추천 호출 | `RecordMealModal` 구현 | frontend 배포 |
| 동일 food_type·제공량·단위 | 강화된 `005b`와 API 이중 검증 | embeddings 갱신 후 `005b` 재실행 |
| 레시피 `search` | recipe-service 이름 부분 일치 구현 | recipe-service 배포 |
| `sort=sugar_asc` | product-service DB 정렬 구현 | product-service 배포 |
| `/tags/health-label` | ingredients-service 구현 | ingredients-service 배포 |
| 앱 계정 권한 | `012` 파일 준비 | 운영 DB 적용·권한 조회 |
| NULL report_no 보정 | `013` 및 체크섬 준비 | 운영 DB 적용 |
| 사진 업로드 → 추천 카드 E2E | 미완료 | 인증 테스트 계정으로 배포 후 실행 |

| 용도 | 바꿀 대상 |
|---|---|
| 검색 · 상세 · 카드 목록 | `service.products` → **`service.v_product_display`** |
| 스왑 / 추천 로직 | `service.products` → **`service.v_product_swap_pick`** |

이 교체를 안 하면 브랜드 접두(딸기 → 웰치스 딸기)와 중복 묶음이 화면에 반영되지 않습니다.
자세한 내용은 8절.

## 1. 적용 상태 (중요)

| 환경 | 적용 여부 |
|---|---|
| 프로덕션 `zero-pg` | **003~011 적용 완료** (2026-08-10 확인), `012·013·강화된 005b` 미적용 |
| 스테이징 `dang-stg-pg-1` | 기존 **003~012 적용**, 강화된 `005b`와 `013` 재검증 필요 |

- 스테이징은 DAST용 빈 DB였으므로 운영 원본 데이터가 아니라 검증용 고정 샘플만 넣었습니다.
- 변경은 전부 **추가(additive)** 입니다. 기존 테이블·컬럼·제약을 삭제하거나 바꾼 것이 없어
  기존 코드는 그대로 동작합니다.
- 마이그레이션 이력 테이블이 아직 없습니다. 이번 스테이징 적용은 아래 순서의 실행 로그로 검증했습니다.

### 1.1 실행 순서와 의존성

`001` → `002` → `003` → `004` → `005` → `005b` → `006` → `007` → `008` → `009` → `010`
→ `011` → `013` → `012` 순서입니다. 최종 뷰 정의를 만든 뒤 앱 권한을 부여합니다. `002`는
`pg_trgm`/`fuzzystrmatch` 및 상품 검색 인덱스, `003`은 기본 테이블
인덱스, `004`는 레시피 뷰와 두 매터리얼라이즈드 뷰, `005`/`005b`는 상품 대안 테이블과
계산 결과, `006`~`009`는 큐·리뷰·컬럼·태그·콘텐츠, `010`은 상품 FK입니다.
`005b`는 상품·태그·`product_embeddings`가 채워진 뒤 다시 실행해야 합니다.
상품 표시 뷰는 기존 정제 작업에서 누락된 별도 산출물이어서 `011`로 버전화했습니다.
`012`는 앱 role의 최소 권한만 부여하며 운영 matview refresh 권한은 포함하지 않습니다.
`013`은 신고번호가 없는 상품의 중복 압축 오류를 막고 대안 API 검증용 제공량 필드를 뷰에 추가합니다.

스테이징 전체 절차는 `infra/zero-infra/kafka/staging_apply.sql`에 고정했습니다.

```text
003~012 적용
→ staging_sample_data.sql 실행
→ 005b 재실행
→ mv_category_sugar_stats 갱신
→ mv_sweetener_catalog 갱신
→ staging_validation.sql 실행
```

`staging_sample_data.sql` 마지막에 `005b`, 두 matview 갱신, 검증 SQL include가 들어 있어
샘플만 따로 실행해도 같은 순서가 재현됩니다. 스테이징에서 확인된 대안 11쌍은 샘플
상품·태그·임베딩을 넣은 뒤 실행된 `005b_fill_product_alternatives.sql`에서 생성됐습니다.

---

## 2. 바로 쓸 수 있는 것

### 2.1 `service.v_recipe_swap_ranking` (뷰) — 1,722건

레시피 당류 감소율 랭킹. **`/home/rank/item` 의 `PREPARING` 을 이걸로 해소할 수 있습니다.**
기존 `service.recipes` 에 이미 있던 값을 정렬 가능한 형태로 노출한 것뿐이라 새 데이터가 아닙니다.

```
id, name, thumbnail_url, source,
base_sugar_g, total_sugar_g, sugar_saved_g, sugar_reduction_pct,
total_kcal, base_kcal, kcal_reduction_pct, rnk
```

```sql
SELECT id, name, thumbnail_url, base_sugar_g, total_sugar_g,
       sugar_saved_g, sugar_reduction_pct
FROM service.v_recipe_swap_ranking
ORDER BY rnk
LIMIT 10;
```

실제 상위권(카피로 바로 쓸 수 있는 수치):

| 레시피 | 원래 | 저당 | 감소 |
|---|---:|---:|---:|
| 아바라(아메리카노 바닐라 라떼) | 20.00g | 0.00g | 100% |
| 설탕 대신 스테비아로 저당 과일청 | 704.00g | 4.00g | 99.4% |
| 설탕 없이 만든 아몬드 카스테라 | 76.30g | 0.50g | 99.3% |

> 감소율 80% 이상 99건, 60% 이상 182건. 나머지 1,417건은 20% 미만이라
> 랭킹 상위에는 안 올라옵니다.

### 2.2 `product.product_alternatives` (테이블) — 2,521쌍 / 상품 757개

**SwapCard("이거 대신 이건 어때") 의 상품 문맥 데이터입니다.**

```
product_id, alt_product_id, rank, similarity,
sugar_delta_g, sugar_delta_pct, kcal_delta, computed_at
```

- `sugar_delta_g` 는 **항상 음수**입니다(CHECK 제약). `-20.72` = 당류 20.72g 줄어듦.
- `rank` 는 1~5. `rank=1` 이 가장 추천할 만한 대안입니다.
- `similarity` 는 pgvector 코사인 유사도. **0.70 미만은 저장하지 않습니다**(아래 4절 참고).

```sql
-- 상품 상세 페이지: 이 상품의 저당 대안
SELECT a.product_id, a.product_name, a.brand_name, a.image_url,
       a.sugars, a.calories,
       pa.rank, pa.similarity, pa.sugar_delta_g, pa.sugar_delta_pct
FROM product.product_alternatives pa
JOIN service.products a ON a.product_id = pa.alt_product_id
WHERE pa.product_id = $1
ORDER BY pa.rank
LIMIT 3;
```

**대안이 없는 경우가 정상입니다.** 세 가지 경우가 있습니다.

| 상황 | 건수 | 화면에서 할 것 |
|---|---:|---|
| 당류가 이미 낮거나 저당·제로 표시 | 배치 재실행 후 재집계 | 대체 카드 미노출 |
| 당류는 있으나 비슷하면서 더 낮은 게 없음 | 793 | 카드 미노출 |
| 대안 있음 | 757 | SwapCard 노출 |

> 이미 저당인 사용자에게 계속 대안을 들이미는 피로감을 막기 위해 의도한 동작입니다.
> "대안이 있을 때만 보여준다"가 기본값입니다.

### 2.3 `service.mv_category_sugar_stats` (매터리얼라이즈드 뷰) — 10건

SwapCard 의 "근거" 문구와 비교 배지용. 카테고리별 당류 분포입니다.

```
tag_id, tag_code, tag_name, product_count,
avg_sugar, median_sugar, min_sugar, max_sugar, zero_sugar_count, avg_calories
```

```sql
-- "이 제품 3.2g — 음료 평균 1.6g보다 높아요"
SELECT s.tag_name, s.avg_sugar, s.median_sugar, s.zero_sugar_count, s.product_count
FROM service.mv_category_sugar_stats s
JOIN service.product_tags pt ON pt.tag_id = s.tag_id
WHERE pt.product_id = $1;
```

실제 값:

| 카테고리 | 상품수 | 평균 | 중앙값 | 당류 0g |
|---|---:|---:|---:|---:|
| 베이커리·간식 | 432 | 2.71 | 1.21 | 128 |
| 음료 | 994 | 1.65 | 0.00 | 569 |
| 간편식·면류 | 123 | 2.07 | 1.67 | 15 |
| 유제품 | 112 | 1.18 | 0.54 | 11 |
| 곡물·시리얼 | 59 | 3.14 | 2.00 | 7 |
| 잼·스프레드 | 55 | 4.89 | 4.00 | **0** |
| 견과·씨앗 | 8 | 8.60 | 4.16 | **0** |
| 가공식품 | 235 | 2.22 | 0.50 | 88 |
| 소스·조미 | 318 | 3.48 | 2.00 | 49 |
| 특수영양식 | 91 | 6.30 | 3.00 | 18 |

### 2.4 `service.mv_sweetener_catalog` (매터리얼라이즈드 뷰) — 20건

감미료 사전(CM-0107/0108) 과 새 필터 축. **`service.tags` 의 설명이 이제 채워져 있습니다.**

```
tag_id, tag_code, tag_name, description, caution_text, source_url,
product_count, avg_sugar_of_products
```

실사용 순위: 수크랄로스 725 / 스테비아 446 / 효소처리스테비아 441 / 에리스리톨 382 /
아세설팜칼륨 380 / 말티톨 89 / 아스파탐 49 … 네오탐·스테비올배당체·타가토스·만니톨은 0건.

### 2.5 `service.tags` — 61건 전부 설명 채움

이전에는 `description`/`caution_text`/`source_url` 이 **전부 NULL** 이었습니다(그래서 감미료
화면이 빈 껍데기였습니다). 지금은:

| tag_type | 개수 | description | caution_text |
|---|---:|---:|---:|
| SWEETENER | 20 | 20 | 14 |
| HEALTH_LABEL | 11 | 11 | 8 |
| ALLERGEN | 19 | 19 | 19 |
| CATEGORY | 11 | 11 | 0 |

- `caution_text` 는 **실제 주의가 필요한 것에만** 있습니다(NULL 이 정상). 예: 아스파탐→
  페닐케톤뇨증, 당알코올→설사, 자일리톨→반려견 독성, "무가당"→원재료 당은 남아 있음.
- **`source_url` 은 전부 NULL 입니다. 의도한 것입니다.** 식약처 고시 번호·개정일을 실제로
  대조 검증하지 않았고, 확인 안 된 링크를 넣으면 "근거 있음"으로 잘못 보입니다.
  UI 에서 출처 링크를 필수로 가정하지 마세요.

### 2.6 `content` 스키마 — 읽을거리·컬렉션

지금 프론트에 하드코딩된 `readingList`(4건)와 `HomeAdBanner` 슬라이드(3건)를 대체할 자리입니다.
**DB 로 옮기면 프론트 배포 없이 콘텐츠를 늘릴 수 있습니다.**

- `content.articles` — 기존 8건 시드는 **전부 `is_published=false`** 이고 본문이 비어
  있습니다. 여기에 스테이징 검증용 본문 있는 공개 글 1건을 추가했습니다. 운영 콘텐츠는
  본문이 채워진 뒤 `is_published=true` 로 바꿔주세요.
- `content.collections` — 6건, `is_published=true`. `rule_json` 으로 규칙 기반 큐레이션입니다.
- `content.collection_products` — 수동 큐레이션용(현재 비어 있음).

```jsonc
// rule_json 형태
{"category":"BEVERAGE","max_sugar":0}                    // zero-drinks → 569건
{"category":"JAM_SPREAD","sort":"sugar_asc","limit":10}  // hard-mode-jam
```

**규칙 해석은 백엔드가 구현해야 합니다.** 지원할 키: `category`(tag_code), `max_sugar`,
`sort`(`sugar_asc`|`sugar_desc`), `limit`. 검산 완료 — 6개 규칙 전부 실제 상품에 매칭됩니다.

---

## 3. 만들어만 둔 것 (백엔드 구현 대기)

### 3.1 `service.search_miss_queue`

검색 결과 0건 검색어를 모으는 큐. **생산자가 없어 현재 0건입니다.**

- `product-service` 의 `/search` 는 이미 `results` 개수를 로그로 찍고 있습니다
  (`app/routers/search.py`, `logger.info`).
- `user.activity.raw.v1` 계약과 Mongo 소비자(`dangdang_analytics.user_activity_events`,
  현재 775건)는 **이미 동작 중**입니다. `photo_uploaded`/`meal_confirmed`/`login` 3종이
  실제로 쌓이고 있고, **검색 이벤트만 발행이 안 되고 있습니다.**
- 검색 이벤트(`user.search.performed`, `properties.result_count`)를 발행해 주시면
  야간 배치가 이 테이블을 채웁니다. 그 결과가 상품 수집·정규화 우선순위가 됩니다.

`status`: `OPEN` → `SOURCING` → `ADDED` / `REJECTED`

### 3.2 `product.product_reviews` / `product.product_review_sentiment`

PR-0306(상품 리뷰)은 스키마가 아예 없어 미구현이었습니다. 테이블만 만들어 뒀습니다(0건).
`service` 스키마를 건드리지 않고 `product` 스키마에 뒀습니다 — `product_favorites`,
`product_ai_summaries` 와 같은 패턴입니다.

- 제약: `rating` 1~5, `content` 최소 5자, `(product_id, user_id)` 유니크(1인 1리뷰)
- **`is_seed` 컬럼**: 데모·시연용으로 넣은 행을 실제 사용자 리뷰와 구분합니다.
  운영 노출 시 `is_seed=true` 를 걸러내거나 "예시"로 표기할 수 있어야 합니다.
- 감정분석 결과는 `product_review_sentiment` 로 분리했습니다(모델 교체 시 재계산해야 하므로).
  `includes_seed=true` 면 실제 사용자 의견처럼 보여주면 안 됩니다.

---

## 4. 백엔드에서 고쳐야 할 것

### 4.1 `sort=sugar_asc` — 인덱스는 준비됐습니다

`service.products(sugars)` 인덱스를 추가했습니다. `EXPLAIN` 으로 `Index Scan` 확인 완료
(이전에는 Seq Scan + Sort).

- `app/services/product_store.py` 의 `_apply_search_order` 에 분기 추가 필요.
  현재 `abc` 와 기본(rank)만 있습니다.
- **현재 동작 확인 결과: 미지원 정렬값을 조용히 무시합니다.** `sort=sugar_asc` 로 호출해도
  에러 없이 관련도순 결과가 나옵니다. 미지원 값은 400 으로 거절하는 편이 낫습니다.
- 프론트(`components/ProductFeed.tsx`)에 "당류 낮은순" UI 가 이미 있지만 **클라이언트
  정렬**이라 현재 페이지만 정렬됩니다(백엔드에는 항상 `sort:"rank"` 를 보냅니다).
  서버 정렬로 바꿔주세요.

### 4.2 추가된 컬럼 (현재 전부 NULL)

```sql
service.recipes.category        TEXT      -- RC-0107 카드 필드, 크롤러가 채울 예정
service.recipes.cook_time_min   SMALLINT  -- RC-0107 카드 필드
service.products.source         TEXT      -- MFDS | MAKER | CRAWL | AI_ESTIMATE
service.products.last_verified_at TIMESTAMPTZ
```

- `recipes.category`/`cook_time_min` 은 P1-2 에서 "컬럼이 없어서 못 채운다"고 했던 항목입니다.
  **컬럼은 생겼지만 값은 아직 전부 NULL** 입니다 — 없는 값을 지어내지 않았습니다.
  응답에 포함하려면 NULL 허용으로 처리해 주세요.
- `products.source`/`last_verified_at` 은 2026-07-16 재설계로 `created_at`/`updated_at` 이
  삭제되면서 잃은 신선도·출처 추적을 대신합니다.

---

## 5. 재생성·갱신 규칙

| 대상 | 언제 다시 돌려야 하나 | 방법 |
|---|---|---|
| `product_alternatives` | 상품 추가/영양값 변경 시 | `product_embeddings` upsert **먼저**, 그다음 `005b` 재실행 (전량 교체, 7초) |
| `mv_category_sugar_stats` | 상품 적재 배치 후 | `REFRESH MATERIALIZED VIEW CONCURRENTLY` (유니크 인덱스 있음) |
| `mv_sweetener_catalog` | 태그 설명 수정 후 | 위와 동일 |
| `v_recipe_swap_ranking` | 불필요 (일반 뷰) | — |

**순서 주의**: `product_embeddings` 를 갱신하지 않고 `005b` 만 돌리면 낡은 벡터로 대안이
만들어집니다.

---

## 6. 대안 품질 기준 (조정하려면 여기)

`005b_fill_product_alternatives.sql` 의 후보 규칙입니다.

1. 같은 CATEGORY와 같은 `food_type` 안에서만
2. `serving_value`가 같고 `g ↔ g`, `mL ↔ mL`처럼 비교 단위가 같을 것
3. 원본이 이미 저당·제로로 표시된 상품이 아닐 것
4. 당류가 실제로 더 낮을 것
5. **유사도 ≥ 0.70**
6. 최소 0.5g 이상 낮으면서, 2g 이상 줄거나 20% 이상 줄 것
7. 상품당 상위 5개

**유사도 0.70 의 근거** (구간별 무작위 6쌍 육안 검수, 2026-08-09):

| 구간 | 판정 | 예시 |
|---|---|---|
| 0.60~0.65 | 쓸 수 없음 | 노니주스 → 토마토주스, 통밀스콘 → 녹차양갱 |
| 0.70~0.75 | 쓸 만함 | 저당치폴레소스 → 저당 굴소스 |
| 0.80~ | 매우 정확 | 저당 스위트 칠리 소스 → 저칼로리 스위트 칠리 소스 |

카테고리가 11종뿐이라 성깁니다(토스트소스와 오트밀이 같은 `베이커리·간식`).
**카테고리 필터만으로는 못 거르고, 유사도 하한이 실질적인 안전장치입니다.**
임계값을 낮추면 커버리지는 늘지만 오매칭이 바로 늘어납니다.

---

## 7. 알려진 한계 (넘겨드리는 그대로)

| 항목 | 현황 | 영향 |
|---|---|---|
| 레시피 대체 커버리지 | 1,722건 중 **359건(21%)** | SwapCard 를 레시피에 붙여도 79%는 빈 상태 |
| 상품 대안 커버리지 | 당류>0 인 1,551건 중 **757건(49%)** | 위 표 참고 |
| `brand_name` 결측 | **1,446건(59%)** | 카드·SwapCard 에 브랜드가 절반 이상 빔 |
| `ingredient_text` 결측 | 366건(15%) | 감미료·알레르기 자동 태깅 불가 |
| `manufacturer_name` 결측 | 367건 | 식약처 대조 키 약함 |
| `purchase_url` 결측 | 74건 | 구매 연결 끊김 |
| 외부 핫링크 이미지 | 25건 | 나머지 2,413건은 MinIO. 이 25건은 깨질 수 있음 |
| `user_preferences` | **0건** | 관심 카테고리·알레르기가 하나도 저장 안 됨 — 저장 경로 확인 필요 |
| `meal_items.product_id` 연결 | 292건 중 **9건(3%)** | "취향 기반" 개인화는 아직 근거 부족 |

결측 필드들은 **값을 지어낼 수 없어** 채우지 않았습니다. 식약처 API 대조나 수동 입력이
선행돼야 합니다.

---

## 8. 상품 정제 작업 (2026-08-09) — 조회 대상 교체 필요

`service.products` 테이블의 **컬럼·제약은 건드리지 않았습니다.** 행 삭제와 뷰 추가만
있었으므로 기존 코드는 그대로 동작하되, 아래 뷰로 바꿔야 개선이 화면에 반영됩니다.

### 8.1 `service.v_product_display` — 검색·상세·카드용 (2,427건)

브랜드명이 상품명에 없으면 앞에 붙여 `display_name` 을 만들어 줍니다.
**970건의 표시명이 바뀝니다.**

| 원래 `product_name` | `display_name` |
|---|---|
| 딸기 | 웰치스 딸기 |
| 제로 | 코카콜라 제로 |
| 망고 | 분다버그 망고 |
| 논알콜 | 버드와이저 제로 논알콜 |

검색 결과에 `딸기`, `제로` 같은 검색어 수준 이름이 그대로 노출되던 문제
(PRODUCTION_HANDOFF P1-6)를 코드 변경 없이 해소합니다.

> `brand_name` 결측 1,446건에는 접두가 붙지 않습니다 — 그 건들은 여전히 원래 이름 그대로입니다.

### 8.2 `service.v_product_swap_pick` — 스왑/추천 전용 (2,158건)

`report_no`(식약처 품목보고번호) 기준으로 같은 제품의 여러 등록 건을 **대표 1건으로 압축**합니다.
2,427건 → 2,158건, **269건이 대표 뒤로 접힘.**

```
product_id, display_name, product_name, brand_name, report_no, food_type,
sugars, calories, image_url, variant_count, variant_brands
```

- 묶인 그룹은 **영양성분이 100% 동일함을 확인한 뒤** 처리했습니다.
- `variant_count` / `variant_brands` 로 **"다른 브랜드 N개"** 표시가 가능합니다.
- 대표 사례: 알룰로스 10개 브랜드 → 1건, 도시곳간 반찬세트 7종 → 1건.

**목록(display)에서는 2,427건 전부 노출하고, 스왑 카드에서만 압축본을 쓰세요.**
스왑 추천에 같은 제품이 브랜드만 바꿔 여러 번 뜨는 걸 막는 게 목적입니다.

### 8.3 삭제된 상품 11건 (2,438 → 2,427)

| 사유 | 건수 | 예 |
|---|---:|---|
| 화장품 | 4 | 모공패드, 마데카크림, 스킨크림 |
| 반려동물 | 3 | 다이어트 관절 사료, 황태파우더·황태포 |
| 생활용품 | 2 | UV차단 우양산, 샴푸 |
| 주방용품 | 1 | 우드 조리도구 모음 |
| 상품 아님 | 1 | "달걀·닭가슴살 모아보기" — 크롤러가 카테고리 목록 페이지를 상품으로 오인 |

- 전부 삭제 전에 **`curation.removed_products` 에 원본 행 + 태그를 JSONB 로 백업**했습니다
  (`product_row`, `tag_rows`, `reason`, `removed_at`, `removed_by`). 되돌릴 수 있습니다.
- 삭제 시점에 FK 참조(스왑·식단기록·찜)는 전부 0건이었습니다.

### 8.4 삭제 여파와 후속 조치 (완료)

상품 삭제가 파생 데이터에 반영되지 않아 아래를 처리했습니다.

1. **`product_alternatives` 고아 행 1건 발생** — 삭제된 '제로스킨 MD 크림'을 기준 상품으로
   하는 대안 행이 남아 있었습니다. `product_alternatives` 에 FK 가 없어 연쇄 삭제가
   안 됐던 것입니다. → **005b 재실행으로 정리** (2,522 → **2,521쌍**, 상품 757개 커버).
2. **FK 추가 (`010_alternatives_fk.sql`)** — `product_id` / `alt_product_id` 양쪽에
   `ON DELETE CASCADE`. 이제 상품이 지워지면 대안 행도 함께 지워집니다.
   `recipe_ingredient_products`, `product_embeddings` 와 같은 방식입니다.
3. **매터리얼라이즈드 뷰 갱신** — 음료 995→994, 베이커리·간식 437→432 등 반영.
4. **컬렉션 부제 숫자 동기화** — "음료 994종 중 569종이 당류 0g".

> **앞으로 상품을 지우거나 추가하면**: `product_embeddings` upsert → `005b` 재실행 →
> `REFRESH MATERIALIZED VIEW CONCURRENTLY` 2건 → 컬렉션 부제 숫자 확인. 5절 표 참고.

### 8.5 손대지 않고 남긴 것

- **고당류인데 "저당" 표기 상품 53건** — 요청에 따라 유지. 표시명·검색에 그대로 나옵니다.
- **저당과 무관한 일반 식재료 13건** (번데기·발효맛술·동치미·나또·참치 등) — 명백한 오류는
  아니라고 보고 판단 보류. 목록이 필요하면 데이터 파트에 요청하세요.
- **`제로스킨 MD 크림` 재확인 권장** — 화장품으로 분류해 삭제했지만, 해당 행의
  `food_type` 은 `빵류`였고 `ingredient_text` 는 아몬드분말·생크림·에리스리톨 등
  식품 원재료였습니다. 분류가 틀렸을 가능성이 있으니 필요하면
  `curation.removed_products` 에서 복원하세요.

---

## 9. 실측 검증·권한·운영 상태

### 9.1 스테이징 적용 결과

대상은 `dang-be-ns-stg/dang-stg-pg-1`, PostgreSQL 17.10, database `zero`입니다.
`003~012`를 위 순서로 적용했고 재실행도 전부 성공했습니다. `staging_sample_data.sql`로
실제 개인정보가 아닌 고정 샘플을 넣고 `005b`를 다시 실행했습니다.

| 검증 대상 | 스테이징 결과 |
|---|---:|
| `v_product_display` | 13건 |
| `v_product_swap_pick` | 7건 |
| `v_recipe_swap_ranking` | 2건 |
| `product_alternatives` | 11쌍 |
| `mv_category_sugar_stats` | 5건 |
| `mv_sweetener_catalog` | 3건 |
| 공개 `content.collections` | 6건 |
| `content.articles` | 9건, 기존 8건은 비공개·본문 없음 + 검증용 공개 1건 |
| `product.product_reviews` | `is_seed=true` 3건 |
| `product.product_review_sentiment` | `includes_seed=true` 1건 |
| 상품 연결 식단 기록 | 1건 |
| 사용자 선호 설정 | 1건 |

`v_product_swap_pick.variant_count`가 2보다 큰 샘플 5건, 당류 0g이며 대안이 없는
샘플 3건, 레시피 랭킹 2건, 리뷰·감정·식단·선호 샘플을 `staging_validation.sql`로
실제 조회합니다. 시드 실행은 자동 배포에 포함하지 않는 수동 절차입니다.

### 9.1.1 운영 기준값 확정

운영 DB를 재조회한 최신 기준은 다음과 같습니다. 문서 앞·뒤에 남아 있던 이전 값은
백필 전 수치이며 백엔드 테스트 기준으로 사용하지 않습니다.

| 항목 | 최신 기준값 |
|---|---:|
| 상품 | 2,427건 |
| 상품 대안 | 2,521쌍 / 757개 상품 |
| 음료 | 994개 / 당류 0g 569개 |
| 중복 압축 결과 | 2,158건 |

### 9.2 정확한 상품 뷰 정의와 타입

`v_product_display`와 `v_product_swap_pick`은 기존 003~010 원본에는 없었고,
운영 DB에서 별도 정제 작업으로 먼저 생성된 객체였습니다. 운영 정의를 그대로
`011_product_display_views.sql`에 보관했습니다.

- `display_name`: `text`
- `variant_count`: `bigint`
- `variant_brands`: `character varying[]`
- `v_product_display`: 상품명·브랜드·영양값·이미지·`brand_prefixed`를 반환하고
  `curation.removed_products`에 있는 상품을 제외합니다.
- `v_product_swap_pick`: `report_no`별 `DISTINCT ON` 대표 1건과 variant 집계를 반환합니다.

리뷰 테이블에는 `created_at`과 `updated_at`이 모두 `timestamptz NOT NULL DEFAULT now()`로
있습니다. 자동 수정 시각 트리거는 없습니다.

현재 리뷰·감정·검색 누락 큐에는 `products`/`users` FK가 없고, 콘텐츠에서는
`content.collection_products.slug → content.collections.slug ON DELETE CASCADE`만 있습니다.
상품 대안은 `010`에서 양쪽 상품 FK와 `ON DELETE CASCADE`를 적용합니다. 제약은 각 SQL과
운영 `pg_constraint` 조회 결과를 기준으로 합니다.

### 9.3 계정·RLS

운영과 스테이징에서 확인된 로그인 role은 공용 `yesman`이며, 별도 Product/Main/Refresh
로그인 role은 확인되지 않았습니다. 스테이징 Secret 이름은 `dang-stg-pg-secret`이고
키 이름은 `postgres_user`/`postgres_password`입니다. 비밀번호는 문서화하지 않습니다.

새 오브젝트의 owner는 `postgres`라서 `yesman`에는 처음에 권한이 없었습니다.
`012_service_permissions.sql`을 스테이징에 적용해 새 뷰·테이블 SELECT, 리뷰 CRUD,
`service.event_outbox` INSERT를 부여했습니다. 운영 권한 변경은 별도 승인 전까지 적용하지
않았습니다. 대상 오브젝트의 RLS는 운영·스테이징 모두 비활성이고 정책은 0건입니다.

`REFRESH MATERIALIZED VIEW`는 일반 GRANT가 아니라 owner 권한이 필요합니다. 현재 matview
owner는 `postgres`이며 앱 role에 owner 권한을 올리지 않았습니다. 전용 refresh Job/계정과
Secret 이름이 확정되면 그 계정으로 `REFRESH MATERIALIZED VIEW CONCURRENTLY`를 운영화해야 합니다.

### 9.3.1 운영 권한 적용 계획

`012_service_permissions.sql`은 현재 스테이징에만 적용되어 있습니다. 운영 적용은 다음
조건으로 진행합니다.

| 항목 | 계획 |
|---|---|
| 승인 담당 | DB 운영 승인자 + Product/Main 서비스 오너 공동 승인 |
| 적용 시점 | 백엔드 배포 직전의 운영 변경 창, 배포 T-1 체크에서 승인 여부 확정 |
| 적용 순서 | 백엔드 배포 전에 `012_service_permissions.sql` 실행 |
| 적용 대상 | 현재 운영 공용 role `yesman`; 비밀번호는 Secret에서만 읽음 |
| matview 권한 | `yesman`에 부여하지 않음. 전용 owner/refresh Job으로 분리 |
| 롤백 | 아래 REVOKE 문을 역순으로 실행하고 애플리케이션 배포를 중단 |

적용 후 검증 SQL:

```sql
SELECT has_schema_privilege('yesman', 'service', 'USAGE')
   AND has_schema_privilege('yesman', 'product', 'USAGE')
   AND has_schema_privilege('yesman', 'content', 'USAGE') AS schema_usage_ok;
SELECT has_table_privilege('yesman', 'service.v_product_display', 'SELECT')
   AND has_table_privilege('yesman', 'service.v_product_swap_pick', 'SELECT')
   AND has_table_privilege('yesman', 'product.product_alternatives', 'SELECT')
   AND has_table_privilege('yesman', 'product.product_reviews', 'SELECT,INSERT,UPDATE,DELETE')
   AND has_table_privilege('yesman', 'service.event_outbox', 'INSERT') AS yesman_grants_ok;
SELECT relname, relowner::regrole
FROM pg_class
WHERE (relnamespace::regnamespace::text, relname) IN
      (('service','mv_category_sugar_stats'), ('service','mv_sweetener_catalog'));
```

운영에서는 `012` 적용 전까지 새 뷰 조회 및 리뷰 CRUD가 보장되지 않으므로, 해당 기능을
활성화하는 백엔드 배포보다 먼저 권한 검증을 통과해야 합니다.

### 9.4 검색 이벤트 개인정보 정책 및 운영 자동화

- 현재 이벤트 토픽은 `user.activity.raw`이며 outbox publisher 배포는 운영에 있습니다.
- 운영 `service.event_outbox`에는 `user.search.performed`가 아직 0건입니다. 현재 확인된
  이벤트는 로그인·사진 업로드·분석 완료·식단 확정뿐입니다.
- `user.search.performed`는 개인정보 최소화 정책으로 확정합니다.
  - 검색어 원문은 Kafka, `event_outbox`, PostgreSQL에 저장하지 않습니다.
  - 저장 식별자는 환경별 Secret의 HMAC 키로 만든 HMAC-SHA-256 해시만 사용합니다. 단순
    SHA-256은 사전 대입이 가능하므로 사용하지 않습니다.
  - 정규화 전 길이를 기록하지 않고, 정규화 후 `query_length`만 최대 128자로 제한합니다.
  - 로그인 사용자는 기존 PostgreSQL `public.users.id`를 `user_id`로 사용합니다. 비로그인
    검색은 현재 v1 계약으로 발행하지 않으며, v2에서 `user_id=null`과 HMAC `session_hash`를
    추가한 뒤에만 허용합니다. 임의의 사용자 ID 0이나 가짜 public user를 만들지 않습니다.
  - 이메일·전화번호·주민등록번호·계좌/카드번호·인증 토큰·건강/성/법률 등 민감 범주로
    판정된 검색은 해시도 만들지 않고 `result_count`와 이벤트 시각만 관측합니다.
  - 이벤트 필수 필드는 `event_id`, `event_type`, `user_id`, `occurred_at`, `producer`,
    `schema_version`, `properties`; `query`는 금지하고 `properties.query_hash`,
    `properties.query_length`, `properties.result_count`를 사용합니다.
  - `search_miss_queue`에는 현재 `query_norm` 컬럼을 원문이 아닌 HMAC 해시 저장 슬롯으로
    취급하고, 최종 필드는 `query_hash(64자)`, `query_length`, `miss_count`,
    `first_seen_at`, `last_seen_at`, `status`, `resolved_product_id`, `note`입니다.
  - Kafka 보존은 기존 7일, outbox 발행 완료 행은 30일, `search_miss_queue`의 해결 행은
    30일 후 삭제하고 미해결 행은 90일 재평가 후 보존 여부를 결정합니다.

운영 자동화 담당과 일정은 다음처럼 지정합니다. 현재 클러스터에는 이 이름의 Job이 아직
배포되어 있지 않으므로, 아래는 배포할 운영 Job의 고정 계약입니다.

| 작업 | Job/CronJob | 담당 | 일정(KST) | 실패 시 | 수동 재실행 |
|---|---|---|---|---|---|
| `product_embeddings` 갱신 | `zero-db-product-refresh` 1단계 | Infra/DB | 매일 03:00 | Kubernetes Job 실패 알림 + 운영 온콜 | 임베딩 upsert 후 2단계부터 재실행 |
| `005b` 대안 재생성 | `zero-db-product-refresh` 2단계 | Infra/DB | 03:15 | 동일 | `psql -f migrations/005b_fill_product_alternatives.sql` |
| 두 matview 갱신 | `zero-db-product-refresh` 3단계 | Infra/DB | 03:30 | 동일 | 두 `REFRESH MATERIALIZED VIEW CONCURRENTLY` 실행 |
| 컬렉션 부제 동기화 | `zero-db-product-refresh` 4단계 | Infra/DB + Content | 03:35 | 동일 | 최신 MV 수치로 동기화 SQL 실행 |
| 검색 누락어 야간 배치 | `zero-search-miss-nightly` | Product + Infra/DB | 매일 04:00 | Kubernetes Job 실패 알림 + Product 온콜 | 정책 검증 후 queue batch 재실행 |

matview 단계는 앱 계정이 아니라 별도 owner/refresh Secret을 사용하는 것으로 고정합니다.
배포 전까지는 기존 수동 순서인 `product_embeddings` 갱신 → `005b` → 두 matview → 부제
검증을 사용합니다.

### 9.5 체크섬

원본 전달 시 `infra/zero-infra/kafka/migrations/SHA256SUMS`를 함께 첨부합니다. 재검증은
다음처럼 실행합니다.

```bash
cd infra/zero-infra/kafka/migrations
sha256sum -c SHA256SUMS
```
