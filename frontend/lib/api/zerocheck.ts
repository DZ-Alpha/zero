import { apiRequest } from "@/lib/api/client";

export type GaugeResponse = {
  cal: number;
  sugar: number;
  calorieTarget?: number | null;
  sugarTarget?: number | null;
  cal_target?: number | null;
  sugar_target?: number | null;
};

export type RecipeListItem = {
  id: number;
  name: string;
  thumbnailUrl?: string | null;
  sugarReductionPct?: number | null;
  comparisonStatus?: string | null;
};

export type RecipeDetailResponse = RecipeListItem & {
  steps?: unknown;
  source?: string | null;
  publishedAt?: string | null;
  nutrition?: {
    totalSugarG?: number | null;
    totalKcal?: number | null;
    baseSugarG?: number | null;
    baseKcal?: number | null;
    sugarReductionPct?: number | null;
    comparisonStatus?: string | null;
  };
  ingredients?: Array<{
    id: number;
    name: string;
    amount?: string | null;
    type?: string;
    sugarG?: number | null;
    kcal?: number | null;
  }>;
};

export type MyPageResponse = {
  enabledSns: string[];
  email?: string | null;
  optionalAgree: boolean;
  favorite?: string[] | null;
  healthStat?: {
    optionalAgree?: boolean;
    allergic?: boolean | null;
    tall?: number | null;
    weight?: number | null;
    age?: number | null;
  };
};

export type HealthProfileResponse = {
  birthYear?: number | null;
  gender?: string | null;
  heightCm?: number | null;
  weightKg?: number | null;
  activityLevel?: string | null;
  healthGoal?: string | null;
  dailyCalorieTarget?: number | null;
  dailySugarTargetG?: number | null;
  targetSource?: string | null;
  consent?: boolean;
};

export type ProductDetailResponse = {
  name?: string | null;
  brand?: string | null;
  category?: string | null;
  cal?: number | null;
  dang?: number | null;
  natu?: number | null;
  danb?: number | null;
  carb?: number | null;
  fat?: number | null;
  ingredi?: string | null;
  allerg?: string[] | null;
  imageUrl?: string | null;
  purchaseUrl?: string | null;
};

export type ProductSearchItem = {
  id: string;
  name: string;
  desc: string;
  url: string;
};

export type HomeProductItem = {
  rank?: number | null;
  name: string;
  brand?: string | null;
  image?: string | null;
  url?: string | null;
};

export type DietCalendarItem = {
  date: string;
  name: string;
  url: string;
};

export type DietAnalysisItem = {
  name: string;
  dang?: number | null;
  calo?: number | null;
  "ingred-list"?: Array<{ name: string; amount?: number | null }>;
};

export type DietAnalysisResponse = {
  status?: string;
  message?: string;
  id?: string;
  dang?: number | null;
  calo?: number | null;
  "list-diet"?: DietAnalysisItem[];
};

export type RecipeSubstituteResponse = {
  substitutes: Array<{
    ingredientId: number;
    ingredientName: string;
    products: Array<{
      productId: string;
      name: string;
      brand?: string | null;
      image?: string | null;
      url?: string | null;
      matchScore?: number | null;
      isPrimary?: boolean;
    }>;
  }>;
};

function query(path: string, values: Record<string, string | number | boolean | undefined | null>) {
  const params = new URLSearchParams();
  Object.entries(values).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") params.set(key, String(value));
  });
  return `${path}?${params.toString()}`;
}

export function getDailyGauge(token: string) {
  return apiRequest<GaugeResponse>(query("/home/user-sugar-calorie", { usr: token }));
}

export function getMyPage(token: string) {
  return apiRequest<MyPageResponse>(query("/user/mypage", { usr: token }));
}

export function deleteAccount(token: string) {
  return apiRequest<{ status: string }>(query("/user/mypage", { usr: token, exituser: "EXIT" }), { method: "DELETE" });
}

export function getHealthProfile(token: string) {
  return apiRequest<HealthProfileResponse>(query("/home/health-profile", { usr: token }));
}

export function updateFirstSet(token: string, payload: {
  favoriteCategory?: string[];
  isAllergic?: boolean;
  optionalAgree?: boolean;
  tall?: number;
  weight?: number;
  birthday?: string;
}) {
  return apiRequest<{ status: string }>("/user/firstset", {
    method: "POST",
    body: JSON.stringify({ usr: token, ...payload }),
  });
}

