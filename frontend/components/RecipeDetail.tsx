"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { FavoriteButton } from "@/components/FavoriteButton";
import { RecipeCover } from "@/components/RecipeCover";
import { SafeImage } from "@/components/SafeImage";
import { recipeBySlug, recipes, type RecipeData } from "@/data/catalog";
import { getRecipeDetail, getRecipeSubstitutes, RecipeDetailResponse, RecipeSubstituteResponse } from "@/lib/api/zerocheck";

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
  const catalogDetail = recipeBySlug[slug] ?? recipes.find((recipe) => recipe.databaseId === slug) ?? null;
  const parsedId = Number(catalogDetail?.databaseId ?? slug);
  const recipeId = Number.isFinite(parsedId) ? parsedId : null;
  const fallbackDetail = useMemo<RecipeData>(() => catalogDetail ?? ({
    slug,
    databaseId: recipeId === null ? undefined : String(recipeId),
    title: "레시피를 불러오고 있어요",
    author: "저당 레시피",
    category: "한 끼",
    servings: "분량 정보 준비 중",
    time: "조리 시간 준비 중",
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
  const [loading, setLoading] = useState(recipeId !== null);
  const [unavailable, setUnavailable] = useState(!catalogDetail && recipeId === null);
  useEffect(() => {
    setLive(null);
    setLiveSubstitutes(null);
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
      thumbnail: live.thumbnailUrl || fallbackDetail.thumbnail,
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
    return (liveSubstitutes?.substitutes ?? [])
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
  }, [liveSubstitutes]);
  const substitutesLoaded = liveSubstitutes !== null;
  const similar = recipes.filter((recipe) => recipe.slug !== detail.slug).slice(0, 3);
  const comparisonReady = detail.comparisonStatus === "completed" && detail.comparisonSugar > 0 && detail.comparisonCalories > 0;

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
          <p className="eyebrow">{detail.category} · {detail.servings} · {detail.time} · {detail.difficulty}</p>
          <h1>{detail.title}</h1>
          <p>{detail.summary}</p>
          <div className="detail-metrics"><div><span>등록 재료 당류</span><strong>{detail.estimatedSugar}g</strong></div><div><span>등록 재료 열량</span><strong>{detail.estimatedCalories}kcal</strong></div><div><span>영양 계산률</span><strong>{detail.nutritionCoverage ?? 100}%</strong></div></div>
          <FavoriteButton label={detail.title} id={recipeId} kind="recipe" checkInitial />
          {detail.sourceUrl && <a className="source-link" href={detail.sourceUrl} target="_blank" rel="noreferrer">원본 레시피 보기 ↗</a>}
        </div>
      </section>

      <section className="recipe-compare wrap">
        {comparisonReady ? <>
          <header className="section-line-heading"><div><p className="eyebrow">일반 조리와 비교</p><h2>바꾼 재료가 수치에 어떻게 보이는지 확인해요</h2></div></header>
          <div className="compare-bars">
            <div><span>일반 조리</span><i><b style={{ width: "100%" }} /></i><strong>당류 {detail.comparisonSugar}g · {detail.comparisonCalories}kcal</strong></div>
            <div className="better"><span>이 레시피</span><i><b style={{ width: `${Math.round((detail.estimatedSugar / detail.comparisonSugar) * 100)}%` }} /></i><strong>당류 {detail.estimatedSugar}g · {detail.estimatedCalories}kcal</strong></div>
          </div>
        </> : <div className="recipe-data-status"><div><p className="eyebrow">영양 비교</p><h2>등록된 재료의 합계를 먼저 확인해보세요</h2><p>일반 조리법과 비교할 수 있는 값이 준비되면 당류와 열량 차이도 함께 알려드릴게요.</p></div><span><b>{detail.nutritionCoverage ?? 100}%</b>재료 영양 연결</span></div>}
        <p>영양값은 등록된 재료를 합산한 값이에요. 실제 섭취량과 사용한 제품에 따라 달라질 수 있어요.</p>
      </section>

      <section className="recipe-body wrap">
        <aside><p className="eyebrow">재료 · {detail.servings}</p>{detail.ingredients.map((item) => <div key={item}><span>{item}</span><i>✓</i></div>)}</aside>
        <div className="recipe-steps"><p className="eyebrow">간단히 보는 조리 순서</p>{detail.steps.map((step, index) => <article key={step.title}><span>{String(index + 1).padStart(2, "0")}</span><div><h3>{step.title}</h3><p>{step.description}</p></div></article>)}</div>
      </section>

      <section className="detail-products-band">
        <div className="used-products wrap">
          <header className="section-line-heading"><div><p className="eyebrow">이 요리에 활용할 수 있는 제품</p><h2>재료를 바꿀 때 함께 살펴보세요</h2></div><Link href="/search">식품 전체 보기 →</Link></header>
          {relatedProducts.length > 0 && <div className="compact-recommendations">{relatedProducts.map((product) => <Link href={`/product/${product.id}`} key={product.id}><div className="compact-product-photo"><SafeImage src={product.image} alt={`${product.title} 제품`} /></div><h3>{product.title}</h3><p>{product.serving} 기준 당류 {product.sugar}g · {product.calories}kcal</p><b>♥</b></Link>)}</div>}
          {substitutesLoaded && relatedProducts.length === 0 && <p className="used-products-empty">아직 매칭된 상품이 없어요.</p>}
        </div>
      </section>

      <section className="similar-section wrap">
        <header className="section-line-heading"><div><p className="eyebrow">비슷한 저당 레시피</p><h2>다음 메뉴도 이어서 살펴보세요</h2></div></header>
        <div className="similar-grid">{similar.map((recipe) => <Link href={`/recipes/${recipe.databaseId ?? recipe.slug}`} key={recipe.databaseId ?? recipe.slug}><RecipeCover recipe={recipe} /><small>{recipe.category}</small><h3>{recipe.title}</h3><p>등록 재료 당류 {recipe.estimatedSugar}g</p></Link>)}</div>
      </section>
    </main>
  );
}
