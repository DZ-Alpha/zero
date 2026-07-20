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

function inferCategory(name: string): RecipeData["category"] {
  if (/소스|고추장|드레싱|잼/.test(name)) return "소스";
  if (/면|국수|파스타/.test(name)) return "면";
  if (/떡볶이|김밥/.test(name)) return "분식";
  if (/케이크|쿠키|아이스|디저트|간식/.test(name)) return "간식";
  if (/무침|볶음|조림|반찬/.test(name)) return "반찬";
  return "한 끼";
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
    category: matched?.category ?? inferCategory(item.name),
    servings: matched?.servings ?? "분량 정보 준비 중",
    time: matched?.time ?? "조리 시간 준비 중",
    difficulty: matched?.difficulty ?? "차근차근",
    summary: matched?.summary ?? "재료와 조리 순서를 확인하고 식단에 가볍게 더해보세요.",
    ingredients: ingredients.length > 0 ? ingredients : matched?.ingredients ?? [],
    steps: detail?.steps ? normalizeSteps(detail.steps) : matched?.steps ?? [],
    sourceUrl,
    estimatedSugar: nutrition?.totalSugarG ?? matched?.estimatedSugar ?? 0,
    estimatedCalories: nutrition?.totalKcal ?? matched?.estimatedCalories ?? 0,
    estimatedProtein: matched?.estimatedProtein ?? 0,
    comparisonSugar: nutrition?.baseSugarG ?? matched?.comparisonSugar ?? 0,
    comparisonCalories: nutrition?.baseKcal ?? matched?.comparisonCalories ?? 0,
    savedDemo: matched?.savedDemo ?? 0,
    tone: matched?.tone ?? tones[item.id % tones.length],
    keywords: keywords.length > 0 ? keywords : matched?.keywords ?? [],
    comparisonStatus: nutrition?.comparisonStatus === "completed" || item.comparisonStatus === "completed" ? "completed" : "pending",
    nutritionCoverage: detail?.nutrition ? 100 : matched?.nutritionCoverage ?? 0,
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
    getRecipes(1)
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
