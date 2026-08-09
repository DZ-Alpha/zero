"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import { SafeImage } from "@/components/SafeImage";
import { FavoriteIconButton } from "@/components/FavoriteButton";
import { products as mockProducts } from "@/data/catalog";
import { PRODUCT_CATEGORIES, SWEETENER_FILTERS } from "@/data/taxonomy";
import { useAuthSession } from "@/hooks/useAuthSession";
import { useProductCatalog } from "@/hooks/useProductCatalog";
import { getProductFavorites, getSearchRecommendations } from "@/lib/api/zerocheck";

const personalSlugs = new Set([
  "lalasweet-low-sugar-soymilk",
  "fermented-konjac-rice",
  "low-sugar-wholewheat-konjac-bagel",
  "konjac-peach-zero-jelly",
]);
const personalIds = new Set(mockProducts.filter((product) => personalSlugs.has(product.slug)).map((product) => product.backendId).filter(Boolean));

function ProductFeedContent() {
  const searchParams = useSearchParams();
  const [query, setQuery] = useState(() => searchParams.get("query") ?? "");
  const [category, setCategory] = useState("전체");
  const [sugarFilter, setSugarFilter] = useState("전체");
  const [sweetener, setSweetener] = useState("전체");
  const [sort, setSort] = useState("추천순");
  const [personalOnly, setPersonalOnly] = useState(false);
  const [suggestions, setSuggestions] = useState<Array<{ id: string; name: string }>>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const sentinel = useRef<HTMLDivElement>(null);
  const resultsRef = useRef<HTMLDivElement>(null);
  const { ready: authReady, signedIn, token } = useAuthSession();
  const [favoriteProductIds, setFavoriteProductIds] = useState<Set<string>>(new Set());

  // /search?query=... 로 직접 들어오거나 다른 query값으로 링크를 다시 눌렀을 때도
  // 검색창과 실제 검색 요청에 반영되어야 한다 - 이전엔 query state가 항상 빈
  // 문자열로 시작해 URL의 query가 무시됐다(2026-07-31 리포트).
  useEffect(() => {
    setQuery(searchParams.get("query") ?? "");
  }, [searchParams]);

  // 목록 카드마다 즐겨찾기 여부를 개별 조회하면 N+1이라, 즐겨찾기 목록을 한 번만
  // 통으로 불러와 Set으로 대조한다(RecordMealModal.tsx/RecipeFeed.tsx와 같은 패턴).
  useEffect(() => {
    if (!authReady || !signedIn || !token) return;
    let active = true;
    getProductFavorites(token).then((result) => {
      if (active) setFavoriteProductIds(new Set(result["list-products"].map((item) => item.id)));
    }).catch(() => {
      // 조회 실패해도 하트는 기본(안 찜) 상태로 남는다 — 눌러서 다시 저장할 수 있다.
    });
    return () => {
      active = false;
    };
  }, [authReady, signedIn, token]);

  const categories = ["전체", ...PRODUCT_CATEGORIES.map((item) => item.label)];
  const sweeteners = ["전체", ...SWEETENER_FILTERS];
  const categoryCode = PRODUCT_CATEGORIES.find((item) => item.label === category)?.code;
  const apiSort = sort === "당류 낮은순"
    ? "sugar_asc"
    : sort === "열량 낮은순"
      ? "calorie_asc"
      : "rank";
  const { products, status, hasMore, loadingMore, loadMore, retry } = useProductCatalog({
    query: query.trim() || undefined,
    category: categoryCode,
    sort: apiSort,
  });
  const filtered = useMemo(() => {
    let list = products.filter((product) => {
      const hasNutrition = product.nutritionAvailable !== false;
      const sugarMatch = sugarFilter === "전체" || (hasNutrition && (sugarFilter === "당류 0g" ? product.sugar === 0 : sugarFilter === "당류 3g 이하" ? product.sugar <= 3 : product.calories <= 100));
      const sweetenerMatch = sweetener === "전체" || (hasNutrition && product.sweeteners.some((item) => item.includes(sweetener)));
      return sugarMatch && sweetenerMatch && (!personalOnly || personalIds.has(product.backendId));
    });
    return list;
  }, [personalOnly, products, sugarFilter, sweetener]);

  useEffect(() => {
    const keyword = query.trim();
    if (!keyword) {
      setSuggestions([]);
      return;
    }
    const timeout = window.setTimeout(() => {
      getSearchRecommendations(keyword)
        .then(({ items }) => setSuggestions(items.slice(0, 6)))
        .catch(() => setSuggestions([]));
    }, 180);
    return () => window.clearTimeout(timeout);
  }, [query]);

  useEffect(() => {
    const node = sentinel.current;
    if (!node) return;
    const observer = new IntersectionObserver(([entry]) => entry.isIntersecting && loadMore(), { rootMargin: "180px" });
    observer.observe(node);
    return () => observer.disconnect();
  }, [loadMore]);

  const recommendations = products.filter((product) => personalIds.has(product.backendId)).slice(0, 3);
  const recommendationItems = recommendations.length > 0
    ? recommendations
    : products.length > 0
      ? products.slice(0, 3)
      : mockProducts.filter((product) => personalSlugs.has(product.slug)).slice(0, 3);
  const activeFilters = [category !== "전체" ? category : "", sugarFilter !== "전체" ? sugarFilter : "", sweetener !== "전체" ? sweetener : "", personalOnly ? "추천 제품" : ""].filter(Boolean);

  // 검색은 이미 query state로 실시간 반영되지만, 카테고리 필터 영역이 화면
  // 위쪽을 차지해서 결과가 스크롤해야 보이는 위치에 있다(2026-08-01 피드백) -
  // 엔터/돋보기 클릭 시 결과 시작점으로 스크롤해 바로 보이게 한다.
  function scrollToResults() {
    resultsRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function resetFilters() {
    setQuery("");
    setCategory("전체");
    setSugarFilter("전체");
    setSweetener("전체");
    setPersonalOnly(false);
    setSort("추천순");
  }

  return (
    <main className="catalog-page product-catalog page-wrap">
      <section className="catalog-intro wrap">
        <div><p className="eyebrow">당당 저당 제품</p><h1>제품 사진과 성분을<br />같이 보고 골라요.</h1></div>
      </section>

      <section className="catalog-recommendation personal-products wrap">
        <header><div><span>기록에 맞춘 추천</span><h2>오늘 남은 당류에 맞는 제품</h2></div></header>
        <div>{recommendationItems.map((product, index) => <Link href={`/product/${product.backendId ?? product.slug}`} key={product.backendId ?? product.slug}><span className="recommendation-rank">0{index + 1}</span><div><h3>{product.title}</h3><p>{product.nutritionAvailable === false ? "상세에서 영양정보 확인" : `${product.serving} 기준 당류 ${product.sugar}g · ${product.calories}kcal`}</p></div></Link>)}</div>
      </section>

      <section className="product-results-band">
        <div className="catalog-explorer wrap">
          <aside className="catalog-filter-rail" aria-label="제품 검색과 필터">
            <div className="catalog-filter-title"><strong>제품 찾기</strong>{activeFilters.length > 0 && <button type="button" onClick={resetFilters}>초기화</button>}</div>
            <div className="catalog-search-wrap catalog-rail-search-wrap">
              <div className="catalog-rail-search"><input value={query} onChange={(event) => { setQuery(event.target.value); setShowSuggestions(true); }} onFocus={() => setShowSuggestions(true)} onBlur={() => window.setTimeout(() => setShowSuggestions(false), 120)} onKeyDown={(event) => { if (event.key === "Enter") { setShowSuggestions(false); scrollToResults(); } }} autoComplete="off" aria-autocomplete="list" aria-expanded={showSuggestions && suggestions.length > 0} placeholder="제품명·브랜드 검색" /><button type="button" onClick={scrollToResults} aria-label="검색 결과로 이동">⌕</button></div>
              {showSuggestions && suggestions.length > 0 && <div className="search-suggestions" role="listbox">{suggestions.map((item) => <button type="button" role="option" key={item.id} onMouseDown={(event) => event.preventDefault()} onClick={() => { setQuery(item.name); setShowSuggestions(false); }}>{item.name}</button>)}</div>}
            </div>
            <div className="catalog-filter-group"><strong>카테고리</strong><div className="catalog-filter-options">{categories.map((item) => <button type="button" className={category === item ? "is-active" : ""} onClick={() => setCategory(item)} key={item}><i aria-hidden="true" />{item}</button>)}</div></div>
            <div className="catalog-filter-group"><strong>영양 기준</strong><div className="catalog-filter-options">{["전체", "당류 0g", "당류 3g 이하", "100kcal 이하"].map((item) => <button type="button" className={sugarFilter === item ? "is-active" : ""} onClick={() => setSugarFilter(item)} key={item}><i aria-hidden="true" />{item}</button>)}</div></div>
            <div className="catalog-filter-group"><strong>감미료</strong><div className="catalog-filter-options">{sweeteners.map((item) => <button type="button" className={sweetener === item ? "is-active" : ""} onClick={() => setSweetener(item)} key={item}><i aria-hidden="true" />{item}</button>)}</div></div>
            <label className="catalog-rail-check"><input type="checkbox" checked={personalOnly} onChange={(event) => setPersonalOnly(event.target.checked)} /><span>내 기록 추천 제품만</span></label>
          </aside>

        <section className="catalog-list" ref={resultsRef}>
          <header className="catalog-tools"><p>{status === "loading" ? "저당 제품을 불러오는 중" : <><b>{filtered.length}</b>개의 저당 제품</>}</p><div className="catalog-sort"><select value={sort} onChange={(event) => setSort(event.target.value)} aria-label="제품 정렬"><option>추천순</option><option>당류 낮은순</option><option>열량 낮은순</option></select></div></header>
          {activeFilters.length > 0 && <div className="active-filter-summary" aria-label="적용된 필터"><span>적용한 조건</span>{activeFilters.map((item) => <b key={item}>{item}</b>)}<button type="button" onClick={resetFilters}>모두 지우기</button></div>}
          {status === "mock" && <div className="inline-service-notice" role="status"><div><b>서버에서 제품을 불러오지 못했어요.</b><span>지금은 준비된 제품 목록을 보여드려요.</span></div><button type="button" onClick={retry}>다시 불러오기</button></div>}
          {status === "loading" && <div className="catalog-loading" aria-live="polite"><i /><i /><i /><span>저당픽을 불러오고 있어요.</span></div>}
          <div className="product-feed">
            {status !== "loading" && filtered.map((product) => {
              const key = product.backendId ?? product.slug;
              return (
              <article className="product-feed-card" key={key}>
                <Link href={`/product/${key}`} className="product-feed-art"><div className="product-photo-card"><SafeImage src={product.image} alt={`${product.title} 제품 이미지`} fallbackLabel="제품 이미지 준비 중" /></div><span>{product.category}</span></Link>
                <div><small>{product.brand}{product.nutritionAvailable === false ? "" : ` · ${product.serving} 기준`}</small><h2><Link href={`/product/${key}`}>{product.title}</Link></h2>{product.nutritionAvailable === false ? <p>영양정보는 상세에서 확인해 주세요.</p> : <p>당류 <b>{product.sugar}g</b> · {product.calories}kcal</p>}<em>{product.sweeteners[0] ?? "원재료 확인"}</em></div>
                <FavoriteIconButton label={product.title} id={product.backendId} kind="product" initial={favoriteProductIds.has(String(product.backendId))} />
              </article>
            )})}
          </div>
          {hasMore && <div ref={sentinel} className="feed-sentinel">{loadingMore ? "다음 제품을 불러오고 있어요." : "아래로 내리면 제품을 더 볼 수 있어요."}</div>}
          {!hasMore && status !== "loading" && filtered.length > 0 && <div className="feed-end">현재 조건의 제품을 모두 봤어요.</div>}
          {status !== "loading" && filtered.length === 0 && <div className="empty-catalog"><b>조건에 맞는 제품이 없어요.</b><span>검색어를 짧게 바꾸거나 필터를 지우고 다시 찾아보세요.</span><button type="button" onClick={resetFilters}>검색 조건 지우기</button></div>}
        </section>
        </div>
      </section>
    </main>
  );
}

export function ProductFeed() {
  return (
    <Suspense fallback={<main className="catalog-page product-catalog page-wrap"><div className="catalog-loading" aria-live="polite"><i /><i /><i /><span>저당픽을 불러오고 있어요.</span></div></main>}>
      <ProductFeedContent />
    </Suspense>
  );
}
