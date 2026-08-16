"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { RecipeCover } from "@/components/RecipeCover";
import { FavoriteIconButton } from "@/components/FavoriteButton";
import { portionPrefix, recipes as mockRecipes } from "@/data/catalog";
import { RECIPE_CATEGORIES } from "@/data/taxonomy";
import { useAuthSession } from "@/hooks/useAuthSession";
import { useRecipeCatalog } from "@/hooks/useRecipeCatalog";
import { getRecipeFavorites } from "@/lib/api/zerocheck";

export function RecipeFeed() {
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("전체");
  const [sort, setSort] = useState("당류 감소순");
  const [personalOnly, setPersonalOnly] = useState(false);
  const [visible, setVisible] = useState(6);
  const sentinel = useRef<HTMLDivElement>(null);
  const { ready: authReady, signedIn, token } = useAuthSession();
  const [favoriteRecipeIds, setFavoriteRecipeIds] = useState<Set<string>>(new Set());
  // 목록은 수집한 레시피 전체를 보여준다. eligible=true 로 고정돼 있어서 재료 비교가
  // 끝난 345건만 닿을 수 있었다(2026-08-16) — 1,709건 중 5분의 1이다. 이제 그 조건은
  // 아래 체크박스를 켤 때만 걸린다.
  const { recipes, source, loading, total, hasMore, loadMore, retry } = useRecipeCatalog(mockRecipes, {
    search: query.trim() || undefined,
    sort: sort === "당류 감소순" ? "sugarReduction" : undefined,
    eligible: personalOnly || undefined,
    category: category !== "전체" ? category : undefined,
  });
  // 추천 띠("재료 비교가 끝난 메뉴")는 목록과 기준이 다르므로 따로 부른다. 목록에서
  // 앞 3건을 자르면 비교가 안 끝난 레시피가 추천으로 올라간다.
  const { recipes: verifiedRecipes } = useRecipeCatalog(mockRecipes, { sort: "sugarReduction", eligible: true });
  const recommendationItems = useMemo(() => verifiedRecipes.slice(0, 3), [verifiedRecipes]);

  // 목록 카드마다 즐겨찾기 여부를 개별 조회하면 N+1이라, 즐겨찾기 목록을 한 번만
  // 통으로 불러와 Set으로 대조한다(RecordMealModal.tsx와 같은 패턴) — 이게
  // 없으면 찜 저장/해제는 잘 되는데 목록을 다시 불러올 때마다 항상 "안 찜"
  // 상태로 보이는 문제가 있었다.
  useEffect(() => {
    if (!authReady || !signedIn || !token) return;
    let active = true;
    getRecipeFavorites(token).then((result) => {
      if (active) setFavoriteRecipeIds(new Set(result["list-receipe"].map((item) => String(item.id))));
    }).catch(() => {
      // 조회 실패해도 하트는 기본(안 찜) 상태로 남는다 — 눌러서 다시 저장할 수 있다.
    });
    return () => {
      active = false;
    };
  }, [authReady, signedIn, token]);

  // 칩은 항상 전 카테고리를 보여준다. 예전처럼 받아온 recipes 에서 뽑으면, 카테고리를
  // 서버로 거른 뒤에는 그 카테고리 하나만 남아 다른 칩으로 갈아탈 수 없다.
  const categories = ["전체", ...RECIPE_CATEGORIES];
  const filtered = useMemo(() => {
    let list = recipes.filter((recipe) => {
      // 카테고리와 eligible 은 서버 쿼리로 넘어갔다. 여기서 또 거르면 안 된다 -
      // 받아온 페이지 안에서만 거르던 게 무한 스크롤이 멈추던 원인이었다.
      return [recipe.title, recipe.category, recipe.author, ...recipe.keywords].some((value) => value.includes(query));
    });
    if (sort === "인기순") list = [...list].sort((a, b) => b.savedDemo - a.savedDemo);
    // "빠른 조리순"은 조리 시간 숨김(RecipeCover.tsx 참고)과 함께 잠시 뺐다 —
    // DB 레시피 대부분 time이 "조리 시간 준비 중"이라 파싱이 NaN이 돼 정렬이
    // 사실상 동작하지 않았다. 시간 데이터가 채워지면 옵션과 함께 되돌린다.
    if (sort === "당류 낮은순") list = [...list].sort((a, b) => a.estimatedSugar - b.estimatedSugar);
    return list;
  }, [category, query, recipes, sort]);

  useEffect(() => setVisible(6), [category, personalOnly, query, sort]);
  useEffect(() => {
    const node = sentinel.current;
    if (!node) return;
    const observer = new IntersectionObserver(([entry]) => {
      if (!entry.isIntersecting) return;
      setVisible((count) => Math.min(count + 3, filtered.length));
      // 로드된 recipes 안에서 보여줄 게 거의 떨어져 가면(필터 없는 "전체" 상태
      // 기준) 서버에서 다음 페이지를 더 받아온다 - 그냥 필터링된 20건 안에서만
      // 더 보여주면 실제로는 1700여 건 중 20건 이후로 절대 안 보이는 문제가 있었다.
      if (hasMore && recipes.length - visible <= 6) loadMore();
    }, { rootMargin: "160px" });
    observer.observe(node);
    return () => observer.disconnect();
  }, [filtered.length, hasMore, loadMore, recipes.length, visible]);

  const activeFilters = [category !== "전체" ? category : "", personalOnly ? "재료 비교 완료" : ""].filter(Boolean);

  function resetFilters() {
    setQuery("");
    setCategory("전체");
    setPersonalOnly(false);
    setSort("당류 감소순");
  }

  return (
    <main className="catalog-page page-wrap">
      <section className="catalog-intro wrap">
        <div>
          <p className="eyebrow">저당 레시피</p>
          <h1>수집한 저당 레시피를<br />모두 모았어요.</h1>
        </div>
      </section>

      <section className="catalog-recommendation personal-picks wrap">
        <header><div><span>재료 비교가 끝난 메뉴</span><h2>당류를 덜어낸 순서로 골랐어요</h2></div></header>
        <div>{recommendationItems.map((recipe, index) => <Link href={`/recipes/${recipe.databaseId ?? recipe.slug}`} key={recipe.databaseId ?? recipe.slug}><span className="recommendation-rank">0{index + 1}</span><div><h3>{recipe.title}</h3><p>{portionPrefix(recipe)}당류 {recipe.estimatedSugar}g · {portionPrefix(recipe)}{recipe.estimatedCalories}kcal</p></div></Link>)}</div>
      </section>

      <section className="recipe-results-band">
        <div className="catalog-explorer wrap">
          <aside className="catalog-filter-rail" aria-label="레시피 검색과 필터">
            <div className="catalog-filter-title"><strong>레시피 찾기</strong>{activeFilters.length > 0 && <button type="button" onClick={resetFilters}>초기화</button>}</div>
            <div className="catalog-rail-search"><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="메뉴나 재료 검색" /><span aria-hidden="true">⌕</span></div>
            <div className="catalog-filter-group">
              <strong>카테고리</strong>
              <div className="catalog-filter-options">{categories.map((item) => <button type="button" className={category === item ? "is-active" : ""} onClick={() => setCategory(item)} key={item}><i aria-hidden="true" />{item}</button>)}</div>
            </div>
            <label className="catalog-rail-check"><input type="checkbox" checked={personalOnly} onChange={(event) => setPersonalOnly(event.target.checked)} /><span>재료 비교가 끝난 메뉴만</span></label>
          </aside>
          <section className="catalog-list">
          <header className="catalog-tools"><p>{loading ? "레시피를 불러오는 중" : source === "mock" ? "레시피 목록" : category !== "전체" || personalOnly ? "선택한 조건의 레시피" : <><b>{total.toLocaleString()}</b>개의 레시피</>}</p><div className="catalog-sort"><select value={sort} onChange={(event) => setSort(event.target.value)} aria-label="레시피 정렬"><option>당류 감소순</option><option>인기순</option><option>당류 낮은순</option></select></div></header>
          {activeFilters.length > 0 && <div className="active-filter-summary" aria-label="적용된 필터"><span>적용한 조건</span>{activeFilters.map((item) => <b key={item}>{item}</b>)}<button type="button" onClick={resetFilters}>모두 지우기</button></div>}
          {source === "mock" && !loading && <div className="inline-service-notice" role="status"><div><b>레시피 목록을 잠시 불러오지 못했어요.</b><span>잠시 후 다시 시도해 주세요.</span></div><button type="button" onClick={retry}>다시 불러오기</button></div>}
          {loading && <div className="catalog-loading" aria-live="polite"><i /><i /><i /><span>레시피를 불러오고 있어요.</span></div>}
          <div className="recipe-feed">
            {!loading && filtered.slice(0, visible).map((recipe) => {
              const key = recipe.databaseId ?? recipe.slug;
              return (
              <article className="feed-card" key={key}>
                <Link href={`/recipes/${key}`} className="feed-image"><RecipeCover recipe={recipe} /></Link>
                <div className="feed-card-copy"><small>{recipe.author}</small><h2><Link href={`/recipes/${key}`}>{recipe.title}</Link></h2><p>{recipe.nutritionCoverage ? <><b>{portionPrefix(recipe)}당류 {recipe.estimatedSugar}g</b> · {portionPrefix(recipe)}{recipe.estimatedCalories}kcal</> : "영양정보를 확인하고 있어요."}</p></div>
                <FavoriteIconButton label={recipe.title} id={recipe.databaseId} kind="recipe" initial={favoriteRecipeIds.has(String(recipe.databaseId))} />
              </article>
            )})}
          </div>
          {/* hasMore일 땐 filtered 안에 아직 다 안 보여줬어도, 서버에 더 있는데
              화면엔 다 보여준 상태(visible >= filtered.length)일 수 있어 sentinel을
              계속 걸어둬야 loadMore가 트리거된다. */}
          {(visible < filtered.length || hasMore) && <div ref={sentinel} className="feed-sentinel">다음 레시피를 불러오고 있어요.</div>}
          {!loading && !hasMore && visible >= filtered.length && filtered.length > 0 && <div className="feed-end">현재 조건의 레시피를 모두 봤어요.</div>}
          {!loading && filtered.length === 0 && <div className="empty-catalog"><b>조건에 맞는 레시피가 없어요.</b><span>검색어를 짧게 바꾸거나 선택한 분류를 지워보세요.</span><button type="button" onClick={resetFilters}>검색 조건 지우기</button></div>}
          </section>
        </div>
      </section>
    </main>
  );
}
