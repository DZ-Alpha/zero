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

// 2026-07-31 요청 - 카테고리가 너무 적어 대부분의 실제(비목업) 레시피가 "한 끼"
// 하나로 몰렸다. service.recipes 테이블엔 category 컬럼이 없어(데이터팀 스키마
// 추가 필요, useRecipeCatalog.ts 참고) 실서버 카테고리를 직접 못 받으니, 그때까지
// 이름 기반 추정이 더 세분화되도록 국·찌개/샐러드를 추가해 분포를 넓힌다.
export const RECIPE_CATEGORIES = ["한 끼", "국·찌개", "반찬", "샐러드", "간식", "면", "분식", "소스"] as const;
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
