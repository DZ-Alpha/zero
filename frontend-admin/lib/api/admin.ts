import { adminApiRequest } from "@/lib/api/client";

export type AdminIdentity = {
  userId: number;
  loginId: string;
};

// US-0102 / backend/login-service/app/routers/admin_auth.py:POST /administrator-login
export async function adminLogin(id: string, pw: string, captcha: string) {
  return adminApiRequest<{ status: string; token: string }>("/administrator-login", {
    method: "POST",
    body: JSON.stringify({ id, pw, captcha }),
  });
}

// backend/admin-service/app/routers/admin.py:GET /admin/me
export async function getAdminMe(token?: string) {
  return adminApiRequest<AdminIdentity>("/admin/me", {}, token);
}

// AD-0101/0102 — backend/product-service/app/routers/admin.py:POST /admin (menu=manage-item)
export type ProductUpsertInput = {
  id?: string;
  name?: string;
  brand?: string;
  categoryTagId?: string;
  ingredientText?: string;
  imageUrl?: string;
  purchaseUrl?: string;
  reportNo?: string;
  manufacturerName?: string;
  foodType?: string;
  servingValue?: string;
  servingUnit?: string;
  calories?: string;
  sugars?: string;
};

// Istio 전환 요청서 §1(2026-07-30) - menu 값으로 프록시가 서비스를 고르던
// POST /admin 대신 기능별 URL을 쓴다. 경로만으로 소유 서비스가 정해진다:
// /admin/products/* → product-service, /admin/tags/* → ingredients-service.
export async function upsertProduct(input: ProductUpsertInput) {
  const body: Record<string, unknown> = {
    name: input.name,
    brand: input.brand,
    category_tag_id: input.categoryTagId,
    ingredient_text: input.ingredientText,
    image_url: input.imageUrl,
    purchase_url: input.purchaseUrl,
    report_no: input.reportNo,
    manufacturer_name: input.manufacturerName,
    food_type: input.foodType,
    serving_value: input.servingValue,
    serving_unit: input.servingUnit,
    calories: input.calories,
    sugars: input.sugars,
  };
  if (input.id) {
    return adminApiRequest<{ status: string; id?: string }>(`/admin/products/${encodeURIComponent(input.id)}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    });
  }
  return adminApiRequest<{ status: string; id?: string }>("/admin/products", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

// AD-0103 — POST /admin/products/{id}/nutrients
export type NutritionInput = {
  id: string;
  cal?: string;
  natu?: string;
  dang?: string;
  dan?: string;
  carb?: string;
  fat?: string;
};

export async function upsertNutrition(input: NutritionInput) {
  const { id, ...nutrients } = input;
  return adminApiRequest<{ status: string; id: string }>(`/admin/products/${encodeURIComponent(id)}/nutrients`, {
    method: "POST",
    body: JSON.stringify(nutrients),
  });
}

// AD-0104 — POST /admin/products/{id}/ingredients
export type IngredientsInput = {
  id: string;
  ingredientText?: string;
  allergenTagIds: string[];
};

export async function upsertIngredients(input: IngredientsInput) {
  return adminApiRequest<{ status: string; id: string }>(`/admin/products/${encodeURIComponent(input.id)}/ingredients`, {
    method: "POST",
    body: JSON.stringify({
      ingredient_text: input.ingredientText,
      allergen_tag_ids: input.allergenTagIds,
    }),
  });
}

// 원재료 등록에서 실제로 태그(알레르기 등)를 고르려면 태그 마스터 관리가
// 먼저 필요하다 — backend/ingredients-service/app/routers/admin.py의
// POST /admin/tags. (예전엔 POST /admin 하나를 menu 값으로 나눠 썼는데,
// Istio 전환 요청서 §1로 경로 기반 분리 - 프록시가 body를 읽을 필요가 없어졌다.)
export type TagInput = {
  tagType: "CATEGORY" | "ALLERGEN" | "SWEETENER" | "HEALTH_LABEL";
  tagCode: string;
  tagName: string;
  description?: string;
  cautionText?: string;
  sourceUrl?: string;
};

export async function createTag(input: TagInput) {
  return adminApiRequest<{ status: string; id: string }>("/admin/tags", {
    method: "POST",
    body: JSON.stringify({
      tag_type: input.tagType,
      tag_code: input.tagCode,
      tag_name: input.tagName,
      description: input.description,
      caution_text: input.cautionText,
      source_url: input.sourceUrl,
    }),
  });
}