export function updateHealthProfile(token: string, payload: HealthProfileResponse) {
  return apiRequest<HealthProfileResponse & { status: string }>("/home/health-profile", {
    method: "PUT",
    body: JSON.stringify({
      usr: token,
      consent: payload.consent ?? false,
      birthYear: payload.birthYear,
      gender: payload.gender,
      heightCm: payload.heightCm,
      weightKg: payload.weightKg,
      activityLevel: payload.activityLevel,
      healthGoal: payload.healthGoal,
      dailyCalorieTarget: payload.dailyCalorieTarget,
      dailySugarTargetG: payload.dailySugarTargetG,
    }),
  });
}

export function getRecipes() {
  return apiRequest<{ recipes: RecipeListItem[] }>("/recipes");
}

export function getRecipeDetail(id: number) {
  return apiRequest<RecipeDetailResponse>(`/recipes/${id}`);
}

export function searchProducts(values: {
  query?: string;
  category?: string;
  warning?: string;
  sort?: string;
  page?: number;
}) {
  return apiRequest<{ items: ProductSearchItem[]; page: number }>(
    query("/search", { ...values, page: values.page ?? 1 }),
  );
}

export function getProductDetail(id: string) {
  return apiRequest<ProductDetailResponse>(query("/product", { id }));
}

export function getProductAiSummary(id: string) {
  return apiRequest<{ "ai-oneline"?: string }>(query("/product/ai", { id }));
}

export function getProductSweetenerInfo(id: string) {
  return apiRequest<{ "gammi-info"?: string }>(query("/product/gammi-info", { id }));
}

export function getProductUserFeatureInfo(id: string, token: string) {
  return apiRequest<{ "user-feature-info"?: string }>(query("/product/user-feature-info", { id, usr: token }));
}

export function getUserRecommendations(token: string) {
  return apiRequest<{ listProducts: HomeProductItem[] }>(query("/home/user-recommend", { usr: token }));
}

export function getProductRanking() {
  return apiRequest<{ status?: string; listProducts: HomeProductItem[] }>("/home/rank/item");
}

export function getDietCalendar(token: string, year: number, month: number) {
  return apiRequest<{ list: DietCalendarItem[] }>(query("/diet/calender", { usr: token, year, month }));
}

export function getDietOtherFoods(token: string, id: string) {
  return apiRequest<DietAnalysisResponse>(query("/diet/other-foods", { usr: token, id }));
}

export function getSearchRecommendations(searchQuery: string) {
  return apiRequest<{ items: Array<{ id: string; name: string }> }>(query("/search/recommend", { query: searchQuery }));
}

export function getRecipeSubstitutes(id: number) {
  return apiRequest<RecipeSubstituteResponse>(`/recipes/${id}/substitutes`);
}

export type ChatbotResponse = {
  status?: string;
  "cs-partner"?: string | null;
  time?: string | null;
  msg?: string | null;
  "is-img"?: boolean;
};

// MN-0111: 요청 키는 명세대로 msg/template, 응답은 cs-partner/time/msg/is-img.
export function sendChatbotMessage(msg: string, token?: string | null, template?: string) {
  return apiRequest<ChatbotResponse>("/ai/chatbot", {
    method: "POST",
    body: JSON.stringify({ msg, ...(token ? { usr: token } : {}), ...(template ? { template } : {}) }),
  });
}

export function unlinkSocialAccount(token: string, provider: string) {
  return apiRequest<{ status: string; enabledSns: string[] }>(
    query(`/user/social/${provider}`, { usr: token }),
    { method: "DELETE" },
  );
}

// RC-0101~0102: usr은 쿼리 파라미터, img/mode는 바디 (백엔드 get_current_user가 Query로 받음)
export function uploadDietPhoto(token: string, img: string, mode?: "daily", mealType?: "BREAKFAST" | "LUNCH" | "DINNER" | "SNACK") {
  return apiRequest<{ status: string; id?: string }>(query("/diet/upload", { usr: token }), {
    method: "POST",
    body: JSON.stringify({ img, ...(mode ? { mode } : {}), ...(mealType ? { mealType } : {}) }),
  });
}

// RC-0103: 명세는 img 입력이지만 실제 백엔드는 upload가 돌려준 meal_log id를 받는다
export function analyzeDietPhoto(token: string, id: string) {
  return apiRequest<DietAnalysisResponse>(query("/diet/ai-analyze", { usr: token, id }));
}
