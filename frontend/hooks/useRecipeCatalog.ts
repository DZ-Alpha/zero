"use client";

import { useCallback, useEffect, useState } from "react";
import type { RecipeData } from "@/data/catalog";
import { getRecipes, type RecipeDetailResponse, type RecipeListItem } from "@/lib/api/zerocheck";

function normalizeSteps(value: unknown) {
  if (!Array.isArray(value)) return [];
  return value.map((step, index) => {
    if (typeof step === "string") return { title: `${index + 1}단계`, description: step };
    if (typeof step === "object" && step) {
      const item = step as Record<string, unknown>;
      return {
        title: typeof item.title === "string" ? item.title : `${index + 1}단계`,
        description: typeof item.description === "string" ? item.description : typeof item.text === "string" ? item.text : "조리 순서를 확인해 주세요.",
      };
    }
    return { title: `${index + 1}단계`, description: String(step) };
  });
}

// service.recipes 테이블에 category 컬럼이 없어(데이터팀 스키마 추가 필요) 이름
// 키워드로 추정한다 - 카테고리가 너무 적어 대부분이 "한 끼"로 몰린다는 리포트
// (2026-07-31)에 맞춰 패턴을 세분화했다. 판정 순서가 중요 - 더 구체적인
// 카테고리를 먼저 검사해 애매한 단어(예: "볶음")가 "한 끼" 뒤로 밀리지 않게 한다.
function inferCategory(name: string): RecipeData["category"] {
  if (/소스|고추장|드레싱|잼|양념장|다시다|육수|시럽/.test(name)) return "소스";
  if (/면|국수|파스타|우동|라면|냉면|스파게티/.test(name)) return "면";
  if (/떡볶이|김밥|순대|튀김|호떡|핫도그|어묵/.test(name)) return "분식";
  if (/케이크|쿠키|아이스|디저트|간식|빵|머핀|타르트|마카롱|파이|초코|젤리/.test(name)) return "간식";
  if (/국|찌개|탕|전골|스프|수프|육개장|미역국/.test(name)) return "국·찌개";
  if (/샐러드|브런치|포케|리소토/.test(name)) return "샐러드";
  if (/무침|볶음|조림|나물|장아찌|김치|반찬/.test(name)) return "반찬";
  return "한 끼";
}

function recipeCategory(value: string | null | undefined, name: string): RecipeData["category"] {
  const allowed: RecipeData["category"][] = ["소스", "면", "분식", "간식", "국·찌개", "샐러드", "반찬", "한 끼"];
  return allowed.includes(value as RecipeData["category"])
    ? value as RecipeData["category"]
    : inferCategory(name);
}

function toRecipeData(item: RecipeListItem, detail: RecipeDetailResponse | null, fallback: RecipeData[]): RecipeData {
  const matched = fallback.find((recipe) => recipe.databaseId === String(item.id));
  const nutrition = detail?.nutrition;
  const ingredients = detail?.ingredients?.map((ingredient) => `${ingredient.name}${ingredient.amount ? ` ${ingredient.amount}` : ""}`) ?? [];
  const keywords = detail?.ingredients?.slice(0, 3).map((ingredient) => ingredient.name) ?? [];
  const sourceUrl = detail?.source?.startsWith("http") ? detail.source : matched?.sourceUrl ?? "";
  const tones = ["lime", "mint", "sand", "lavender"] as const;

  return {
    slug: String(item.id),
    databaseId: String(item.id),
    title: detail?.name || item.name || matched?.title || "레시피 이름 준비 중",
    author: detail?.source || matched?.author || "저당 레시피",
    category: item.category ? recipeCategory(item.category, item.name) : matched?.category ?? inferCategory(item.name),
    servings: matched?.servings ?? "분량 정보 준비 중",
    time: item.cookTimeMin != null ? `${item.cookTimeMin}분` : matched?.time ?? "조리 시간 준비 중",
    difficulty: matched?.difficulty ?? "차근차근",
    summary: matched?.summary ?? "재료와 조리 순서를 확인하고 식단에 가볍게 더해보세요.",
    ingredients: ingredients.length > 0 ? ingredients : matched?.ingredients ?? [],
    steps: detail?.steps ? normalizeSteps(detail.steps) : matched?.steps ?? [],
    sourceUrl,
    estimatedSugar: nutrition?.totalSugarG ?? item.sugar ?? matched?.estimatedSugar ?? 0,
    estimatedCalories: nutrition?.totalKcal ?? item.calories ?? matched?.estimatedCalories ?? 0,
    estimatedProtein: matched?.estimatedProtein ?? 0,
    comparisonSugar: nutrition?.baseSugarG ?? matched?.comparisonSugar ?? 0,
    comparisonCalories: nutrition?.baseKcal ?? matched?.comparisonCalories ?? 0,
    savedDemo: matched?.savedDemo ?? 0,
    tone: matched?.tone ?? tones[item.id % tones.length],
    keywords: keywords.length > 0 ? keywords : matched?.keywords ?? [],
    comparisonStatus: ["completed", "ready"].includes(nutrition?.comparisonStatus ?? item.comparisonStatus ?? "") ? "completed" : "pending",
    nutritionCoverage: detail?.nutrition || item.sugar != null || item.calories != null ? 100 : matched?.nutritionCoverage ?? 0,
    publishedAt: detail?.publishedAt || matched?.publishedAt,
    thumbnail: detail?.thumbnailUrl || item.thumbnailUrl || matched?.thumbnail,
  };
}

export function useRecipeCatalog(fallback: RecipeData[]) {
  const [items, setItems] = useState<RecipeData[]>([]);
  const [source, setSource] = useState<"mock" | "api">("mock");
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const [revision, setRevision] = useState(0);

  useEffect(() => {
    let active = true;
    setLoading(true);
    const timeout = new Promise<never>((_, reject) => {
      window.setTimeout(() => reject(new Error("RECIPE_CATALOG_MOCK_FALLBACK")), 3500);
    });
    Promise.race([getRecipes(1), timeout])
      .then(({ recipes, hasNext }) => {
        if (!active) return;
        // 목록 응답만으로 카드를 만들고 상세 정보는 상세 페이지에 들어갔을 때만 호출한다.
        // 전체 레시피마다 상세 API를 호출하면 DB 데이터가 늘수록 요청이 폭증한다.
        setItems(recipes.map((recipe) => toRecipeData(recipe, null, fallback)));
        setSource("api");
        setPage(1);
        setHasMore(hasNext);
      })
      .catch(() => {
        if (!active) return;
        setItems(fallback);
        setSource("mock");
        setHasMore(false);
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [fallback, revision]);

  const loadMore = useCallback(() => {
    if (source !== "api" || loadingMore || !hasMore) return;
    setLoadingMore(true);
    const nextPage = page + 1;
    getRecipes(nextPage)
      .then(({ recipes, hasNext }) => {
        setItems((current) => [...current, ...recipes.map((recipe) => toRecipeData(recipe, null, fallback))]);
        setPage(nextPage);
        setHasMore(hasNext);
      })
      .catch(() => setHasMore(false))
      .finally(() => setLoadingMore(false));
  }, [source, loadingMore, hasMore, page, fallback]);

  return {
    recipes: items,
    source,
    loading,
    loadingMore,
    hasMore,
    loadMore,
    retry: () => setRevision((current) => current + 1),
  };
}
