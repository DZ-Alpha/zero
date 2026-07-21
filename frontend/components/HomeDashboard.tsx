"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { RecordMealModal } from "@/components/RecordMealModal";
import { ServiceBanner } from "@/components/ServiceBanner";
import { products, recipes } from "@/data/catalog";
import { useAuthSession } from "@/hooks/useAuthSession";
import { useDailyGauge } from "@/hooks/useDailyGauge";
import { DietRecord, getTodayKey, keyToDate, MealType, useDietRecords } from "@/hooks/useDietRecords";
import { useUserSettings } from "@/hooks/useUserSettings";
import { withMockFallback } from "@/lib/api/client";
import { getProductRanking, getUserRecommendations, HomeProductItem } from "@/lib/api/zerocheck";

type RankingItem = { name: string; meta: string; saved: number; href: string };

const meals: MealType[] = ["아침", "점심", "저녁", "간식"];

const recipeRanking: RankingItem[] = recipes.map((recipe) => ({ name: recipe.title, meta: `${recipe.time} · 등록 재료 당류 ${recipe.estimatedSugar}g`, saved: recipe.savedDemo, href: `/recipes/${recipe.slug}` }));
const fallbackProductRanking: RankingItem[] = products.slice(0, 10).map((product) => ({ name: product.title, meta: `${product.serving} 기준 · 당류 ${product.sugar}g · ${product.calories}kcal`, saved: product.savedDemo, href: `/product/${product.slug}` }));

function toRankingItems(items: HomeProductItem[], personalized: boolean): RankingItem[] {
  return items.map((item, index) => {
    const catalogItem = products.find((product) => product.title.trim() === item.name.trim());
    return {
      name: item.name,
      meta: [item.brand, personalized ? "관심 기준에 맞춘 추천" : "많이 찾는 식품"].filter(Boolean).join(" · "),
      saved: item.rank ?? index + 1,
      href: catalogItem ? `/product/${catalogItem.slug}` : `/search?query=${encodeURIComponent(item.name)}`,
    };
  });
}

const readingList = [
  { category: "성분 읽기", title: "제로슈거인데 당류가 0g이 아닐 수 있나요?", copy: "표시 문구와 영양성분표를 함께 봐야 하는 이유를 알아봐요.", time: "3분" },
  { category: "감미료", title: "알룰로스와 에리스리톨은 무엇이 다를까요?", copy: "자주 쓰이는 대체 감미료의 특징을 쉬운 말로 정리했어요.", time: "4분" },
  { category: "식단 기록", title: "간식을 끊지 않고 당류를 줄이는 방법", copy: "먹는 시간을 바꾸고 양을 기록하는 작은 습관부터 시작해요.", time: "3분" },
  { category: "처음 읽기", title: "영양성분표는 이 세 줄부터 보면 쉬워요", copy: "열량, 당류, 1회 제공량을 순서대로 확인해보세요.", time: "2분" },
] as const;

function percent(value: number, max: number) {
  return Math.min(100, Math.round((value / max) * 100));
}

function roundSugar(value: number) {
  return Math.round((value + Number.EPSILON) * 100) / 100;
}

function sugarText(value: number) {
  return new Intl.NumberFormat("ko-KR", { maximumFractionDigits: 2 }).format(roundSugar(value));
}

