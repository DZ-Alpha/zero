"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { HomeAdBanner } from "@/components/HomeAdBanner";
import { RecordMealModal } from "@/components/RecordMealModal";
import { SafeImage } from "@/components/SafeImage";
import { LoginPromptDialog } from "@/components/SystemFeedback";
import { teamRanking as mockTeamRanking } from "@/components/rooms/roomData";
import { products, recipes } from "@/data/catalog";
import { useAuthSession } from "@/hooks/useAuthSession";
import { useDailyGauge } from "@/hooks/useDailyGauge";
import { DietRecord, getTodayKey, keyToDate, MealType, useDietRecords } from "@/hooks/useDietRecords";
import { useUserSettings } from "@/hooks/useUserSettings";
import { withMockFallback } from "@/lib/api/client";
import { getRoomsHome } from "@/lib/api/rooms";
import { getProductRanking, getUserRecommendations, HomeProductItem } from "@/lib/api/zerocheck";
import { RoomsHomeResponse } from "@/lib/rooms/contracts";

type RankingItem = { name: string; meta: string; saved: number; href: string };

const meals: MealType[] = ["아침", "점심", "저녁", "간식"];

const MEAL_LABELS: Record<string, string> = { breakfast: "아침", lunch: "점심", dinner: "저녁", snack: "간식" };

// "새 사진이 올라왔어요" 안내는 한 번 보면(방으로 들어가면) 지워지고, 그 뒤에
// 진짜 새로운 활동이 생겨야 다시 뜬다 - 방별 마지막으로 확인한 활동 id를
// localStorage에 남겨서 기기별로 기억한다(서버에 읽음 상태를 둘 정도의 기능은
// 아니라고 판단).
const ROOM_NUDGE_SEEN_KEY = "room_nudge_seen_activity";

function getSeenActivityId(roomId: string): string | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(ROOM_NUDGE_SEEN_KEY);
    if (!raw) return null;
    return (JSON.parse(raw) as Record<string, string>)[roomId] ?? null;
  } catch {
    return null;
  }
}

function markActivitySeen(roomId: string, activityId: string) {
  if (typeof window === "undefined") return;
  try {
    const raw = window.localStorage.getItem(ROOM_NUDGE_SEEN_KEY);
    const map = raw ? (JSON.parse(raw) as Record<string, string>) : {};
    map[roomId] = activityId;
    window.localStorage.setItem(ROOM_NUDGE_SEEN_KEY, JSON.stringify(map));
  } catch {
    // localStorage를 못 쓰는 환경 - 그냥 매번 안내가 뜨는 정도로만 열화된다.
  }
}

const recipeRanking: RankingItem[] = recipes.map((recipe) => ({ name: recipe.title, meta: `${recipe.time} · 등록 재료 당류 ${recipe.estimatedSugar}g`, saved: recipe.savedDemo, href: `/recipes/${recipe.slug}` }));
const fallbackProductRanking: RankingItem[] = products.slice(0, 10).map((product) => ({ name: product.title, meta: `${product.serving} 기준 · 당류 ${product.sugar}g · ${product.calories}kcal`, saved: product.savedDemo, href: `/product/${product.slug}` }));
// 실제 랭킹 참여 조건(멤버 3명+·개설 7일+)을 만족하는 방이 아직 없으면
// weeklyRanking이 통째로 빈 배열로 온다 - 그렇다고 카드를 비워두면 안
// 만들어진 기능처럼 보이니, 저당픽 랭킹과 같은 패턴으로 목업을 채워둔다.
const fallbackRoomRanking: RankingItem[] = mockTeamRanking.slice(0, 3).map((team, index) => ({
  name: team.name,
  meta: `멤버 ${team.members}명 · 기록률 ${team.recordRate}% · 평균 당류 ${team.averageSugar}g`,
  saved: index + 1,
  href: "/rooms",
}));
const emptyRoomsHome: RoomsHomeResponse = {
  rooms: [],
  recentActivities: [],
  weeklyRanking: [],
  activeTeamCount: 0,
  maxRoomCount: 3,
  recentActivitiesNextCursor: null,
  weeklyRankingNextCursor: null,
  incomingNudges: [],
};

function toRoomRanking(weeklyRanking: RoomsHomeResponse["weeklyRanking"]): RankingItem[] {
  return weeklyRanking.map((room, index) => ({
    name: room.name,
    meta: `멤버 ${room.memberCount}명 · 기록률 ${room.recordRate}% · 평균 당류 ${room.averageSugar}g`,
    saved: index + 1,
    href: room.isMine ? `/rooms/${room.id}` : "/rooms",
  }));
}

