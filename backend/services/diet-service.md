# Diet Service (제로식단)

## 소유 데이터

- `service.meal_logs` (PK `meal_log_id` UUID, FK `user_id` → `public.users(id)`)
- `service.meal_items` (PK `meal_item_id` UUID, FK `meal_log_id` → `meal_logs`, FK `product_id` → `service.products`(nullable))
- view `service.v_meal_totals` (meal_log 단위 칼로리/당류/탄수화물 합계)

## 참조하는 외부 데이터 (읽기 전용)

- `public.users(id)` — JWT에서 나온 `user_id`를 그대로 사용, User/Auth 서비스에 별도 조회 불필요
- `service.products` — 식단에 상품을 추가할 때 이름/영양정보를 **스냅샷으로 복사**해서 `meal_items`에 저장(아래 참고)

## 핵심 설계: 이력 스냅샷

`meal_items`는 상품이 나중에 바뀌어도 과거 기록이 변하지 않도록 `item_name`/`calories`/`sugars`/`carbohydrate`를 섭취 당시 값으로 **복제 저장**한다. 즉:

- 식단에 상품 추가 시: `service.products`에서 현재 값을 읽어와 `meal_items`에 그대로 insert (참조가 아니라 복사)
- `product_id`는 "원본이 어떤 상품이었는지" 링크용일 뿐, 표시할 영양값은 항상 `meal_items` 자체 컬럼에서 읽는다
- 원본 상품이 삭제되면 `product_id`는 `ON DELETE SET NULL`로 NULL이 되지만 스냅샷 값은 그대로 남는다

## 레시피 참조는 느슨하다

`meal_items.external_recipe_id`(VARCHAR)는 Recipe Service의 레시피 ID를 문자열로만 들고 있고 **DB FK가 없다**. 레시피 존재 여부 확인이 필요하면 Recipe Service API를 호출해야 한다. `product_id`와 `external_recipe_id`는 동시에 채워질 수 없다(CHECK 제약).

## 담당 기능 (기능명세서 기준)

| 기능ID | 설명 | 참고 |
|---|---|---|
| RC-0101~0102 | 한끼/하루 식단 사진 업로드 | `meal_logs` insert (`input_type='VISION'`, `analysis_status='PENDING'`). `mealType`/`eatenAt`은 선택값(PRODUCTION_HANDOFF.md P0-3) — 안 보내면 기존처럼 `mode` 기반 기본값/업로드 시각을 쓴다 |
| RC-0103 | AI 식단 분석 (실제 구현) | `app/services/vision_service.py` — Claude Vision(`claude-opus-4-8`)으로 사진 속 음식 항목(이름/제공량/칼로리/당류/탄수화물)을 구조화 출력으로 추정, `meal_items` insert 후 `analysis_status='COMPLETED'`. `ANTHROPIC_API_KEY` 없으면 기존과 동일하게 `PREPARING` 반환(무비용 폴백) |
| RC-0104 | OCR 분석 결과로 식단 항목 채우기 | 아직 미구현 — OCR 전용 파이프라인 필요(`services/알릴거.md` 2번 참고) |
| RC-0105 | 대체 제품 추천 | Product Service 검색 API 호출(이 서비스 데이터 아님) |
| RC-0106 | 캘린더 (날짜별 식단) | `meal_logs.eaten_at` 기준 조회 |
| MN-0106~0108 | 홈 당/칼로리 게이지 | `v_meal_totals`를 하루 단위로 재집계 |
| RC-0113 | 식단 기록 생성 | `POST /diet/records` — 레시피/상품/사진 공통 모델. `meal_log`(1) + `meal_item`(1)을 즉시 `COMPLETED` 상태로 생성. `Authorization: Bearer` 헤더 인증 |
| RC-0114 | 식단 기록 수정 | `PUT /diet/records/{id}` — mealType/serving/sugar/calories 부분 수정 |
| RC-0115 | 식단 기록 삭제 | `DELETE /diet/records/{id}` — meal_item + meal_log 함께 삭제 |
| RC-0116 | 식단 기록 날짜별/월별 조회 | `GET /diet/records?date=` — 그 날짜의 합계+항목 목록. `?year=&month=` — 날짜별로 묶어서 각 날짜의 합계+항목 목록을 한 응답에 담는다(PRODUCTION_HANDOFF.md P1-3, 캘린더 N+1 제거) |
| RC-0117 | 업로드 취소 | `DELETE /diet/upload/{id}` — `analysis_status != COMPLETED`인 draft만 취소 가능(확정된 건 409, RC-0115로 삭제) |

## 참고 쿼리

```sql
-- 하루 칼로리/당 합계 (MN-0106~0108). v_meal_totals는 meal_log 단위라 애플리케이션에서 하루로 묶는다.
SELECT date_trunc('day', ml.eaten_at) AS day,
       sum(vt.total_calories) AS calories,
       sum(vt.total_sugars) AS sugars
FROM service.meal_logs ml
JOIN service.v_meal_totals vt ON vt.meal_log_id = ml.meal_log_id
WHERE ml.user_id = $1 AND ml.eaten_at >= $2 AND ml.eaten_at < $3
GROUP BY 1;

-- 캘린더 (RC-0106)
SELECT meal_log_id, eaten_at, meal_type
FROM service.meal_logs
WHERE user_id = $1 AND eaten_at >= $2 AND eaten_at < $3
ORDER BY eaten_at;
```

## 미정 항목 (해결됨)

- ~~`user_favorites`(즐겨찾기)를 이 서비스가 가질지, User 쪽에 둘지~~ → **2026-07-18 명세(PR-0307/0308, RC-0111/0112)로 해결**: 하나의 경계 테이블 대신 상품 찜은 `product.product_favorites`(Product Service), 레시피 찜은 `recipe.recipe_favorites`(Recipe Service)로 각자 소유 도메인에 나눠 만들었다. Diet Service는 찜 데이터를 갖지 않는다.
