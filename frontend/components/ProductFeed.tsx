"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { SafeImage } from "@/components/SafeImage";
import { FavoriteIconButton } from "@/components/FavoriteButton";
import { products as mockProducts } from "@/data/catalog";
import { PRODUCT_CATEGORIES, SWEETENER_FILTERS } from "@/data/taxonomy";
import { useProductCatalog } from "@/hooks/useProductCatalog";
import { getSearchRecommendations } from "@/lib/api/zerocheck";

const personalSlugs = new Set([
  "lalasweet-low-sugar-soymilk",
  "fermented-konjac-rice",
  "low-sugar-wholewheat-konjac-bagel",
  "konjac-peach-zero-jelly",
]);
const personalIds = new Set(mockProducts.filter((product) => personalSlugs.has(product.slug)).map((product) => product.backendId).filter(Boolean));

export function ProductFeed() {
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("전체");
  const [sugarFilter, setSugarFilter] = useState("전체");
  const [sweetener, setSweetener] = useState("전체");
  const [sort, setSort] = useState("추천순");
  const [personalOnly, setPersonalOnly] = useState(false);
  const [suggestions, setSuggestions] = useState<Array<{ id: string; name: string }>>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const sentinel = useRef<HTMLDivElement>(null);

  const categories = ["전체", ...PRODUCT_CATEGORIES.map((item) => item.label)];
  const sweeteners = ["전체", ...SWEETENER_FILTERS];
  const categoryCode = PRODUCT_CATEGORIES.find((item) => item.label === category)?.code;
  const { products, status, hasMore, loadingMore, loadMore, retry } = useProductCatalog({
    query: query.trim() || undefined,
    category: categoryCode,
    sort: "rank",
  });
  const filtered = useMemo(() => {
    let list = products.filter((product) => {
      const hasNutrition = product.nutritionAvailable !== false;
      const sugarMatch = sugarFilter === "전체" || (hasNutrition && (sugarFilter === "당류 0g" ? product.sugar === 0 : sugarFilter === "당류 3g 이하" ? product.sugar <= 3 : product.calories <= 100));
      const sweetenerMatch = sweetener === "전체" || (hasNutrition && product.sweeteners.some((item) => item.includes(sweetener)));
      return sugarMatch && sweetenerMatch && (!personalOnly || personalIds.has(product.backendId));
    });
    if (sort === "인기순") list = [...list].sort((a, b) => b.savedDemo - a.savedDemo);
    if (sort === "당류 낮은순") list = [...list].sort((a, b) => a.sugar - b.sugar);
    if (sort === "열량 낮은순") list = [...list].sort((a, b) => a.calories - b.calories);
    return list;
  }, [personalOnly, products, sort, sugarFilter, sweetener]);

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
        <div><p className="eyebrow">제로·저당 식품</p><h1>제품 사진과 성분을<br />같이 보고 골라요.</h1><p className="catalog-source-note">제품의 영양정보와 원재료를 한곳에서 비교해보세요.</p></div>
        <div className="catalog-search-wrap">
          <div className="catalog-search"><input value={query} onChange={(event) => { setQuery(event.target.value); setShowSuggestions(true); }} onFocus={() => setShowSuggestions(true)} onBlur={() => window.setTimeout(() => setShowSuggestions(false), 120)} autoComplete="off" aria-autocomplete="list" aria-expanded={showSuggestions && suggestions.length > 0} placeholder="제품명, 브랜드, 원재료를 검색해보세요" /><span>⌕</span></div>
          {showSuggestions && suggestions.length > 0 && <div className="search-suggestions" role="listbox">{suggestions.map((item) => <button type="button" role="option" key={item.id} onMouseDown={(event) => event.preventDefault()} onClick={() => { setQuery(item.name); setShowSuggestions(false); }}>{item.name}</button>)}</div>}
        </div>
      </section>

      <section className="catalog-recommendation personal-products wrap">
        <header><div><span>기록에 맞춘 추천</span><h2>오늘 남은 당류를 고려했어요</h2></div><p>간식과 한 끼에 바로 더해볼 수 있는 제품부터 보여드려요.</p></header>
        <div>{recommendationItems.map((product, index) => <Link href={`/product/${product.backendId ?? product.slug}`} key={product.backendId ?? product.slug}><span className="recommendation-rank">0{index + 1}</span><div><h3>{product.title}</h3><p>{product.nutritionAvailable === false ? "상세에서 영양정보 확인" : `${product.serving} 기준 당류 ${product.sugar}g · ${product.calories}kcal`}</p></div></Link>)}</div>
      </section>

      <section className="product-results-band">
        <div className="product-filter-section wrap">
          <div className="filter-row"><span>카테고리</span><div>{categories.map((item) => <button type="button" className={category === item ? "is-active" : ""} onClick={() => setCategory(item)} key={item}>{item}</button>)}</div></div>
          <div className="filter-row"><span>영양 기준</span><div>{["전체", "당류 0g", "당류 3g 이하", "100kcal 이하"].map((item) => <button type="button" className={sugarFilter === item ? "is-active" : ""} onClick={() => setSugarFilter(item)} key={item}>{item}</button>)}</div></div>
          <div className="filter-row"><span>감미료</span><div>{sweeteners.map((item) => <button type="button" className={sweetener === item ? "is-active" : ""} onClick={() => setSweetener(item)} key={item}>{item}</button>)}</div></div>
        </div>

        <section className="catalog-list wrap">
          <header className="catalog-tools"><p><b>{filtered.length}</b>개의 제품</p><div className="catalog-sort"><label><input type="checkbox" checked={personalOnly} onChange={(event) => setPersonalOnly(event.target.checked)} />추천 제품만</label><select value={sort} onChange={(event) => setSort(event.target.value)}><option>추천순</option><option>인기순</option><option>당류 낮은순</option><option>열량 낮은순</option></select></div></header>
          {activeFilters.length > 0 && <div className="active-filter-summary" aria-label="적용된 필터"><span>적용한 조건</span>{activeFilters.map((item) => <b key={item}>{item}</b>)}<button type="button" onClick={resetFilters}>모두 지우기</button></div>}
          {status === "mock" && <div className="inline-service-notice" role="status"><div><b>서버에서 제품을 불러오지 못했어요.</b><span>지금은 준비된 제품 목록을 보여드려요.</span></div><button type="button" onClick={retry}>다시 불러오기</button></div>}
          {status === "loading" && <div className="catalog-loading" aria-live="polite"><i /><i /><i /><span>제품을 불러오고 있어요.</span></div>}
          <div className="product-feed">
            {status !== "loading" && filtered.map((product) => {
              const key = product.backendId ?? product.slug;
              return (
              <article className="product-feed-card" key={key}>
                <Link href={`/product/${key}`} className="product-feed-art"><div className="product-photo-card"><SafeImage src={product.image} alt={`${product.title} 제품 이미지`} fallbackLabel="제품 이미지 준비 중" /></div><span>{product.category}</span></Link>
                <div><small>{product.brand}{product.nutritionAvailable === false ? "" : ` · ${product.serving} 기준`}</small><h2><Link href={`/product/${key}`}>{product.title}</Link></h2>{product.nutritionAvailable === false ? <p>영양정보는 상세에서 확인해 주세요.</p> : <p>당류 <b>{product.sugar}g</b> · {product.calories}kcal</p>}<em>{product.sweeteners[0] ?? "원재료 확인"}</em></div>
                <FavoriteIconButton label={product.title} />
              </article>
            )})}
          </div>
          {hasMore && <div ref={sentinel} className="feed-sentinel">{loadingMore ? "다음 제품을 불러오고 있어요." : "아래로 내리면 제품을 더 볼 수 있어요."}</div>}
          {!hasMore && status !== "loading" && filtered.length > 0 && <div className="feed-end">현재 조건의 제품을 모두 봤어요.</div>}
          {status !== "loading" && filtered.length === 0 && <div className="empty-catalog"><b>조건에 맞는 제품이 없어요.</b><span>검색어를 짧게 바꾸거나 필터를 지우고 다시 찾아보세요.</span><button type="button" onClick={resetFilters}>검색 조건 지우기</button></div>}
        </section>
      </section>
    </main>
  );
}
