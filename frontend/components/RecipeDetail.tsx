"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { FavoriteButton } from "@/components/FavoriteButton";
import { RecipeCover } from "@/components/RecipeCover";
import { SafeImage } from "@/components/SafeImage";
import { portionPrefix, productBySlug, recipeBySlug, recipes, type RecipeData } from "@/data/catalog";
import { RECIPE_CATEGORIES } from "@/data/taxonomy";
import { useAuthSession } from "@/hooks/useAuthSession";
import { useUserSettings } from "@/hooks/useUserSettings";
import { getRecipeDetail, getRecipeSubstitutes, getRelatedRecipes, RecipeDetailResponse, RecipeListItem, RecipeSubstituteResponse } from "@/lib/api/zerocheck";

function normalizeSteps(value: unknown, fallback: { title: string; description: string }[]) {
  if (!Array.isArray(value) || value.length === 0) return fallback;
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

export function RecipeDetail({ slug = "perilla-low-sugar-jeyuk" }: { slug?: string }) {
  const { token } = useAuthSession();
  const { profile } = useUserSettings();
  const catalogDetail = recipeBySlug[slug] ?? recipes.find((recipe) => recipe.databaseId === slug) ?? null;
  const parsedId = Number(catalogDetail?.databaseId ?? slug);
  const recipeId = Number.isFinite(parsedId) ? parsedId : null;
  const fallbackDetail = useMemo<RecipeData>(() => catalogDetail ?? ({
    slug,
    databaseId: recipeId === null ? undefined : String(recipeId),
    title: "레시피를 불러오고 있어요",
    author: "저당 레시피",
    category: "한 끼",
    servings: "전체 분량 기준",
    // 여기는 카탈로그에 없는 레시피(= DB 수집분)만 오는 자리라 전체 분량 합계다.
    // 카탈로그에 있으면 위 catalogDetail 쪽으로 빠지고 거기엔 기준이 이미 들어있다.
    portionBasis: "total",
    time: "",
    difficulty: "차근차근",
    summary: "재료와 조리 순서를 확인하고 있어요.",
    ingredients: [],
    steps: [],
    sourceUrl: "",
    estimatedSugar: 0,
    estimatedCalories: 0,
    estimatedProtein: 0,
    comparisonSugar: 0,
    comparisonCalories: 0,
    savedDemo: 0,
    tone: "lime",
    keywords: [],
    comparisonStatus: "pending",
    nutritionCoverage: 0,
  }), [catalogDetail, recipeId, slug]);
  const [live, setLive] = useState<RecipeDetailResponse | null>(null);
  const [liveSubstitutes, setLiveSubstitutes] = useState<RecipeSubstituteResponse | null>(null);
  const [relatedLive, setRelatedLive] = useState<RecipeListItem[]>([]);
  const [loading, setLoading] = useState(recipeId !== null);
  const [unavailable, setUnavailable] = useState(!catalogDetail && recipeId === null);
  useEffect(() => {
    setLive(null);
    setLiveSubstitutes(null);
    setRelatedLive([]);
    if (recipeId === null) {
      setLoading(false);
      setUnavailable(!catalogDetail);
      return;
    }
    let active = true;
    setLoading(true);
    setUnavailable(false);
    getRecipeDetail(recipeId).then((value) => {
      if (active) setLive(value);
    }).catch(() => {
      if (active) setUnavailable(!catalogDetail);
    }).finally(() => {
      if (active) setLoading(false);
    });
    getRecipeSubstitutes(recipeId).then((value) => {
      if (active) setLiveSubstitutes(value);
    }).catch(() => undefined);
    getRelatedRecipes(recipeId).then((value) => {
      if (active) setRelatedLive(value.recipes);
    }).catch(() => undefined);
    return () => {
      active = false;
    };
  }, [catalogDetail, recipeId]);

  const detail = useMemo(() => {
    if (!live) return fallbackDetail;
    const nutrition = live.nutrition;
    return {
      ...fallbackDetail,
      title: live.name || fallbackDetail.title,
      author: live.source || fallbackDetail.author,
      // DB category(2026-08-16 백필)를 여기서 안 받아서, 카탈로그에 없는 레시피는
      // fallbackDetail 의 하드코딩 "한 끼" 가 그대로 보였다. 허용 목록에 없는 값
      // (미판정 NULL 등)이면 폴백을 쓴다.
      category: RECIPE_CATEGORIES.includes(live.category as RecipeData["category"])
        ? live.category as RecipeData["category"]
        : fallbackDetail.category,
      thumbnail: live.thumbnailUrl || fallbackDetail.thumbnail,
      videoId: live.videoId ?? fallbackDetail.videoId,
      publishedAt: live.publishedAt || fallbackDetail.publishedAt,
      estimatedSugar: nutrition?.totalSugarG ?? fallbackDetail.estimatedSugar,
      estimatedCalories: nutrition?.totalKcal ?? fallbackDetail.estimatedCalories,
      comparisonSugar: nutrition?.baseSugarG ?? fallbackDetail.comparisonSugar,
      comparisonCalories: nutrition?.baseKcal ?? fallbackDetail.comparisonCalories,
      // 백엔드/DB는 "ready"를 쓴다 — "completed"로 비교하고 있어서 재료 합산이
      // 끝난 레시피도 항상 "준비 중" 패널만 떴다. RecipeData 내부 표현은 그대로
      // "completed" 리터럴을 쓰되(catalog.ts 타입과 맞춤), API 값 체크만 고친다.
      comparisonStatus: nutrition?.comparisonStatus === "ready" ? "completed" as const : fallbackDetail.comparisonStatus,
      // useRecipeCatalog.ts와 같은 규칙: API가 nutrition을 내려주면(재료 합산 완료)
      // 100%로 본다 — 여기서 한 번도 안 채워져서 fallback의 0이 항상 남아있었다.
      nutritionCoverage: nutrition ? 100 : fallbackDetail.nutritionCoverage,
      ingredients: live.ingredients?.length
        ? live.ingredients.map((item) => `${item.name}${item.amount ? ` ${item.amount}` : ""}`)
        : fallbackDetail.ingredients,
      steps: normalizeSteps(live.steps, fallbackDetail.steps),
    };
  }, [fallbackDetail, live]);
  const relatedProducts = useMemo(() => {
    // liveSubstitutes는 이 레시피 재료에 실제로 매칭된 상품(DB pgvector 매칭 결과)이라
    // 정적 카탈로그(products)에 없는 상품도 많다 — backendId로 카탈로그를 역참조하면
    // 대부분 매칭에 실패해서 늘 하드코딩 3개만 뜨는 버그가 있었다. API가 이미 카드에
    // 필요한 필드(image/sugar/calories)를 다 주므로 카탈로그 조회 없이 바로 쓰고,
    // 매칭이 진짜 없으면(재료 자체에 대체 상품이 없는 레시피) 빈 상태를 그대로 보여준다
    // — 무관한 고정 상품 3개를 계속 채워 넣는 게 오히려 혼란을 줬다.
    const liveProducts = (liveSubstitutes?.substitutes ?? [])
      .flatMap((group) => group.products)
      .filter((item, index, list) => list.findIndex((other) => other.productId === item.productId) === index)
      .map((item) => ({
        id: item.productId,
        title: item.name,
        image: item.image ?? "",
        serving: "100g",
        sugar: item.sugar ?? 0,
        calories: item.calories ?? 0,
      }))
      .slice(0, 3);
    if (liveProducts.length > 0) return liveProducts;
    if (process.env.NEXT_PUBLIC_MOCK_MODE !== "1" || live || detail.slug !== "perilla-low-sugar-jeyuk") return [];
    const product = productBySlug["nuts-green-low-sugar-gochujang"];
    return product ? [{ id: product.backendId ?? product.slug, title: product.title, image: product.image, serving: product.serving, sugar: product.sugar, calories: product.calories }] : [];
  }, [detail.slug, live, liveSubstitutes]);
  const substitutesLoaded = liveSubstitutes !== null;
  const similar = useMemo(() => {
    if (relatedLive.length > 0) {
      return relatedLive.map((item) => {
        // 연관 레시피도 API 유래라 목록 카드와 같은 규칙으로 각자 기준을 정한다 —
        // fallbackDetail을 펼치는 김에 지금 보고 있는 레시피의 기준까지 물려받으면
        // 1인분짜리 상세에서 전체 분량 레시피가 "총" 없이 나온다.
        const matched = recipes.find((recipe) => recipe.databaseId === String(item.id));
        return {
          ...fallbackDetail,
          slug: String(item.id),
          databaseId: String(item.id),
          title: item.name,
          category: (item.category as RecipeData["category"]) || detail.category,
          time: item.cookTimeMin != null ? `${item.cookTimeMin}분` : "",
          thumbnail: item.thumbnailUrl ?? undefined,
          estimatedSugar: item.sugar ?? 0,
          estimatedCalories: item.calories ?? 0,
          portionBasis: matched?.portionBasis ?? "total",
          comparisonStatus: "completed" as const,
        };
      });
    }
    return recipes.filter((recipe) => recipe.slug !== detail.slug && recipe.category === detail.category).slice(0, 3);
  }, [detail.category, detail.slug, fallbackDetail, relatedLive]);
  const changedIngredients = (live?.ingredients ?? []).filter((ingredient) =>
    ingredient.baseSugarG != null && ingredient.sugarG != null && ingredient.baseSugarG > ingredient.sugarG,
  );
  const mockComparison = process.env.NEXT_PUBLIC_MOCK_MODE === "1" && !live && detail.slug === "perilla-low-sugar-jeyuk";
  const comparisonRows = (liveSubstitutes?.substitutes ?? []).filter((group) => group.products.length > 0).slice(0, 3).map((group) => {
    const ingredient = live?.ingredients?.find((item) => item.id === group.ingredientId);
    const product = group.products[0];
    return { key: group.ingredientId, ingredientName: group.ingredientName, baseSugar: ingredient?.baseSugarG ?? null, productName: product.name, sugar: ingredient?.sugarG ?? product.sugar ?? 0, image: product.image ?? "" };
  });
  if (mockComparison && comparisonRows.length === 0) {
    const product = productBySlug["nuts-green-low-sugar-gochujang"];
    comparisonRows.push({ key: -1, ingredientName: "볶음고추장", baseSugar: 9.5, productName: "넛츠그린 저당 고추장", sugar: 3, image: product?.image ?? "" });
  }
  const comparisonReady = mockComparison || (detail.comparisonStatus === "completed"
    && detail.comparisonSugar - detail.estimatedSugar >= 0.1
    && (changedIngredients.length > 0 || (liveSubstitutes?.substitutes.some((group) => group.products.length > 0) ?? false)));
  const matchedAllergens = (profile.allergens ?? []).filter((allergen) =>
    detail.ingredients.some((ingredient) =>
      ingredient.replace(/\s/g, "").includes(allergen.replace(/\s/g, "")),
    ),
  );

  if (loading && !catalogDetail) {
    return <main className="detail-page page-wrap"><div className="detail-state wrap"><div className="catalog-loading"><i /><i /><i /><span>레시피를 불러오고 있어요.</span></div></div></main>;
  }

  if (unavailable && !catalogDetail) {
    return <main className="detail-page page-wrap"><div className="detail-state wrap"><h1>레시피를 찾을 수 없어요.</h1><p>목록으로 돌아가 다른 메뉴를 확인해보세요.</p><Link href="/recipes">레시피 목록 보기</Link></div></main>;
  }

  return (
    <main className="detail-page page-wrap">
      <section className="detail-hero wrap">
        <div className="detail-hero-image"><RecipeCover recipe={detail} hero /></div>
        <div className="detail-hero-copy">
          <p className="eyebrow">{[detail.category, detail.servings, detail.time, detail.difficulty].filter(Boolean).join(" · ")}</p>
          <h1>{detail.title}</h1>
          <p>{detail.summary}</p>
          {/* DB 수집 레시피는 전체 분량 합계라 "총"을 붙인다(data/catalog.ts portionBasis). */}
          <div className="detail-metrics"><div><span>{portionPrefix(detail)}당류</span><strong>{detail.estimatedSugar}g</strong></div><div><span>{portionPrefix(detail)}열량</span><strong>{detail.estimatedCalories}kcal</strong></div></div>
          <FavoriteButton label={detail.title} id={recipeId} kind="recipe" checkInitial />
          {detail.sourceUrl && <a className="source-link" href={detail.sourceUrl} target="_blank" rel="noreferrer">원본 레시피 보기 ↗</a>}
        </div>
      </section>

      {token && matchedAllergens.length > 0 && (
        <section className="allergen-user-warning wrap" role="alert">
          <div><strong>내 주의 성분이 재료에 포함될 수 있어요</strong><span>{matchedAllergens.join(", ")}</span></div>
          <p>재료명 기반 참고 정보이며 의료 판단을 대신하지 않아요. 조리 전 실제 제품 포장과 원재료 표시를 반드시 확인해 주세요.</p>
        </section>
      )}

      {comparisonReady && <section className="recipe-compare wrap">
          <header className="section-line-heading"><div><p className="eyebrow">일반 조리와 비교</p><h2>바꾼 재료가 수치에 어떻게 보이는지 확인해요</h2></div></header>
          <div className="recipe-compare-layout">
            <div className="compare-bars">
              <div><span>일반 조리</span><i><b style={{ width: "100%" }} /></i><strong>당류 {detail.comparisonSugar}g · {detail.comparisonCalories}kcal</strong></div>
              <div className="better"><span>이 레시피</span><i><b style={{ width: `${Math.max(4, Math.round((detail.estimatedSugar / detail.comparisonSugar) * 100))}%` }} /></i><strong>당류 {detail.estimatedSugar}g · {detail.estimatedCalories}kcal</strong></div>
            </div>
            <div className="recipe-swap-code" aria-label="당류를 줄인 재료 선택">
              {comparisonRows.map((row) => <article key={row.key}>
                <div className="recipe-swap-photo"><SafeImage src={row.image} alt={`${row.productName} 제품`} fallbackLabel="제품" /></div>
                <div><small>바꿔 담은 재료</small><strong>{row.ingredientName}</strong><p><span>일반 {row.baseSugar ?? "-"}g</span><i aria-hidden="true">→</i><b>{row.productName}</b><em>{row.sugar}g</em></p></div>
              </article>)}
            </div>
          </div>
        </section>}

      <section className="recipe-body wrap">
        <aside><p className="eyebrow">재료 · {detail.servings}</p>{detail.ingredients.map((item) => <div key={item}><span>{item}</span><i>✓</i></div>)}</aside>
        <div className="recipe-steps"><p className="eyebrow">간단히 보는 조리 순서</p>{detail.steps.map((step, index) => <article key={`${index}-${step.title}`}><span>{String(index + 1).padStart(2, "0")}</span><div><p>{step.description}</p></div></article>)}</div>
      </section>

      <section className="detail-products-band">
        <div className="used-products wrap">
          <header className="section-line-heading"><div><p className="eyebrow">이 요리에 활용할 수 있는 제품</p><h2>재료를 바꿀 때 함께 살펴보세요</h2></div><Link href="/search">저당 제품 전체 보기 →</Link></header>
          {relatedProducts.length > 0 && <div className="compact-recommendations">{relatedProducts.map((product) => <Link href={`/product/${product.id}`} key={product.id}><div className="compact-product-photo"><SafeImage src={product.image} alt={`${product.title} 제품`} /></div><h3>{product.title}</h3><p>{product.serving} 기준 당류 {product.sugar}g · {product.calories}kcal</p><b>♥</b></Link>)}</div>}
          {substitutesLoaded && relatedProducts.length === 0 && <p className="used-products-empty">아직 매칭된 상품이 없어요.</p>}
        </div>
      </section>

      <section className="similar-section wrap">
        <header className="section-line-heading"><div><p className="eyebrow">비슷한 저당 레시피</p><h2>다음 메뉴도 이어서 살펴보세요</h2></div></header>
        <div className="similar-grid">{similar.map((recipe) => <Link href={`/recipes/${recipe.databaseId ?? recipe.slug}`} key={recipe.databaseId ?? recipe.slug}><RecipeCover recipe={recipe} /><small>{recipe.category}</small><h3>{recipe.title}</h3><p>{portionPrefix(recipe)}당류 {recipe.estimatedSugar}g · {portionPrefix(recipe)}{recipe.estimatedCalories}kcal</p></Link>)}</div>
      </section>
    </main>
  );
}
