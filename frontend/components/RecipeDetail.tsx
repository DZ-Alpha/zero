"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { FavoriteButton } from "@/components/FavoriteButton";
import { RecipeCover } from "@/components/RecipeCover";
import { SafeImage } from "@/components/SafeImage";
import { productBySlug, products, recipeBySlug, recipes, type RecipeData } from "@/data/catalog";
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
      comparisonStatus: nutrition?.comparisonStatus === "completed" ? "completed" as const : fallbackDetail.comparisonStatus,
      ingredients: live.ingredients?.length
        ? live.ingredients.map((item) => `${item.name}${item.amount ? ` ${item.amount}` : ""}`)
        : fallbackDetail.ingredients,
      steps: normalizeSteps(live.steps, fallbackDetail.steps),
    };
  }, [fallbackDetail, live]);
  const relatedProducts = useMemo(() => {
    const fallback = [
      productBySlug["nuts-green-low-sugar-gochujang"],
      productBySlug["low-sugar-oyster-sauce"],
      productBySlug["fermented-konjac-rice"],
    ];
    const matched = (liveSubstitutes?.substitutes ?? [])
      .flatMap((group) => group.products)
      .map((item) => products.find((product) => product.backendId === item.productId))
      .filter((product): product is NonNullable<typeof product> => Boolean(product));
    return [...matched, ...fallback].filter((product, index, list) => list.findIndex((item) => item.slug === product.slug) === index).slice(0, 3);
  }, [liveSubstitutes]);
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
          <FavoriteButton label={detail.title} id={recipeId} kind="recipe" />
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
          <div className="compact-recommendations">{relatedProducts.map((product) => <Link href={`/product/${product.backendId ?? product.slug}`} key={product.backendId ?? product.slug}><div className="compact-product-photo"><SafeImage src={product.image} alt={`${product.title} 제품`} /></div><h3>{product.title}</h3><p>{product.serving} 기준 당류 {product.sugar}g · {product.calories}kcal</p><b>♥</b></Link>)}</div>
        </div>
      </section>

      <section className="similar-section wrap">
        <header className="section-line-heading"><div><p className="eyebrow">비슷한 저당 레시피</p><h2>다음 메뉴도 이어서 살펴보세요</h2></div></header>
        <div className="similar-grid">{similar.map((recipe) => <Link href={`/recipes/${recipe.databaseId ?? recipe.slug}`} key={recipe.databaseId ?? recipe.slug}><RecipeCover recipe={recipe} /><small>{recipe.category} · {recipe.time}</small><h3>{recipe.title}</h3><p>등록 재료 당류 {recipe.estimatedSugar}g</p></Link>)}</div>
      </section>
    </main>
  );
}