function MealSymbol({ meal }: { meal: MealType }) {
  if (meal === "아침") {
    return (
      <svg viewBox="0 0 48 48" aria-hidden="true">
        <path className="meal-symbol-sun" d="M16 29a8 8 0 0 1 16 0" />
        <path d="M10 31h28M13 36h22M24 12v5M11 20l4 3M37 20l-4 3" />
      </svg>
    );
  }

  if (meal === "점심") {
    return (
      <svg viewBox="0 0 48 48" aria-hidden="true">
        <circle className="meal-symbol-sun" cx="24" cy="24" r="8" />
        <path d="M24 9v5M24 34v5M9 24h5M34 24h5M13.5 13.5l3.5 3.5M31 31l3.5 3.5M34.5 13.5 31 17M17 31l-3.5 3.5" />
      </svg>
    );
  }

  if (meal === "저녁") {
    return (
      <svg viewBox="0 0 48 48" aria-hidden="true">
        <path className="meal-symbol-moon" d="M30.5 10.5A14 14 0 1 0 38 33a13 13 0 0 1-7.5-22.5Z" />
        <path className="meal-symbol-cloud" d="M12 34.5h21a5 5 0 0 0 .4-10 8 8 0 0 0-15-1.5 6 6 0 0 0-6.4 11.5Z" />
      </svg>
    );
  }

  return (
    <svg viewBox="0 0 48 48" aria-hidden="true">
      <path className="meal-symbol-leaf" d="M25 14c3-5 8-6 11-4-1 5-5 8-11 7" />
      <path className="meal-symbol-apple" d="M24 17c-4-4-13-2-14 8-1 9 6 15 14 12 8 3 15-3 14-12-1-10-10-12-14-8Z" />
      <path d="M24 17c0-4 1-6 3-8" />
    </svg>
  );
}

