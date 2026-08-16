"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { RecipeData } from "@/data/catalog";
import { RECIPE_CATEGORIES } from "@/data/taxonomy";
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

// service.recipes.category 는 2026-08-16 백필로 채워졌다(1,677건). 그래서 이 함수는
// 이제 폴백이다 - 미판정으로 NULL 인 32건과 목업 모드에서만 돈다.
//
// 판정 순서가 중요하다. "그 자체로 먹지 않는 것"과 "마시는 것"을 먼저 걸러야
// `저당고추장`이 한 끼로, `바나나우유라떼`가 간식으로 새지 않는다.
// 반대로 `굴소스 제육볶음`처럼 요리가 주인 이름은 소스로 가면 안 되므로,
// 양념류는 이름 끝에 올 때만 인정한다(자세한 기준은 docs 의 카테고리 정의 참고).
function inferCategory(name: string): RecipeData["category"] {
  if (/(?:소스|고추장|쌈장|드레싱|잼|양념장|시럽|마요네즈|앙금|연유|청)$/.test(name)) return "양념·소스";
  if (/라떼|스무디|셰이크|쉐이크|에이드|레모네이드|주스|쥬스|식혜|스무디|(?:커피|차)$/.test(name)) return "음료";
  if (/케이크|케익|쿠키|과자|도넛|빵|머핀|타르트|마카롱|초코|초콜릿|젤리|찰떡|떡|스콘|아이스|디저트|간식|그래놀라/.test(name)) return "간식";
  return "한 끼";
}

function recipeCategory(value: string | null | undefined, name: string): RecipeData["category"] {
  return RECIPE_CATEGORIES.includes(value as RecipeData["category"])
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
    // DB 수집 레시피는 인분 정보가 없다(service.recipes 에 컬럼 자체가 없고,
    // 원본 영상에도 2% 미만만 적혀 있다). "준비 중"은 곧 채워질 것처럼 읽히는데
    // 실제로는 채울 수 없는 값이라, 수치가 무엇을 뜻하는지를 밝히는 쪽으로 바꿨다.
    servings: matched?.servings ?? "전체 분량 기준",
    // 카탈로그 매칭이 있으면 거기서 이미 정해진 기준을 그대로 쓰고(catalog.ts의
    // withPortionBasis), 매칭이 없으면 total_kcal 그대로라 전체 분량 합계다.
    // 화면 접두("총 ")가 이 값으로 갈린다.
    portionBasis: matched?.portionBasis ?? "total",
    time: item.cookTimeMin != null ? `${item.cookTimeMin}분` : matched?.time === "조리 시간 준비 중" ? "" : matched?.time ?? "",
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

export function useRecipeCatalog(fallback: RecipeData[], values: { search?: string; sort?: string; eligible?: boolean } = {}) {
  const fallbackRef = useRef(fallback);
  fallbackRef.current = fallback;
  const [items, setItems] = useState<RecipeData[]>([]);
  const [source, setSource] = useState<"mock" | "api">("mock");
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const [total, setTotal] = useState(0);
  const [revision, setRevision] = useState(0);

  useEffect(() => {
    let active = true;
    setLoading(true);
    const fallbackTimer = window.setTimeout(() => {
      if (!active) return;
      setItems(fallbackRef.current);
      setTotal(fallbackRef.current.length);
      setSource("mock");
      setHasMore(false);
      setLoading(false);
    }, 3500);
    getRecipes(1, values.search, values.sort, values.eligible)
      .then(({ recipes, hasNext, total: nextTotal }) => {
        if (!active) return;
        window.clearTimeout(fallbackTimer);
        // 목록 응답만으로 카드를 만들고 상세 정보는 상세 페이지에 들어갔을 때만 호출한다.
        // 전체 레시피마다 상세 API를 호출하면 DB 데이터가 늘수록 요청이 폭증한다.
        setItems(recipes.map((recipe) => toRecipeData(recipe, null, fallbackRef.current)));
        setSource("api");
        setPage(1);
        setHasMore(hasNext);
        setTotal(nextTotal);
      })
      .catch(() => {
        if (!active) return;
        window.clearTimeout(fallbackTimer);
        setItems(fallbackRef.current);
        setTotal(fallbackRef.current.length);
        setSource("mock");
        setHasMore(false);
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
      window.clearTimeout(fallbackTimer);
    };
  }, [revision, values.search, values.sort, values.eligible]);

  const loadMore = useCallback(() => {
    if (source !== "api" || loadingMore || !hasMore) return;
    setLoadingMore(true);
    const nextPage = page + 1;
    getRecipes(nextPage, values.search, values.sort, values.eligible)
      .then(({ recipes, hasNext, total: nextTotal }) => {
        setItems((current) => [...current, ...recipes.map((recipe) => toRecipeData(recipe, null, fallbackRef.current))]);
        setPage(nextPage);
        setHasMore(hasNext);
        setTotal(nextTotal);
      })
      .catch(() => setHasMore(false))
      .finally(() => setLoadingMore(false));
  }, [source, loadingMore, hasMore, page, values.search, values.sort, values.eligible]);

  return {
    recipes: items,
    source,
    loading,
    loadingMore,
    hasMore,
    total,
    loadMore,
    retry: () => setRevision((current) => current + 1),
  };
}
