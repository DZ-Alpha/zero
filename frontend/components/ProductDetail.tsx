"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { FavoriteButton } from "@/components/FavoriteButton";
import { SafeImage } from "@/components/SafeImage";
import { productBySlug, products, type ProductData } from "@/data/catalog";
import { useAuthSession } from "@/hooks/useAuthSession";
import { useDailyGauge } from "@/hooks/useDailyGauge";
import { getTodayKey, useDietRecords } from "@/hooks/useDietRecords";
import { useUserSettings } from "@/hooks/useUserSettings";
import {
  getProductAiSummary,
  getProductAlternatives,
  getProductDetail,
  getProductReviews,
  ProductAlternativesResponse,
  ProductDetailResponse,
  ProductReviewsResponse,
} from "@/lib/api/zerocheck";
import { renderInlineMarkdown } from "@/lib/inlineMarkdown";

function format(value: number) {
  return Number.isInteger(value) ? String(value) : value.toFixed(2).replace(/0+$/, "").replace(/\.$/, "");
}

export function ProductDetail({ slug = "lotte-cinema-zero-popcorn" }: { slug?: string }) {
  const { token } = useAuthSession();
  const remoteGauge = useDailyGauge(token);
  const { recordsByDate } = useDietRecords();
  const { goals, profile } = useUserSettings();
  const catalogDetail = productBySlug[slug] ?? products.find((product) => product.backendId === slug) ?? null;
  const productId = catalogDetail?.backendId ?? (/^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(slug) ? slug : null);
  const fallbackDetail = useMemo<ProductData>(() => catalogDetail ?? ({
    backendId: productId ?? undefined,
    slug,
    foodCode: productId?.slice(0, 13).toUpperCase() ?? "",
    title: "상품 정보를 불러오고 있어요",
    brand: "브랜드 정보 준비 중",
    maker: "",
    category: "가공식품",
    serving: "100g",
    calories: 0,
    sugar: 0,
    protein: 0,
    fat: 0,
    carbs: 0,
    ingredients: [],
    sweeteners: [],
    image: "",
    summary: "영양정보와 원재료를 확인하고 있어요.",
    savedDemo: 0,
  }), [catalogDetail, productId, slug]);
  const [liveDetail, setLiveDetail] = useState<ProductDetailResponse | null>(null);
  const [liveSummary, setLiveSummary] = useState<string | null>(null);
  const [alternativeResult, setAlternativeResult] = useState<ProductAlternativesResponse | null>(null);
  const [reviewResult, setReviewResult] = useState<ProductReviewsResponse | null>(null);
  const [loading, setLoading] = useState(Boolean(productId));
  const [unavailable, setUnavailable] = useState(!catalogDetail && !productId);

  // 기본 상품 정보(가격/영양성분 등)는 AI 요약 3종과 분리해서 먼저 불러온다 —
  // 전부 Promise.all로 묶으면 상품 정보가 다 준비돼도 가장 느린 AI 호출(매번
  // 실시간으로 Claude를 부르는 캐싱 없는 요청)이 끝날 때까지 로딩 스피너에
  // 막혀 있었다. AI 3종은 각자 도착하는 대로 해당 섹션만 채운다.
  useEffect(() => {
    setLiveDetail(null);
    setAlternativeResult(null);
    setReviewResult(null);
    if (!productId) {
      setLoading(false);
      setUnavailable(!catalogDetail);
      return;
    }
    let active = true;
    setLoading(true);
    setUnavailable(false);

    getProductDetail(productId).then((base) => {
      if (!active) return;
      setLiveDetail(base);
    }).catch(() => {
      if (active) setUnavailable(!catalogDetail);
    }).finally(() => {
      if (active) setLoading(false);
    });
    getProductAlternatives(productId)
      .then((result) => {
        if (active) setAlternativeResult(result);
      })
      .catch(() => {});
    getProductReviews(productId)
      .then((result) => {
        if (active) setReviewResult(result);
      })
      .catch(() => {});

    return () => {
      active = false;
    };
  }, [catalogDetail, productId]);

  useEffect(() => {
    setLiveSummary(null);
    if (!productId) return;
    let active = true;

    // 단맛을 낸 원재료 섹션은 AI 요약(gammi-info)을 뺐다(2026-07-31 요청) -
    // 원재료명 기반 고정 문구만 쓰므로 더 이상 호출하지 않는다.
    getProductAiSummary(productId).then((summary) => {
      if (active) setLiveSummary(summary?.["ai-oneline"] ?? null);
    }).catch(() => {});

    return () => {
      active = false;
    };
  }, [productId]);

  const detail = useMemo(() => ({
    ...fallbackDetail,
    title: liveDetail?.name || fallbackDetail.title,
    brand: liveDetail?.brand || fallbackDetail.brand,
    category: liveDetail?.category || fallbackDetail.category,
    serving: liveDetail?.serving || fallbackDetail.serving,
    calories: liveDetail?.cal ?? fallbackDetail.calories,
    sugar: liveDetail?.dang ?? fallbackDetail.sugar,
    protein: liveDetail?.danb ?? fallbackDetail.protein,
    fat: liveDetail?.fat ?? fallbackDetail.fat,
    carbs: liveDetail?.carb ?? fallbackDetail.carbs,
    ingredients: liveDetail?.ingredi ? [liveDetail.ingredi] : fallbackDetail.ingredients,
    image: liveDetail?.imageUrl || fallbackDetail.image,
    summary: liveSummary || fallbackDetail.summary,
  }), [fallbackDetail, liveDetail, liveSummary]);
  const similar = products
    .filter((product) => product.slug !== detail.slug && product.category === detail.category)
    .concat(products.filter((product) => product.slug !== detail.slug))
    .slice(0, 3);
  const hasAlternatives = alternativeResult?.status === "AVAILABLE" && alternativeResult.alternatives.length > 0;
  const sweetenerTitle = detail.sweeteners.length > 0 ? `${detail.sweeteners[0]}을(를) 사용했어요.` : "원재료를 한 번 더 확인해보세요.";
  const todayRecords = recordsByDate[getTodayKey()] ?? [];
  const currentSugar = Math.round((todayRecords.filter((item) => item.source !== "server").reduce((sum, item) => sum + item.sugar, 0) + Number(remoteGauge?.sugar ?? 0) + Number.EPSILON) * 100) / 100;
  const currentCalories = todayRecords.filter((item) => item.source !== "server").reduce((sum, item) => sum + item.calories, 0) + Number(remoteGauge?.cal ?? 0);
  const todaySugar = Math.round((currentSugar + detail.sugar + Number.EPSILON) * 100) / 100;
  const todayCalories = currentCalories + detail.calories;
  const todayRate = Math.round((todaySugar / goals.sugar) * 100);
  const calorieRate = Math.round((todayCalories / goals.calories) * 100);
  const remainingSugar = Math.round((goals.sugar - todaySugar + Number.EPSILON) * 100) / 100;
  const withinGoal = remainingSugar >= 0;
  const matchedAllergens = (liveDetail?.allerg ?? []).filter((allergen) =>
    (profile.allergens ?? []).some((selected) =>
      allergen.replace(/\s/g, "").includes(selected.replace(/\s/g, "")),
    ),
  );

  if (loading && !catalogDetail) {
    return <main className="detail-page page-wrap"><div className="detail-state wrap"><div className="catalog-loading"><i /><i /><i /><span>상품 정보를 불러오고 있어요.</span></div></div></main>;
  }

  if (unavailable && !catalogDetail) {
    return <main className="detail-page page-wrap"><div className="detail-state wrap"><h1>상품을 찾을 수 없어요.</h1><p>목록으로 돌아가 다른 상품을 확인해보세요.</p><Link href="/search">상품 목록 보기</Link></div></main>;
  }

  return (
    <main className="detail-page product-detail page-wrap">
      <section className="product-detail-hero wrap">
        <div className="product-detail-photo"><SafeImage src={detail.image} alt={`${detail.title} 제품 이미지`} loading="eager" fallbackLabel="제품 이미지 준비 중" /></div>
        <div className="product-detail-copy">
          <h1>{detail.title}</h1>
          <p>{liveSummary && <span className="ai-summary-badge">AI 요약</span>}{renderInlineMarkdown(detail.summary)}</p>
          <div className="product-key-nutrients"><div><span>당류</span><strong>{format(detail.sugar)}g</strong></div><div><span>열량</span><strong>{format(detail.calories)}kcal</strong></div><div><span>단백질</span><strong>{format(detail.protein)}g</strong></div><div><span>탄수화물</span><strong>{format(detail.carbs)}g</strong></div></div>
          <FavoriteButton label={detail.title} id={productId} kind="product" checkInitial />
        </div>
      </section>

      {token && matchedAllergens.length > 0 && (
        <section className="allergen-user-warning wrap" role="alert">
          <div><strong>내 주의 성분과 겹쳐요</strong><span>{matchedAllergens.join(", ")}</span></div>
          <p>알레르기 판단을 대신하는 정보가 아니에요. 구매·섭취 전 제품 포장의 최신 원재료명과 알레르기 표시를 반드시 확인해 주세요.</p>
        </section>
      )}

      <section className="personal-ai-note wrap">
        {token ? (
          <>
            <div><p className="eyebrow">오늘 기록에 더하면</p><h2>오늘 당류가 {format(todaySugar)}g이 돼요.</h2></div>
            <div><p>현재 기록 {format(currentSugar)}g · {currentCalories.toLocaleString()}kcal에 이 제품의 {detail.serving} 기준 영양값을 더했어요. 실제로 먹은 양을 바꾸면 수치도 다시 계산돼요.</p><div className="personal-ai-metrics"><span>당류 목표 {format(goals.sugar)}g 중 {todayRate}%</span><span>칼로리 목표 {goals.calories.toLocaleString()}kcal 중 {calorieRate}%</span></div></div>
          </>
        ) : (
          <div><p className="eyebrow">오늘 기록에 더하면</p><h2>로그인하면 오늘 기록에 더한 당류를 볼 수 있어요.</h2><p><Link href="/login">로그인하기 →</Link></p></div>
        )}
      </section>

      <section className="ingredient-story wrap">
        <article>
          <p className="eyebrow">단맛을 낸 원재료</p>
          <h2>{sweetenerTitle}</h2>
          <p>{renderInlineMarkdown(detail.sweeteners.length > 0 ? `${detail.sweeteners.join(", ")}이(가) 원재료명에 들어 있어요. 이름만 보기보다 먹는 양과 전체 영양성분을 함께 확인해 주세요.` : "원재료명에서 특정 대체 감미료를 바로 확인하기 어려워요. 구매한 제품의 최신 원재료명을 한 번 더 확인해 주세요.")}</p>
          <Link href="/search">다른 제품과 비교하기 →</Link>
        </article>
        <div className="personal-product-analysis">
          <p className="eyebrow">오늘 기록을 바탕으로 한 안내</p>
          {token ? (
            <>
              <h3>{withinGoal ? "오늘 목표 안에서 선택할 수 있어요." : "오늘은 먹는 양을 조금 조절해보세요."}</h3>
              <p>오늘 이미 당류 {format(currentSugar)}g을 기록했어요. {detail.serving}을 추가하면 오늘 누적 당류가 {format(todaySugar)}g이 돼요 — {withinGoal ? `목표까지 ${format(remainingSugar)}g 남아요.` : `목표를 ${format(Math.abs(remainingSugar))}g 넘어요.`}</p>
              <div className="analysis-points">
                <span><b>{format(detail.sugar)}g</b>이 제품의 당류</span>
                <span><b>{format(detail.calories)}kcal</b>이 제품의 열량</span>
              </div>
              <small>알레르기나 건강 상태에 따라 필요한 기준은 달라질 수 있어요. 제품 포장지의 표시도 함께 확인해 주세요.</small>
            </>
          ) : (
            <>
              <h3>로그인하면 내 기록 기반 안내를 볼 수 있어요.</h3>
              <p>오늘 먹은 양과 목표를 반영한 맞춤 안내는 로그인 후 확인할 수 있어요.</p>
              <Link href="/login">로그인하기 →</Link>
            </>
          )}
        </div>
      </section>

      <section className="review-summary wrap">
        <header>
          <div><p className="eyebrow">최근 리뷰 요약</p><h2>사람들이 남긴 이야기를 한눈에 볼 수 있어요</h2></div>
          <span>{reviewResult ? `${reviewResult.total}개${reviewResult.summary?.includesExample ? " · 예시 포함" : ""}` : "리뷰 확인 중"}</span>
        </header>
        {reviewResult?.reviews.length ? reviewResult.reviews.map((review) => (
          <div className="review-empty" key={review.id}><i aria-hidden="true">{review.rating}★</i><p>{review.isExample ? "[예시 리뷰] " : ""}{review.content}</p></div>
        )) : <div className="review-empty"><i aria-hidden="true">✦</i><p>아직 모인 리뷰가 없어요. 리뷰가 쌓이면 맛, 단맛, 식감과 재구매 의견을 짧게 정리해드릴게요.</p></div>}
      </section>

      <section className="product-similar-band">
        <div className="similar-section wrap">
          <header className="section-line-heading"><div><p className="eyebrow">{hasAlternatives ? "저당 대안" : "비슷한 상품"}</p><h2>{hasAlternatives ? "이거 대신 이건 어때요?" : "같은 카테고리에서 비교해보세요"}</h2></div><Link href="/search">제품 전체 보기 →</Link></header>
          {alternativeResult?.status === "ALREADY_LOW" && <div className="review-empty"><i aria-hidden="true">✓</i><p>이미 당류 0g이라 더 낮은 대안을 권하지 않아요.</p></div>}
          {alternativeResult?.status !== "ALREADY_LOW" && (
            <div className="compact-recommendations">
              {hasAlternatives
                ? alternativeResult.alternatives.map((product) => <Link href={`/product/${product.id}`} key={product.id}><div className="compact-product-photo"><SafeImage src={product.image ?? ""} alt={`${product.name} 제품`} /></div><h3>{product.name}</h3><p>당류 {format(product.sugar)}g · 기존보다 {format(product.sugarSavedG)}g 낮아요</p><b>♥</b></Link>)
                : similar.map((product) => <Link href={`/product/${product.backendId ?? product.slug}`} key={product.backendId ?? product.slug}><div className="compact-product-photo"><SafeImage src={product.image} alt={`${product.title} 제품`} /></div><h3>{product.title}</h3><p>{product.serving} 기준 당류 {format(product.sugar)}g · {format(product.calories)}kcal</p><b>♥</b></Link>)}
            </div>
          )}
        </div>
      </section>
    </main>
  );
}
