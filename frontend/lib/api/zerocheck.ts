import { ApiError, apiRequest } from "@/lib/api/client";

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
  // 2026-07-19, 백엔드 PRODUCTION_HANDOFF.md P1-1 반영분 — 카드 렌더링용 필드.
  brand?: string | null;
  category?: string | null;
  serving?: string | null;
  sugar?: number | null;
  calories?: number | null;
  image?: string | null;
  tags?: string[];
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

export type DietPhotoStatus = "PENDING" | "PROCESSING" | "AWAITING_CONFIRMATION" | "COMPLETED" | "FAILED";

export type DietPhotoStatusResponse = {
  meal_log_id: string;
  status: DietPhotoStatus;
  needs_user_confirmation: boolean;
  confidence?: number | null;
  confidence_source?: string | null;
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

export function getRecipes(page = 1) {
  // 백엔드가 페이지네이션을 도입한 뒤에도(page/pageSize/total/hasNext) 이 함수는
  // page 파라미터 없이 항상 1페이지(20건)만 불러왔다 - 전체 1700여 건 중 20건만
  // 보이고 나머지는 화면에 절대 안 나오던 원인 (무한스크롤은 이미 받아온 20건
  // 안에서만 더 보여주는 클라이언트 로직이라, 서버에 다음 페이지를 요청하지
  // 않았다). useRecipeCatalog가 hasNext를 보고 다음 page를 이 함수로 다시 부른다.
  return apiRequest<{ recipes: RecipeListItem[]; page: number; pageSize: number; total: number; hasNext: boolean }>(
    `/recipes?page=${page}`
  );
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
  // 2026-07-19, 백엔드 PRODUCTION_HANDOFF.md P1-1 반영분 — total/pageSize/hasNext 추가.
  return apiRequest<{ items: ProductSearchItem[]; page: number; total?: number; pageSize?: number; hasNext?: boolean }>(
    query("/search", { ...values, page: values.page ?? 1 }),
  );
}

function authHeader(token: string) {
  return { Authorization: `Bearer ${token}` };
}

// 2026-07-19, 백엔드 PRODUCTION_HANDOFF.md P0-4/P1-4 반영분(PR-0307/0308) — 상품 찜.
export function toggleProductFavorite(id: string, token: string) {
  return apiRequest<{ status: string; liked: boolean }>("/product/favorite", {
    method: "POST",
    headers: authHeader(token),
    body: JSON.stringify({ id }),
  });
}

export function getProductFavorites(token: string) {
  return apiRequest<{ "list-products": Array<{ id: string; name: string; brand?: string | null; image?: string | null }> }>(
    "/product/favorite/list",
    { headers: authHeader(token) },
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

// 2026-07-19, 백엔드 PRODUCTION_HANDOFF.md P0-2/P1-3 반영분(RC-0113~0117) — 식단
// 기록 CRUD. 캘린더 월 조회는 날짜별로 이미 묶여서 오기 때문에(day-grouped),
// 기존 getDietCalendar + 로그마다 getDietOtherFoods 호출하던 N+1이 필요 없다.
export type DietRecordApiItem = {
  recordId: string;
  mealType: "BREAKFAST" | "LUNCH" | "DINNER" | "SNACK" | "OTHER";
  itemType: "recipe" | "product" | "photo";
  itemId: string;
  name: string;
  sugar?: number | null;
  calories?: number | null;
};

export type DietRecordsDayGroup = {
  date: string;
  "sugar-total": number;
  "calories-total": number;
  list: DietRecordApiItem[];
};

export function getDietRecordsByMonth(token: string, year: number, month: number) {
  return apiRequest<{ list: DietRecordsDayGroup[] }>(query("/diet/records", { year, month }), {
    headers: authHeader(token),
  });
}

export function createDietRecord(token: string, values: {
  date: string;
  mealType: string;
  itemType: "recipe" | "product" | "photo";
  itemId: string;
  serving: number;
  sugar: number;
  calories: number;
}) {
  return apiRequest<{ status: string; id: string }>("/diet/records", {
    method: "POST",
    headers: authHeader(token),
    body: JSON.stringify(values),
  });
}

export function deleteDietRecord(token: string, id: string) {
  return apiRequest<{ status: string }>(`/diet/records/${id}`, {
    method: "DELETE",
    headers: authHeader(token),
  });
}

export function getSearchRecommendations(searchQuery: string) {
  return apiRequest<{ items: Array<{ id: string; name: string }> }>(query("/search/recommend", { query: searchQuery }));
}

export function getRecipeSubstitutes(id: number) {
  return apiRequest<RecipeSubstituteResponse>(`/recipes/${id}/substitutes`);
}

// 2026-07-19, 백엔드 PRODUCTION_HANDOFF.md P0-4/P1-4 반영분(RC-0111/0112) — 레시피 찜.
// recipe-service는 이 두 엔드포인트가 Authorization: Bearer 헤더만 받는다(usr 쿼리 불가).
export function toggleRecipeFavorite(id: number, token: string) {
  return apiRequest<{ status: string; liked: boolean }>("/recipes/favorite", {
    method: "POST",
    headers: authHeader(token),
    body: JSON.stringify({ id }),
  });
}

export function getRecipeFavorites(token: string) {
  return apiRequest<{ "list-receipe": Array<{ id: number; name: string; image?: string | null }> }>(
    "/recipes/favorite/list",
    { headers: authHeader(token) },
  );
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

// gateway -> diet-service가 MinIO diet-photos에 저장하고 object_key만 돌려준다.
// 브라우저는 MinIO를 직접 보지 않는다. multipart라 apiRequest(항상 JSON
// Content-Type을 붙임)를 쓰지 않고 직접 fetch한다.
export async function uploadDietPhotoFile(token: string, file: File) {
  const form = new FormData();
  form.append("file", file);
  const response = await fetch("/b/uploads/diet-photo", {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: form,
  });
  const contentType = response.headers.get("content-type") ?? "";
  const payload = contentType.includes("application/json") ? await response.json() : await response.text();
  if (!response.ok) {
    const detail = typeof payload === "object" && payload && "detail" in payload
      ? String((payload as { detail: unknown }).detail)
      : "사진 업로드에 실패했어요.";
    throw new ApiError(detail, response.status, payload);
  }
  return payload as { object_key: string };
}

// RC-0101~0102: object_key(uploadDietPhotoFile 결과) 등록 -> meal_log(PENDING)
// 생성. 202를 받으면 분석은 아직 끝난 게 아니다 - getDietPhotoStatus로 폴링한다.
export function uploadDietPhoto(token: string, objectKey: string, mealType?: "BREAKFAST" | "LUNCH" | "DINNER" | "SNACK", eatenAt?: string) {
  return apiRequest<{ meal_log_id: string; status: string }>("/diet/upload", {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: JSON.stringify({ object_key: objectKey, ...(mealType ? { mealType } : {}), ...(eatenAt ? { eatenAt } : {}) }),
  });
}

export function getDietPhotoStatus(token: string, mealLogId: string) {
  return apiRequest<DietPhotoStatusResponse>(`/diet/photo/${mealLogId}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
}

export function confirmDietPhoto(
  token: string,
  mealLogId: string,
  items: Array<{ name: string; sugar: number; calories: number; carbohydrate?: number }>,
) {
  return apiRequest<{ status: string; meal_log_id: string; analysisStatus: string }>(
    `/diet/ai-analyze/${mealLogId}/confirm`,
    {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: JSON.stringify({ items }),
    },
  );
}

// RC-0103: 옛 1회성 스텁 - 새 폴링 플로우에서는 getDietPhotoStatus를 쓴다.
// 다른 곳에서 여전히 참조할 수 있어 남겨둔다.
export function analyzeDietPhoto(token: string, id: string) {
  return apiRequest<DietAnalysisResponse>(query("/diet/ai-analyze", { usr: token, id }));
}
