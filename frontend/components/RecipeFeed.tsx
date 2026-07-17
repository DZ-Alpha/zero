"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { RecipeCover } from "@/components/RecipeCover";
import { FavoriteIconButton } from "@/components/FavoriteButton";
import { recipes as mockRecipes } from "@/data/catalog";
import { RECIPE_CATEGORIES } from "@/data/taxonomy";
import { useRecipeCatalog } from "@/hooks/useRecipeCatalog";

const personalSlugs = new Set(mockRecipes.filter((recipe) => recipe.category === "한 끼" || recipe.category === "반찬").slice(0, 6).map((recipe) => recipe.slug));
const personalIds = new Set(mockRecipes.filter((recipe) => personalSlugs.has(recipe.slug)).map((recipe) => recipe.databaseId).filter(Boolean));

export function RecipeFeed() {
  const { recipes, source, loading, retry } = useRecipeCatalog(mockRecipes);
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("전체");
  const [sort, setSort] = useState("추천순");
  const [personalOnly, setPersonalOnly] = useState(false);
  const [visible, setVisible] = useState(6);
  const sentinel = useRef<HTMLDivElement>(null);

  const availableCategories = new Set(recipes.map((recipe) => recipe.category));
  const categories = ["전체", ...RECIPE_CATEGORIES.filter((item) => availableCategories.has(item))];
  const filtered = useMemo(() => {
    let list = recipes.filter((recipe) => {
      const queryMatch = [recipe.title, recipe.category, recipe.author, ...recipe.keywords].some((value) => value.includes(query));
      const categoryMatch = category === "전체" || recipe.category === category;
      return queryMatch && categoryMatch && (!personalOnly || personalSlugs.has(recipe.slug) || personalIds.has(recipe.databaseId));
    });
    if (sort === "인기순") list = [...list].sort((a, b) => b.savedDemo - a.savedDemo);
    if (sort === "빠른 조리순") list = [...list].sort((a, b) => Number.parseInt(a.time.replace(/\D/g, "")) - Number.parseInt(b.time.replace(/\D/g, "")));
    if (sort === "등록 당류 낮은순") list = [...list].sort((a, b) => a.estimatedSugar - b.estimatedSugar);
    return list;
  }, [category, personalOnly, query, recipes, sort]);

  useEffect(() => setVisible(6), [category, personalOnly, query, sort]);
  useEffect(() => {
    const node = sentinel.current;
    if (!node) return;
    const observer = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting) setVisible((count) => Math.min(count + 3, filtered.length));
    }, { rootMargin: "160px" });
    observer.observe(node);
    return () => observer.disconnect();
  }, [filtered.length]);

  const personalRecipes = recipes.filter((recipe) => personalSlugs.has(recipe.slug) || personalIds.has(recipe.databaseId)).slice(0, 3);
  const recommendationItems = personalRecipes.length > 0 ? personalRecipes : recipes.length > 0 ? recipes.slice(0, 3) : mockRecipes.slice(0, 3);
  const activeFilters = [category !== "전체" ? category : "", personalOnly ? "추천 메뉴" : ""].filter(Boolean);

  function resetFilters() {
    setQuery("");
    setCategory("전체");
    setPersonalOnly(false);
    setSort("추천순");
  }

  return (
    <main className="catalog-page page-wrap">
      <section className="catalog-intro wrap">
        <div>
          <p className="eyebrow">저당 레시피</p>
          <h1>등록된 재료까지 확인한<br />저당 메뉴를 모았어요.</h1>
          <p className="catalog-source-note">만개의레시피 데이터 중 재료 영양값이 모두 연결된 메뉴를 우선 보여드려요.</p>
        </div>
        <div className="catalog-search"><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="메뉴나 재료를 검색해보세요" /><span>⌕</span></div>
      </section>

      <section className="catalog-recommendation personal-picks wrap">
        <header><div><span>기록에 맞춘 추천</span><h2>최근 기록과 잘 맞는 메뉴예요</h2></div><p>한 끼는 든든하게, 간식의 단맛은 가볍게 고를 수 있도록 골랐어요.</p></header>
        <div>{recommendationItems.map((recipe, index) => <Link href={`/recipes/${recipe.databaseId ?? recipe.slug}`} key={recipe.databaseId ?? recipe.slug}><span className="recommendation-rank">0{index + 1}</span><div><h3>{recipe.title}</h3><p>{recipe.nutritionCoverage ? `등록 재료 당류 ${recipe.estimatedSugar}g` : "영양정보를 확인하고 있어요"}</p></div></Link>)}</div>
      </section>

      <section className="recipe-results-band">
        <div className="catalog-list wrap">
          <header className="catalog-tools">
          <div className="filter-chips">{categories.map((item) => <button type="button" className={category === item ? "is-active" : ""} onClick={() => setCategory(item)} key={item}>{item}</button>)}</div>
          <div className="catalog-sort"><label><input type="checkbox" checked={personalOnly} onChange={(event) => setPersonalOnly(event.target.checked)} />추천 메뉴만</label><select value={sort} onChange={(event) => setSort(event.target.value)}><option>추천순</option><option>인기순</option><option>빠른 조리순</option><option>등록 당류 낮은순</option></select></div>
          </header>
          {activeFilters.length > 0 && <div className="active-filter-summary" aria-label="적용된 필터"><span>적용한 조건</span>{activeFilters.map((item) => <b key={item}>{item}</b>)}<button type="button" onClick={resetFilters}>모두 지우기</button></div>}
          {source === "mock" && !loading && <div className="inline-service-notice" role="status"><div><b>서버에서 레시피를 불러오지 못했어요.</b><span>지금은 준비된 레시피 목록을 보여드려요.</span></div><button type="button" onClick={retry}>다시 불러오기</button></div>}
          {loading && <div className="catalog-loading" aria-live="polite"><i /><i /><i /><span>레시피를 불러오고 있어요.</span></div>}
          <div className="recipe-feed">
            {!loading && filtered.slice(0, visible).map((recipe) => {
              const key = recipe.databaseId ?? recipe.slug;
              return (
              <article className="feed-card" key={key}>
                <Link href={`/recipes/${key}`} className="feed-image"><RecipeCover recipe={recipe} /></Link>
                <div className="feed-card-copy"><small>{recipe.author}{recipe.nutritionCoverage ? ` · 영양 계산 ${recipe.nutritionCoverage}%` : ""}</small><h2><Link href={`/recipes/${key}`}>{recipe.title}</Link></h2><p>{recipe.nutritionCoverage ? <>등록 재료 합계 <b>당류 {recipe.estimatedSugar}g</b> · {recipe.estimatedCalories}kcal</> : "영양정보를 확인하고 있어요."}</p></div>
                <FavoriteIconButton label={recipe.title} />
              </article>
            )})}
          </div>
          {visible < filtered.length && <div ref={sentinel} className="feed-sentinel">다음 레시피를 불러오고 있어요.</div>}
          {!loading && visible >= filtered.length && filtered.length > 0 && <div className="feed-end">현재 조건의 레시피를 모두 봤어요.</div>}
          {!loading && filtered.length === 0 && <div className="empty-catalog"><b>조건에 맞는 레시피가 없어요.</b><span>검색어를 짧게 바꾸거나 선택한 분류를 지워보세요.</span><button type="button" onClick={resetFilters}>검색 조건 지우기</button></div>}
        </div>
      </section>
    </main>
  );
}
