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

export async function upsertProduct(input: ProductUpsertInput) {
  const body: Record<string, unknown> = {
    menu: "manage-item",
    id: input.id,
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
  return adminApiRequest<{ status: string; id?: string }>("/admin", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

// AD-0103 — POST /admin (menu=manage-nutrients)
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
  return adminApiRequest<{ status: string; id: string }>("/admin", {
    method: "POST",
    body: JSON.stringify({ menu: "manage-nutrients", ...input }),
  });
}

// AD-0104 — POST /admin (menu=manage-ingredients)
export type IngredientsInput = {
  id: string;
  ingredientText?: string;
  allergenTagIds: string[];
};

export async function upsertIngredients(input: IngredientsInput) {
  return adminApiRequest<{ status: string; id: string }>("/admin", {
    method: "POST",
    body: JSON.stringify({
      menu: "manage-ingredients",
      id: input.id,
      ingredient_text: input.ingredientText,
      allergen_tag_ids: input.allergenTagIds,
    }),
  });
}

// 원재료 등록에서 실제로 태그(알레르기 등)를 고르려면 태그 마스터 관리가
// 먼저 필요하다 — backend/ingredients-service/app/routers/admin.py, 같은
// /b/admin 경로를 menu(create-tag/update-tag/deactivate-tag)로 공유한다
// (nginx.conf의 Lua 라우팅이 menu 값으로 product-service/ingredients-service를
// 나눠 보낸다 — 프론트는 항상 /admin 하나만 호출하면 된다).
export type TagInput = {
  tagType: "CATEGORY" | "ALLERGEN" | "SWEETENER" | "HEALTH_LABEL";
  tagCode: string;
  tagName: string;
  description?: string;
  cautionText?: string;
  sourceUrl?: string;
};

export async function createTag(input: TagInput) {
  return adminApiRequest<{ status: string; id: string }>("/admin", {
    method: "POST",
    body: JSON.stringify({
      menu: "create-tag",
      tag_type: input.tagType,
      tag_code: input.tagCode,
      tag_name: input.tagName,
      description: input.description,
      caution_text: input.cautionText,
      source_url: input.sourceUrl,
    }),
  });
}