export function HomeDashboard() {
  const { ready: authReady, signedIn, token } = useAuthSession();
  const remoteGauge = useDailyGauge(token);
  const { recordsByDate, loadServerMonth } = useDietRecords();
  const { goals } = useUserSettings();
  const todayKey = useMemo(() => getTodayKey(), []);
  const [activeMeal, setActiveMeal] = useState<MealType | null>(null);
  const [showAllRanking, setShowAllRanking] = useState(false);
  const [feedback, setFeedback] = useState("");
  const [productRanking, setProductRanking] = useState<RankingItem[]>(fallbackProductRanking);
  const [productPanelTitle, setProductPanelTitle] = useState("식품 TOP");

  useEffect(() => {
    const today = keyToDate(todayKey);
    void loadServerMonth(today.getFullYear(), today.getMonth() + 1);
  }, [loadServerMonth, todayKey]);

  useEffect(() => {
    let active = true;
    const rankRequest = withMockFallback(() => getProductRanking(), { listProducts: [] });
    const recommendRequest = token
      ? withMockFallback(() => getUserRecommendations(token), { listProducts: [] })
      : Promise.resolve({ listProducts: [] });

    Promise.all([rankRequest, recommendRequest]).then(([rank, recommend]) => {
      if (!active) return;
      if (token && recommend.listProducts.length > 0) {
        setProductRanking(toRankingItems(recommend.listProducts, true));
        setProductPanelTitle("맞춤 식품");
        return;
      }
      if (rank.listProducts.length > 0) {
        setProductRanking(toRankingItems(rank.listProducts, false));
        setProductPanelTitle("식품 TOP");
        return;
      }
      setProductRanking(fallbackProductRanking);
      setProductPanelTitle("식품 TOP");
    });

    return () => {
      active = false;
    };
  }, [token]);

  const todayRecords = recordsByDate[todayKey] ?? [];
  const entries = useMemo(() => Object.fromEntries(meals.map((meal) => [
    meal,
    todayRecords.filter((item) => item.meal === meal),
  ])) as Record<MealType, DietRecord[]>, [todayRecords]);

  const localTotals = useMemo(() => {
    const result = todayRecords.filter((item) => item.source !== "server").reduce((sum, item) => ({
      sugar: sum.sugar + item.sugar,
      calories: sum.calories + item.calories,
    }), { sugar: 0, calories: 0 });

    return { ...result, sugar: roundSugar(result.sugar) };
  }, [todayRecords]);

  const totals = {
    sugar: roundSugar(localTotals.sugar + Number(remoteGauge?.sugar ?? 0)),
    calories: localTotals.calories + Number(remoteGauge?.cal ?? 0),
  };
  const sugarGoal = signedIn
    ? Number(remoteGauge?.sugarTarget ?? remoteGauge?.sugar_target ?? goals.sugar)
    : 50;
  const calorieGoal = signedIn
    ? Number(remoteGauge?.calorieTarget ?? remoteGauge?.cal_target ?? goals.calories)
    : 2000;
  const sugarRate = percent(totals.sugar, sugarGoal);
  const calorieRate = percent(totals.calories, calorieGoal);
  const state = sugarRate < 65 ? "roomy" : sugarRate < 100 ? "near" : "over";
  const stateCopy = state === "roomy" ? "오늘은 아직 여유가 있어요" : state === "near" ? "오늘 목표에 거의 닿았어요" : "오늘 목표를 조금 넘었어요";

  function openMeal(meal: MealType) {
    setActiveMeal(meal);
  }

  function handleSaved(dateKey: string, record: DietRecord) {
    const date = keyToDate(dateKey);
    const dateLabel = dateKey === todayKey ? "오늘" : `${date.getMonth() + 1}월 ${date.getDate()}일`;
    const currentSugar = (recordsByDate[dateKey] ?? []).reduce((sum, item) => sum + item.sugar, 0);
    const nextSugar = roundSugar(currentSugar + record.sugar);
    setFeedback(`${record.name}을 ${dateLabel} ${record.meal}에 저장했어요. ${nextSugar <= sugarGoal ? `목표까지 ${sugarText(sugarGoal - nextSugar)}g 남았어요.` : "목표보다 조금 높아요. 다음 식사는 당류가 낮은 메뉴를 골라도 좋아요."}`);
  }

  const today = keyToDate(todayKey);
  const todayLabel = `${today.getMonth() + 1}월 ${today.getDate()}일 ${["일", "월", "화", "수", "목", "금", "토"][today.getDay()]}요일`;

  return (
    <main className="home-dashboard">
      <ServiceBanner />

      {authReady && !signedIn && (
        <aside className="guest-preview-notice wrap" aria-label="로그인 전 미리보기 안내">
          <div><span>로그인 전 미리보기</span><p>기본 기록으로 하루 화면을 보여드리고 있어요. 로그인하면 내 목표와 식단으로 바뀌어요.</p></div>
          <Link href="/login">로그인하고 내 기록 보기</Link>
        </aside>
      )}

      <section className="today-character wrap">
        <div className={`today-sugar-character state-${state}`} role="img" aria-label={stateCopy} />
        <div className="today-character-copy">
          <p className="day-label">{todayLabel} · {signedIn ? "나의 오늘" : "오늘의 미리보기"}</p>
          <h1>{stateCopy}</h1>
          <p>식사를 기록할 때마다 설탕이와 오늘 수치가 바로 바뀌어요.</p>
        </div>
      </section>

      <section className="day-board wrap" id="today-board" aria-labelledby="day-board-title">
        <div className="day-numbers">
          <div className="day-board-heading">
            <p className="eyebrow">오늘의 기록</p>
            <h2 id="day-board-title">오늘 먹은 양을 확인해요</h2>
          </div>

          <div className="number-metric">
            <div className="metric-heading"><div><span>당류</span><p>{signedIn ? "설정한" : "기본"} 하루 목표 {sugarText(sugarGoal)}g</p></div><strong>{sugarText(totals.sugar)}<small>g</small></strong></div>
            <div className="metric-bar"><i style={{ clipPath: `inset(0 ${100 - sugarRate}% 0 0)` }} /></div>
            <small>{sugarRate < 100 ? `${sugarText(sugarGoal - totals.sugar)}g 남음` : `${sugarText(totals.sugar - sugarGoal)}g 초과`}</small>
          </div>

          <div className="number-metric calorie">
            <div className="metric-heading"><div><span>칼로리</span><p>{signedIn ? "설정한" : "기본"} 하루 목표 {calorieGoal.toLocaleString()}kcal</p></div><strong>{totals.calories.toLocaleString()}<small>kcal</small></strong></div>
            <div className="metric-bar"><i style={{ clipPath: `inset(0 ${100 - calorieRate}% 0 0)` }} /></div>
            <small>{totals.calories <= calorieGoal ? `${(calorieGoal - totals.calories).toLocaleString()}kcal 남음` : `${(totals.calories - calorieGoal).toLocaleString()}kcal 초과`}</small>
          </div>

          <p className="today-comment">{feedback || (state === "over" ? `설정한 목표보다 ${sugarText(totals.sugar - sugarGoal)}g 높아요.` : `설정한 목표까지 ${sugarText(Math.max(0, sugarGoal - totals.sugar))}g 남았어요.`)}</p>
        </div>

        <div className="meal-slots">
          <div className="meal-slots-heading"><div><p className="eyebrow">식사별 기록</p><h2>기록할 식사를 골라주세요</h2></div><span>누르면 바로 추가할 수 있어요</span></div>
          <div className="meal-slot-grid">
            {meals.map((meal) => (
              <button type="button" className="meal-slot" key={meal} onClick={() => openMeal(meal)} aria-label={`${meal} 기록 열기`}>
                <div className={`meal-slot-icon meal-${meal}`}><MealSymbol meal={meal} /><i aria-hidden="true">＋</i></div>
                <div className="meal-slot-name"><span>{meal}</span></div>
                <div className="meal-slot-copy"><strong>{entries[meal].map((item) => item.name).join(" · ") || "아직 기록이 없어요"}</strong><small>당류 {sugarText(entries[meal].reduce((sum, item) => sum + item.sugar, 0))}g · {entries[meal].reduce((sum, item) => sum + item.calories, 0)}kcal</small></div>
              </button>
            ))}
          </div>
        </div>
      </section>

      <Link className="home-thin-banner" href="/diet">
        <span>{stateCopy} 기록 흐름을 캘린더에서 이어서 볼 수 있어요.</span><b>캘린더에서 흐름 보기 →</b>
      </Link>

      <section className="ranking-section wrap">
        <header className="section-line-heading"><div><p className="eyebrow">많이 찾는 메뉴</p><h2>인기 레시피와 식품</h2></div><p>사용자들이 자주 살펴본 메뉴를 순서대로 모았어요.</p></header>
        <div className="ranking-columns">
          {[["레시피 TOP", recipeRanking, "/recipes"], [productPanelTitle, productRanking, "/search"]].map(([title, list, href]) => (
            <article className="ranking-panel" key={title as string}>
              <header><h3>{title as string}</h3><Link href={href as string}>전체 보기 ↗</Link></header>
              <ol>
                {(list as RankingItem[]).slice(0, showAllRanking ? 10 : 5).map((item, index) => (
                  <li key={item.name}>
                    <Link href={item.href}>
                      <span className="ranking-number">{String(index + 1).padStart(2, "0")}</span>
                      <span className="ranking-copy"><strong>{item.name}</strong><small>{item.meta}</small></span>
                    </Link>
                  </li>
                ))}
              </ol>
            </article>
          ))}
        </div>
        <button type="button" className="ranking-more" onClick={() => setShowAllRanking((current) => !current)} aria-expanded={showAllRanking}>{showAllRanking ? "5위까지만 보기" : "10위까지 보기"}<span aria-hidden="true">{showAllRanking ? "↑" : "↓"}</span></button>
      </section>

      <section className="reading-section wrap">
        <header className="section-line-heading"><div><p className="eyebrow">당당 읽을거리</p><h2>알아두면 선택이 쉬워지는 이야기</h2></div><p>성분과 식단을 이해하는 데 필요한 내용만 짧게 정리했어요.</p></header>
        <div className="reading-grid">
          {readingList.map((item, index) => (
            <article className={`reading-card tone-${index + 1}`} key={item.title}>
              <div className="reading-card-cover"><span>{item.category}</span><b>{String(index + 1).padStart(2, "0")}</b></div>
              <div className="reading-card-copy"><small>{item.time} 읽기</small><h3>{item.title}</h3><p>{item.copy}</p></div>
            </article>
          ))}
        </div>
      </section>

      {activeMeal && (
        <RecordMealModal
          meal={activeMeal}
          initialDate={todayKey}
          existingRecordsByDate={recordsByDate}
          onClose={() => setActiveMeal(null)}
          onSaved={handleSaved}
        />
      )}
    </main>
  );
}
