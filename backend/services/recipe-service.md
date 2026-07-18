# Recipe Service (레시피)

## 소유 데이터

`service-db-v1.0`에는 레시피 콘텐츠 테이블이 **전혀 없다**. 이 서비스는 자체 스토리지(별도 Postgres 스키마/DB든 다른 저장소든)를 새로 설계해야 한다.

다른 테이블들이 레시피를 참조하는 방식을 보면 최소한 아래 필드는 있어야 한다:

- 레시피를 유일하게 식별하는 ID (다른 서비스가 문자열로 참조하므로 형식은 자유롭되 `VARCHAR(100)` 안에 들어가야 함)
- 이름, 재료 목록, 조리법, 대표 이미지
- (RC-0110) 기본 레시피 대비 저당 버전 비교를 위한 칼로리/당류 정보

## 다른 서비스와의 연결 방식: 느슨한 참조

- `service.meal_items.external_recipe_id` (Diet Service)

**DB 레벨 FK가 없는 VARCHAR(100) 문자열**이다. 즉 Recipe Service가 레시피를 삭제해도 다른 서비스 DB에서 자동으로 정리되지 않는다 — 레시피 삭제 시 이벤트를 발행하거나, 참조하는 서비스가 주기적으로 유효성을 검증해야 한다. 반대로 이 설계 덕분에 Recipe Service는 완전히 독립된 DB/스키마를 가져도 다른 서비스에 영향이 없다.

## 담당 기능 (기능명세서 기준)

| 기능ID | 설명 |
|---|---|
| RC-0107 | 저당 레시피 목록 |
| RC-0108 | 레시피 상세 (재료, 요리법) |
| RC-0109 | AI 대체 상품 추천 (레시피 재료 → 제로/저당 상품) — **Product Service 검색 API 호출 필요** |
| RC-0110 | 저당 vs 기본 레시피 당/칼로리 비교 요약 |
| RC-0111~0112 | 레시피 찜 등록/해제(`POST /recipes/favorite`), 찜 목록(`GET /recipes/favorite/list`) — `recipe.recipe_favorites`(PK `(recipe_id, user_id)`)를 이 서비스 전용 신규 `recipe` 스키마에 둔다. `service`는 데이터팀 소유라 건드리지 않음. `Authorization: Bearer` 헤더 인증(이 서비스가 처음으로 인증을 다루는 기능이라 `app/core/auth.py` 신규 추가) |

## 참고

- RC-0109(대체 상품 추천)는 이 서비스 데이터만으로 못 끝난다. 레시피 재료명을 Product Service의 검색/카테고리 필터 API에 넘겨서 대체 상품을 찾아와야 한다 — 두 서비스 간 동기 호출이 필요한 지점.
- 즐겨찾기(`user_favorites.external_recipe_id`)에 잡힌 레시피가 실제로 존재하는지 확인하는 API(`GET /recipes/{id}/exists` 같은 것)를 열어두면 Diet/Main 쪽에서 깨진 링크를 걸러내기 쉽다.
