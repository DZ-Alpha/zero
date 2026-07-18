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

export const RECIPE_CATEGORIES = ["한 끼", "반찬", "간식", "면", "분식", "소스"] as const;
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
