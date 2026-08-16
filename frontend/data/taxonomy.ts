export const PRODUCT_CATEGORIES = [
  { code: "PROCESSED_FOOD", label: "가공식품" },
  { code: "CONVENIENCE_NOODLE", label: "간편식·면류" },
  { code: "NUT_SEED", label: "견과·씨앗" },
  { code: "GRAIN_CEREAL", label: "곡물·시리얼" },
  { code: "BAKERY_SNACK", label: "베이커리·간식" },
  { code: "SAUCE_SEASONING", label: "소스·조미" },
  { code: "PLANT_PROTEIN", label: "식물성 단백질" },
  { code: "DAIRY", label: "유제품" },
  { code: "BEVERAGE", label: "음료" },
  { code: "JAM_SPREAD", label: "잼·스프레드" },
  { code: "SPECIAL_NUTRITION", label: "특수영양식" },
] as const;

export type ProductCategory = typeof PRODUCT_CATEGORIES[number]["label"];

// 2026-08-16 개편 - 이전 8개(한 끼/국·찌개/반찬/샐러드/간식/면/분식/소스)는 분류
// 축이 3개 섞여 있어 배타적일 수 없었다: 한 끼=역할, 면·분식=형태, 반찬·소스=식탁에서의
// 역할, 간식=먹는 때. `비빔국수`는 형태로는 면, 역할로는 한 끼라 어느 쪽도 틀리지 않아
// 판정이 늘 흔들렸다. 축을 "끼니에서의 역할" 하나로 통일하고 4개로 줄였다.
//
// service.recipes.category 는 이제 채워져 있다(1,677건 백필, 2026-08-16). 미판정 32건은
// 이름이 요리명이 아니라 제목 문장이라(예: "다이어트 한끼 배부름") NULL 로 남겼고,
// 그 경우에만 useRecipeCatalog.ts 의 inferCategory() 폴백이 돈다.
export const RECIPE_CATEGORIES = ["한 끼", "간식", "음료", "양념·소스"] as const;
export type RecipeCategory = typeof RECIPE_CATEGORIES[number];

export const HEALTH_LABELS = [
  "제로",
  "제로슈거",
  "제로칼로리",
  "저당",
  "저칼로리",
  "무가당·무첨가당",
  "고단백",
] as const;

export const SWEETENER_FILTERS = ["알룰로스", "에리스리톨", "말티톨", "수크랄로스", "스테비아"] as const;

// 2026-07-30 QA 리포트 - 가입 화면(SignupProfileForm)과 마이페이지 "주의할 성분
// 바꾸기"(PersonalPage)가 각자 다른 하드코딩 목록을 썼다(마이페이지 쪽은 개수도
// 다르고 견과류/달걀/갑각류처럼 더 뭉뚱그린 이름을 씀). 그 결과 가입 때 고른
// 성분이 마이페이지 편집 화면 옵션에 없어서, 편집 화면을 열면 실제로 갖고 있는
// 주의 성분 중 일부만 선택 표시되고 나머지는 편집기에서 보이지도 선택되지도
// 않는 불일치가 있었다. 두 화면이 이 하나의 목록만 쓰도록 통일한다.
export const ALLERGEN_OPTIONS = ["우유", "대두", "땅콩", "호두", "밀", "난류", "새우", "게", "복숭아", "토마토"] as const;
export type AllergenOption = typeof ALLERGEN_OPTIONS[number];
