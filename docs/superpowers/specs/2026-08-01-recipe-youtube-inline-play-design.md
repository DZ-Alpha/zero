# 레시피 상세 페이지 유튜브 인라인 재생 설계

- 작성일: 2026-08-01
- 대상: 레시피 상세 페이지(`/recipes/{id}`)의 썸네일 영역에서 유튜브 영상을 인라인 재생
- 브랜치: `feature/recipe-youtube-inline-play`

## 배경 / 문제

유튜브에서 수집한 레시피는 원본 조리 영상이 있지만, 현재 상세 페이지는 정지 썸네일 이미지만
보여준다. 사용자가 사진 부분을 눌러 조리 영상을 바로 볼 수 있게 한다.

## 핵심 사실 (조사 결과)

**DB 컬럼 추가·링크 수집이 필요 없다.** `video_id`는 이미 존재하고 채워져 있다.

- `service.recipes.video_id` (VARCHAR(100)) — 유튜브 레시피는 값이 있고, 만개의레시피는 없음(NULL).
- 백엔드 `recipe-service`의 `Recipe` 모델에 이미 매핑됨:
  `backend/recipe-service/app/models/recipe.py:18` (`video_id: Mapped[str]`).
- 백엔드가 이미 `video_id`로 유튜브 공개 썸네일 URL을 생성 중:
  `backend/recipe-service/app/routers/recipe.py:32-33`
  (`https://img.youtube.com/vi/{video_id}/hqdefault.jpg`).

즉 `video_id`는 조회 가능하지만 **상세 API 응답 DTO에 실려 있지 않아 프론트로 나가지 않는다.**
따라서 이 작업은 DB/수집 작업이 아니라 **이미 있는 `video_id`를 API → 프론트 → 화면까지
노출하는 배관 작업**이다.

## 데이터 흐름

```
DB service.recipes.video_id  (이미 존재·유튜브 레시피는 채워짐)
  → recipe-service Recipe 모델 (recipe.py:18, 이미 매핑됨)
  → GET /recipes/{id} 응답 DTO      ← [변경①] videoId 추가
  → 프론트 RecipeDetailResponse 타입 ← [변경②] videoId 추가
  → RecipeDetail.tsx detail 객체     ← [변경③] videoId 전달 (+ RecipeData 타입)
  → RecipeCover.tsx 썸네일 렌더       ← [변경④] 재생 버튼 + 인라인 iframe
```

## 결정 사항 (확정)

- 적용 범위: **상세 페이지만** (목록 카드는 지금처럼 썸네일만, 목록 API 미변경).
- 영상 없는 레시피(video_id NULL, 예: 만개의레시피 "고등어 솥밥"): **재생 버튼 숨김**,
  기존과 동일하게 정지 이미지만 표시.
- 임베드 방식: **직접 iframe** (`youtube.com/embed/{videoId}`), 추가 라이브러리 없음.
- 재생 UX: **사진 자리에서 인라인 재생** — 썸네일 클릭 시 그 자리에서 iframe으로 교체.
- 지연 로딩: 클릭 전에는 iframe을 로드하지 않는다(초기 성능 영향 없음).

## 변경 상세

### ① 백엔드 — `backend/recipe-service/app/routers/recipe.py`
`get_recipe_detail`(117~142줄)의 응답 dict에 한 줄 추가:
```python
"videoId": recipe.video_id,   # 유튜브 레시피면 ID, 아니면 None
```
`recipe.video_id`는 이미 모델에 매핑돼 있어 추가 조회 불필요.
목록 응답(`_list_item`)은 변경하지 않는다.

### ② 프론트 타입 — `frontend/lib/api/zerocheck.ts`
`RecipeDetailResponse`(20~40줄)에 필드 추가:
```typescript
videoId?: string | null;
```

### ③ 프론트 변환 — `frontend/components/RecipeDetail.tsx` + `frontend/data/catalog`
- `RecipeData` 타입(`@/data/catalog`)에 `videoId?: string | null` 추가.
- `RecipeDetail.tsx`의 `detail` useMemo(84~109줄)에 `videoId: live?.videoId ?? fallbackDetail.videoId`
  매핑 추가. (fallback 카탈로그엔 없으므로 사실상 `live?.videoId`.)

### ④ 프론트 UI — `frontend/components/RecipeCover.tsx`
- 현재 `RecipeCover.tsx`는 `"use client"`가 없는 서버 컴포넌트다(실측). 파일 최상단에
  `"use client"`를 추가하고 `useState<boolean>(isPlaying)` 도입.
- `hero === true` **그리고** `recipe.videoId`가 있을 때만 썸네일 위에 재생 버튼(▶) 표시.
- 재생 버튼 클릭 → `isPlaying=true` → 이미지 자리에
  `<iframe src="https://www.youtube.com/embed/{videoId}?autoplay=1&rel=0" allow="autoplay; encrypted-media; fullscreen" allowfullscreen />` 렌더.
- `videoId` 없거나 `hero`가 아니면 기존 동작(정지 이미지)과 완전히 동일.
- 접근성: 재생 버튼은 `<button aria-label="영상 재생">`, iframe에는 `title` 속성.

재생 상태를 `RecipeCover` 내부에 두는 이유: 히어로 이미지 영역이 이 컴포넌트에 캡슐화돼 있어
(RecipeDetail.tsx:145 `<div className="detail-hero-image"><RecipeCover recipe={detail} hero /></div>`)
상태를 국소화하면 다른 컴포넌트에 영향이 없다.

## 안 하는 것 (YAGNI)

- DB 마이그레이션 / 컬럼 추가 (이미 있음)
- 유튜브 링크 수집·백필 (이미 채워짐)
- 목록 카드 재생, 재생 모달/팝업, react-player, lite-youtube-embed
- 백엔드 목록(`_list_item`) 응답 변경

## 엣지 케이스

- `video_id`가 NULL(만개의레시피): 재생 버튼 숨김 — 기존 정지 이미지 유지.
- `video_id`가 있으나 영상이 비공개/삭제됨: iframe이 유튜브 자체 오류 화면을 표시(허용).
  별도 사전 검증은 하지 않는다(API 키·쿼터 불필요 원칙 유지).
- 상세 로딩 중(fallbackDetail): `videoId` 없음 → 버튼 없음. 로드 완료 후 나타남.

## 검증

- 백엔드: `GET /recipes/{유튜브레시피 id}` 응답에 `videoId` 포함 확인 /
  만개의레시피 id 응답은 `videoId: null` 확인. recipe-service 기존 테스트 회귀 없음.
- 프론트: 유튜브 레시피 상세 → ▶ 버튼 표시 → 클릭 → 인라인 재생 /
  만개의레시피(고등어 솥밥) 상세 → 버튼 없음. 프론트 빌드·타입체크 통과.