function toRankingItems(items: HomeProductItem[], personalized: boolean): RankingItem[] {
  return items.map((item, index) => {
    const catalogItem = products.find((product) => product.title.trim() === item.name.trim());
    return {
      name: item.name,
      meta: [item.brand, personalized ? "관심 기준에 맞춘 추천" : "많이 찾는 저당픽"].filter(Boolean).join(" · "),
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
  const [loginPrompt, setLoginPrompt] = useState(false);
  const [feedback, setFeedback] = useState("");
  const [productRanking, setProductRanking] = useState<RankingItem[]>(fallbackProductRanking);
  const [productPanelTitle, setProductPanelTitle] = useState("저당픽 TOP");
  const [roomsHome, setRoomsHome] = useState<RoomsHomeResponse>(emptyRoomsHome);
  const [nudgeToast, setNudgeToast] = useState("");
  const [seenActivityId, setSeenActivityId] = useState<string | null>(null);

  useEffect(() => {
    if (!nudgeToast) return;
    const timer = window.setTimeout(() => setNudgeToast(""), 2200);
    return () => window.clearTimeout(timer);
  }, [nudgeToast]);

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
        setProductPanelTitle("맞춤 저당픽");
        return;
      }
      if (rank.listProducts.length > 0) {
        setProductRanking(toRankingItems(rank.listProducts, false));
        setProductPanelTitle("저당픽 TOP");
        return;
      }
      setProductRanking(fallbackProductRanking);
      setProductPanelTitle("저당픽 TOP");
    });

    return () => {
      active = false;
    };
  }, [token]);

  useEffect(() => {
    if (!token) {
      setRoomsHome(emptyRoomsHome);
      return;
    }
    let active = true;
    withMockFallback(() => getRoomsHome(token), emptyRoomsHome).then((response) => {
      if (!active) return;
      setRoomsHome(response);
      if (response.incomingNudges.length > 0) {
        const [first, ...rest] = response.incomingNudges;
        setNudgeToast(
          rest.length > 0
            ? `${first.senderName}님 외 ${rest.length}명이 콕 찔렀어요.`
            : `${first.senderName}님이 ${MEAL_LABELS[first.mealType]} 기록을 콕 찔렀어요.`,
        );
      }
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
    if (!authReady) return;
    if (!signedIn) {
      setLoginPrompt(true);
      return;
    }
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
  const myRoom = roomsHome.rooms[0] ?? null;
  const myRoomActivities = myRoom
    ? roomsHome.recentActivities.filter((activity) => activity.roomId === myRoom.id).slice(0, 4)
    : [];
  const roomRanking = roomsHome.weeklyRanking.length > 0 ? toRoomRanking(roomsHome.weeklyRanking) : fallbackRoomRanking;

  useEffect(() => {
    setSeenActivityId(myRoom ? getSeenActivityId(myRoom.id) : null);
  }, [myRoom?.id]);

  // recentActivities는 서버가 이미 created_at desc로 정렬해서 준다 - 배열의
  // 첫 항목이 가장 최근 활동.
  const latestRoomActivityId = myRoomActivities[0]?.id ?? null;
  const showRoomPhotoNudge = Boolean(myRoom && latestRoomActivityId && latestRoomActivityId !== seenActivityId);
  const showNoRoomActivityNotice = Boolean(myRoom && myRoomActivities.length === 0);

  return (
    <main className="home-dashboard">
      {authReady && !signedIn && (
        <aside className="guest-preview-notice wrap" aria-label="로그인 전 미리보기 안내">
          <div><span>예시 화면</span><p>내 기록은 로그인 후 보여요.</p></div>
          <Link href="/login">로그인하기</Link>
        </aside>
      )}

      <section className="today-character wrap">
        <div className={`today-sugar-character state-${state}`} role="img" aria-label={stateCopy} />
        <div className="today-character-copy">
          <p className="day-label">{todayLabel} · {signedIn ? "나의 오늘" : "오늘의 미리보기"}</p>
          <h1>{stateCopy}</h1>
          {showRoomPhotoNudge && myRoom && (
            <Link
              className="today-room-nudge"
              href={`/rooms/${myRoom.id}`}
              onClick={() => {
                if (!latestRoomActivityId) return;
                markActivitySeen(myRoom.id, latestRoomActivityId);
                setSeenActivityId(latestRoomActivityId);
              }}
            >
              <span className="today-room-nudge-avatars" aria-hidden="true">
                {myRoomActivities.slice(0, 3).map((activity) => <i key={activity.id}>{activity.memberAvatar}</i>)}
              </span>
              <span><strong>{myRoom.name}에 새 사진이 올라왔어요</strong><small>멤버들의 오늘 식탁 보러가기</small></span>
              <b aria-hidden="true">→</b>
            </Link>
          )}
          {showNoRoomActivityNotice && myRoom && (
            <div className="today-room-nudge today-room-nudge-static">
              <span className="today-room-nudge-avatars" aria-hidden="true" />
              <span><strong>오늘은 아무도 등록하지 않았어요</strong><small>{myRoom.name}에서 가장 먼저 기록해보세요</small></span>
            </div>
          )}
        </div>
      </section>

      <section className="day-board wrap" id="today-board" aria-labelledby="day-board-title" data-preview={!signedIn ? "예시" : undefined}>
        <div className="day-numbers">
          <div className="day-board-heading">
            <p className="eyebrow">오늘의 기록</p>
            <h2 id="day-board-title">오늘 먹은 양을 확인해요</h2>
          </div>

          <div className="number-metric">
            <div className="metric-heading"><span>당류</span><strong>{sugarText(totals.sugar)}<small>g</small></strong></div>
            <div className="metric-bar"><i style={{ clipPath: `inset(0 ${100 - sugarRate}% 0 0)` }} /></div>
            <small>하루 목표 {sugarText(sugarGoal)}g</small>
          </div>

          <div className="number-metric calorie">
            <div className="metric-heading"><span>칼로리</span><strong>{totals.calories.toLocaleString()}<small>kcal</small></strong></div>
            <div className="metric-bar"><i style={{ clipPath: `inset(0 ${100 - calorieRate}% 0 0)` }} /></div>
            <small>하루 목표 {calorieGoal.toLocaleString()}kcal</small>
          </div>

          {feedback && <p className="today-comment">{feedback}</p>}
        </div>

        <div className="meal-slots">
          <div className="meal-slots-heading"><div><p className="eyebrow">식사별 기록</p><h2>기록할 식사를 골라주세요</h2></div></div>
          <div className="meal-slot-grid">
            {meals.map((meal) => (
              <button type="button" className="meal-slot" data-meal={meal} key={meal} onClick={() => openMeal(meal)} aria-label={`${meal} 기록 열기`}>
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

      {myRoom ? (
        <section className="home-room-preview wrap" aria-labelledby="home-room-title" data-preview={!signedIn ? "예시" : undefined}>
          <div className="home-room-preview-title">
            <span aria-hidden="true">{myRoom.emoji}</span>
            <div><p className="eyebrow">내 모임 · 오늘</p><h2 id="home-room-title">{myRoom.name}</h2></div>
          </div>
          <div className="home-room-preview-activity">
            <div className="home-room-avatars">{myRoomActivities.map((activity) => <span key={activity.id}>{activity.memberAvatar}</span>)}</div>
            <p><strong>{myRoom.recordedTodayCount}명이 기록했어요</strong></p>
          </div>
          <div className="home-room-preview-photos" aria-label="방금 올라온 모임 식단">
            {myRoomActivities.map((activity) => (
              <span key={activity.id}>
                <SafeImage src={activity.imageUrl} alt="" fallbackLabel={MEAL_LABELS[activity.mealType]} />
                <i>{activity.memberAvatar}</i>
              </span>
            ))}
          </div>
          <div className="home-room-preview-stats">
            <span><small>기록률</small><strong>{myRoom.monthlyRecordRate}%</strong></span>
            <span><small>팀 평균 당류</small><strong>{myRoom.averageSugar}g</strong></span>
          </div>
          <Link href={`/rooms/${myRoom.id}`}>모임 기록 보기 →</Link>
        </section>
      ) : signedIn ? (
        <section className="home-room-preview wrap" aria-labelledby="home-room-title">
          <div className="home-room-preview-title">
            <span aria-hidden="true">🍽️</span>
            <div><p className="eyebrow">얌로그</p><h2 id="home-room-title">아직 참여한 모임이 없어요</h2></div>
          </div>
          <Link href="/rooms">모임 만들거나 참여하기 →</Link>
        </section>
      ) : null}

      <HomeAdBanner />

      <section className="ranking-section home-ranking-three wrap">
        <header className="section-line-heading"><div><p className="eyebrow">이번 주 랭킹</p><h2>지금 인기 있는 모임과 메뉴</h2></div></header>
        <div className="ranking-columns">
          {[["모임", roomRanking, "/rooms", "👥"], ["레시피", recipeRanking, "/recipes", "🥗"], [productPanelTitle.replace(" TOP", ""), productRanking, "/search", "🛒"]].map(([title, list, href, icon]) => (
            <article className="ranking-panel" key={title as string}>
              <header>
                <div className="ranking-panel-heading"><span aria-hidden="true">{icon as string}</span><div><small>이번 주 TOP 3</small><h3>{title as string}</h3></div></div>
                <Link href={href as string}>전체 순위</Link>
              </header>
              <ol>
                {(list as RankingItem[]).slice(0, 3).map((item, index) => (
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
      </section>

      <section className="reading-section wrap">
        <header className="section-line-heading"><div><p className="eyebrow">당당 읽을거리</p><h2>알아두면 선택이 쉬워지는 이야기</h2></div></header>
        <div className="reading-grid">
          {readingList.slice(0, 2).map((item, index) => (
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
      {loginPrompt && <LoginPromptDialog onClose={() => setLoginPrompt(false)} />}
      {nudgeToast && <div className="home-toast" role="status">{nudgeToast}</div>}
    </main>
  );
}
