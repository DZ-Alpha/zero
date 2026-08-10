"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { RecordMealModal } from "@/components/RecordMealModal";
import { SafeImage } from "@/components/SafeImage";
import { LoginPromptDialog } from "@/components/SystemFeedback";
import { products, recipes } from "@/data/catalog";
import { mockRoomsHome } from "@/data/mockRooms";
import { featuredReadingArticles, getReadingArticle } from "@/data/reading";
import { useAuthSession } from "@/hooks/useAuthSession";
import { useDailyGauge } from "@/hooks/useDailyGauge";
import { DietRecord, getTodayKey, keyToDate, MealType, useDietRecords } from "@/hooks/useDietRecords";
import { useUserSettings } from "@/hooks/useUserSettings";
import { withMockFallback } from "@/lib/api/client";
import { getRoomsHome } from "@/lib/api/rooms";
import {
  getRecipeSwapRanking,
  getHomeArticles,
  getUserRecommendations,
  searchProducts,
  HomeArticleItem,
  HomeProductItem,
  HomeRecipeRankingItem,
} from "@/lib/api/zerocheck";
import { RoomsHomeResponse } from "@/lib/rooms/contracts";

type RankingItem = {
  name: string;
  meta: string;
  metric?: string;
  href: string;
  image?: string | null;
  symbol?: string;
};

type ProductSignalMode = "personalized" | "general" | "guest" | "preview";

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

const fallbackRecipeRanking: RankingItem[] = recipes.map((recipe) => ({
  name: recipe.title,
  meta: `등록 재료 당류 ${sugarText(recipe.estimatedSugar)}g · ${recipe.time}`,
  href: `/recipes/${recipe.slug}`,
  image: recipe.thumbnail,
}));
const fallbackProductRanking: RankingItem[] = products.slice(0, 10).map((product) => ({
  name: product.title,
  meta: `${product.serving} 기준 · 당류 ${product.sugar}g`,
  metric: `${product.calories}kcal`,
  href: `/product/${product.slug}`,
  image: product.image,
}));

const emptyRoomsHome: RoomsHomeResponse = {
  rooms: [],
  recentActivities: [],
  todayActivities: [],
  weeklyRanking: [],
  activeTeamCount: 0,
  maxRoomCount: 3,
  recentActivitiesNextCursor: null,
  weeklyRankingNextCursor: null,
  incomingNudges: [],
};

function toRoomRanking(weeklyRanking: RoomsHomeResponse["weeklyRanking"]): RankingItem[] {
  return weeklyRanking.map((room) => ({
    name: room.name,
    meta: `멤버 ${room.memberCount}명 · 평균 당류 ${room.averageSugar}g`,
    metric: `기록률 ${room.recordRate}%`,
    href: room.isMine ? `/rooms/${room.id}` : "/rooms",
    symbol: room.emoji,
  }));
}

function toRankingItems(items: HomeProductItem[], personalized: boolean): RankingItem[] {
  return items.map((item) => {
    // item.id(실제 상품 ID)가 있으면 그걸로 바로 상세 페이지로 보낸다 - 예전엔
    // 이름으로 로컬 목업 카탈로그를 매칭해야만 상세로 갔고, 실서버 상품 대부분은
    // 매칭이 안 돼 검색 페이지로만 보내졌다(2026-07-31 리포트 - 상세로 가야 함).
    const catalogItem = products.find((product) => product.title.trim() === item.name.trim());
    const productKey = item.id ?? catalogItem?.slug;
    return {
      name: item.name,
      meta: [item.brand, personalized ? "관심 기준과 일치" : "전체 제품에서 보기"].filter(Boolean).join(" · "),
      metric: personalized ? "내 기준" : undefined,
      href: productKey ? `/product/${productKey}` : `/search?query=${encodeURIComponent(item.name)}`,
      image: item.image,
    };
  });
}

function toRecipeRankingItems(items: HomeRecipeRankingItem[]): RankingItem[] {
  return items.map((item) => ({
    name: item.name,
    meta:
      item.baseSugarG != null && item.totalSugarG != null
        ? `당류 ${sugarText(item.baseSugarG)}g → ${sugarText(item.totalSugarG)}g`
        : "등록 재료 기준으로 비교했어요",
    metric: `${sugarText(item.sugarReductionPct)}% 감소`,
    href: `/recipes/${item.id}`,
    image: item.image,
  }));
}

function SignalList({ items, emptyMessage }: { items: RankingItem[]; emptyMessage: string }) {
  if (items.length === 0) {
    return <p className="home-signal-empty">{emptyMessage}</p>;
  }

  return (
    <ul className="home-signal-list">
      {items.slice(0, 3).map((item) => (
        <li key={`${item.href}-${item.name}`}>
          <Link href={item.href}>
            <span className={`home-signal-visual${item.image ? " has-image" : ""}`} aria-hidden={!item.image}>
              {item.image ? <SafeImage src={item.image} alt="" fallbackLabel={item.symbol ?? "당"} /> : <b>{item.symbol ?? "당"}</b>}
            </span>
            <span className="home-signal-copy">
              <strong>{item.name}</strong>
              <small>{item.meta}</small>
            </span>
            {item.metric ? <em>{item.metric}</em> : null}
            <i aria-hidden="true">→</i>
          </Link>
        </li>
      ))}
    </ul>
  );
}

type ReadingItem = { slug?: string; category: string; title: string; copy: string; time: string; cover: string; coverCaption: string };

const fallbackReadingList: ReadingItem[] = featuredReadingArticles.map((article) => ({
  slug: article.slug,
  category: article.category,
  title: article.title,
  copy: article.summary,
  time: `${article.readMinutes}분`,
  cover: article.cover,
  coverCaption: article.coverCaption,
}));

function toReadingItems(items: HomeArticleItem[]): ReadingItem[] {
  return items.map((item) => {
    const editorial = getReadingArticle(item.slug);
    return {
      slug: item.slug,
      category: item.category,
      title: item.title,
      copy: item.summary ?? editorial?.summary ?? "본문에서 자세한 내용을 확인해보세요.",
      time: item.readMinutes ? `${item.readMinutes}분` : editorial ? `${editorial.readMinutes}분` : "짧게",
      cover: editorial?.cover ?? "한눈에 읽기",
      coverCaption: editorial?.coverCaption ?? "선택 전에 알아둘 핵심",
    };
  });
}

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

// 홈 화면은 로그인·목업 상태를 같은 흐름에서 다뤄 웹과 모바일을 함께 유지한다.
export function HomeDashboard() {
  const { ready: authReady, signedIn, token, isMockSession } = useAuthSession();
  const remoteGauge = useDailyGauge(token);
  const { recordsByDate, loadServerMonth } = useDietRecords();
  const { goals } = useUserSettings();
  const todayKey = useMemo(() => getTodayKey(), []);
  const [activeMeal, setActiveMeal] = useState<MealType | null>(null);
  const [loginPrompt, setLoginPrompt] = useState(false);
  const [feedback, setFeedback] = useState("");
  const [readingList, setReadingList] = useState<ReadingItem[]>(fallbackReadingList);
  const [recipeRanking, setRecipeRanking] = useState<RankingItem[]>(isMockSession ? fallbackRecipeRanking : []);
  const [productRanking, setProductRanking] = useState<RankingItem[]>(isMockSession ? fallbackProductRanking : []);
  const [productSignalMode, setProductSignalMode] = useState<ProductSignalMode>(isMockSession ? "preview" : "guest");
  const [roomsHome, setRoomsHome] = useState<RoomsHomeResponse>(isMockSession ? mockRoomsHome : emptyRoomsHome);
  const [nudgeToast, setNudgeToast] = useState("");
  const [seenActivityMap, setSeenActivityMap] = useState<Record<string, string | null>>({});
  const [dismissedNudgeKey, setDismissedNudgeKey] = useState<string | null>(null);
  const [dismissedEmptyKey, setDismissedEmptyKey] = useState<string | null>(null);

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

    if (isMockSession) {
      setRecipeRanking(fallbackRecipeRanking);
      setProductRanking(fallbackProductRanking);
      setProductSignalMode("preview");
      return () => {
        active = false;
      };
    }

    const rankRequest = withMockFallback(
      () => getRecipeSwapRanking(),
      { status: "PREPARING", listRecipes: [], listProducts: [] },
    );
    const recommendRequest = token
      ? withMockFallback(() => getUserRecommendations(token), {
          listProducts: [],
          personalized: false,
          matchedPreferenceIds: [],
          reason: "NO_PREFERENCES" as const,
        })
      : withMockFallback(
          () => searchProducts({ sort: "rank", page: 1 }).then((result) => ({
            listProducts: result.items.slice(0, 10).map((item) => ({ id: item.id, name: item.name, brand: item.brand, image: item.image })),
            personalized: false,
            matchedPreferenceIds: [],
            reason: "NO_PREFERENCES" as const,
          })),
          { listProducts: [], personalized: false, matchedPreferenceIds: [], reason: "NO_PREFERENCES" as const },
        );

    Promise.all([rankRequest, recommendRequest]).then(([rank, recommend]) => {
      if (!active) return;
      setRecipeRanking(
        rank.listRecipes.length > 0
          ? toRecipeRankingItems(rank.listRecipes)
          : [],
      );
      if (recommend.listProducts.length > 0) {
        setProductRanking(toRankingItems(recommend.listProducts, recommend.personalized));
        setProductSignalMode(recommend.personalized ? "personalized" : token ? "general" : "guest");
        return;
      }
      // 로그인 전에는 추천 근거가 없어 목록이 비기 쉽다 - 그때만 카탈로그로 채워
      // 둘러볼 거리를 남긴다. 로그인 사용자는 서버 추천 결과를 그대로 따른다.
      setProductRanking(token ? [] : fallbackProductRanking);
      setProductSignalMode(token ? "general" : "guest");
    });

    return () => {
      active = false;
    };
  }, [isMockSession, token]);

  useEffect(() => {
    let active = true;
    withMockFallback(() => getHomeArticles(4), { articles: [] }).then(({ articles }) => {
      if (!active) return;
      setReadingList(articles.length > 0 ? toReadingItems(articles) : fallbackReadingList);
    });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (isMockSession) {
      setRoomsHome(mockRoomsHome);
      return;
    }
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
  }, [isMockSession, token]);

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
  // recentActivities는 "다른 멤버가 새로 올렸는지" 알림용이라 내 기록은 빠져
  // 있다 - "새 사진 알림" 배지엔 계속 이걸 쓰지만, 오늘 실제로 누가 기록했는지
  // (나 포함) 보여줘야 하는 아바타/사진 미리보기/"아무도 없어요" 문구는
  // todayActivities(내 기록 포함)를 써야 한다. 안 그러면 오늘 나 혼자만
  // 기록한 방에서 "오늘 아무도 등록하지 않았어요"라고 잘못 뜬다(2026-07-31 리포트).
  const myRoomActivities = myRoom
    ? roomsHome.recentActivities.filter((activity) => activity.roomId === myRoom.id).slice(0, 4)
    : [];
  const myRoomTodayActivities = myRoom
    ? roomsHome.todayActivities.filter((activity) => activity.roomId === myRoom.id).slice(0, 4)
    : [];
  // 사진 갤러리는 실제 사진이 있는 업로드만 최신순으로 보여준다 - 사진 없는
  // 기록까지 섞이면 빈 칸에 라벨만 뜬다(2026-07-31 리포트). 아바타/기록 수는
  // 사진 유무와 무관하게 myRoomTodayActivities를 그대로 쓴다.
  const myRoomTodayPhotos = myRoomTodayActivities.filter((activity) => activity.imageUrl);
  const roomRanking = toRoomRanking(roomsHome.weeklyRanking);
  const productSignalTitle = productSignalMode === "personalized"
    ? "내 기준에 맞는 저당 제품"
    : productSignalMode === "guest"
      ? "먼저 둘러볼 저당 제품"
      : productSignalMode === "preview"
        ? "내 기준에 맞는 저당 제품"
        : "먼저 둘러볼 저당 제품";
  const productSignalBasis = productSignalMode === "personalized"
    ? "관심 기준"
    : productSignalMode === "preview"
      ? "오늘 추천"
      : productSignalMode === "guest"
        ? "전체 제품"
        : "전체 목록";

  const myRooms = roomsHome.rooms;
  const myRoomIdsKey = myRooms.map((room) => room.id).join(",");
  useEffect(() => {
    const map: Record<string, string | null> = {};
    myRooms.forEach((room) => { map[room.id] = getSeenActivityId(room.id); });
    setSeenActivityMap(map);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [myRoomIdsKey]);

  // 방이 여러 개면 "새 사진" 알림도 방마다 따로 확인해야 한다 - 첫 방만 보던
  // 이전 로직은 두 번째 방부터 새 사진이 와도 알림이 안 떴다. recentActivities는
  // 서버가 이미 created_at desc로 정렬해서 주므로 방별 첫 항목이 최신 활동.
  const roomsWithNewActivity = myRooms.flatMap((room) => {
    const activities = roomsHome.recentActivities.filter((activity) => activity.roomId === room.id).slice(0, 4);
    const latest = activities[0];
    if (!latest || latest.id === seenActivityMap[room.id]) return [];
    return [{ room, activities, latestId: latest.id }];
  });
  const nudgeKey = roomsWithNewActivity.length > 0 ? roomsWithNewActivity.map((entry) => entry.latestId).sort().join(",") : null;
  const showRoomPhotoNudge = Boolean(nudgeKey && nudgeKey !== dismissedNudgeKey);

  // 등록한 방이 하나라도 오늘 기록이 있으면 "아무도 등록하지 않았어요"는 안
  // 띄운다 - "새 사진" 알림과 동시에 뜨면 서로 모순돼 보인다.
  const allRoomsEmptyToday = myRooms.length > 0 && myRooms.every((room) => !roomsHome.todayActivities.some((activity) => activity.roomId === room.id));
  const emptyKey = allRoomsEmptyToday ? myRooms.map((room) => room.id).sort().join(",") : null;
  const showNoRoomActivityNotice = Boolean(!showRoomPhotoNudge && emptyKey && emptyKey !== dismissedEmptyKey);

  return (
    <main className="home-dashboard">
      <section className="home-intro wrap" aria-labelledby="home-intro-title">
        <div className="home-intro-copy">
          <h1 id="home-intro-title">먹고 싶은 건 그대로,<br /><em>당은 더 가볍게.</em></h1>
          <p>당당이 제품과 레시피의 당류를 비교해서, 지금 먹기 좋은 선택을 찾아줄게요.</p>
        </div>
        <div className="home-intro-visual">
          <div className={`today-sugar-character state-${state}`} role="img" aria-label="당당 설탕이" />
          <span className="home-intro-bubble">{stateCopy}</span>
        </div>
      </section>


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
          {showRoomPhotoNudge && (
            <div className="today-room-nudge-wrap">
              <Link
                className="today-room-nudge"
                href={roomsWithNewActivity.length > 1 ? "/rooms" : `/rooms/${roomsWithNewActivity[0].room.id}`}
                onClick={() => {
                  const nextSeen: Record<string, string> = {};
                  roomsWithNewActivity.forEach(({ room, latestId }) => {
                    markActivitySeen(room.id, latestId);
                    nextSeen[room.id] = latestId;
                  });
                  setSeenActivityMap((prev) => ({ ...prev, ...nextSeen }));
                }}
              >
                <span className="today-room-nudge-avatars" aria-hidden="true">
                  {roomsWithNewActivity.length > 1
                    ? roomsWithNewActivity.slice(0, 3).map(({ room }) => <i key={room.id}>{room.emoji}</i>)
                    : roomsWithNewActivity[0].activities.slice(0, 3).map((activity) => <i key={activity.id}>{activity.memberAvatar}</i>)}
                </span>
                <span>
                  <strong>
                    {roomsWithNewActivity.length > 1
                      ? `${roomsWithNewActivity.map(({ room }) => room.name).join(", ")}에 새 사진이 올라왔어요`
                      : `${roomsWithNewActivity[0].room.name}에 새 사진이 올라왔어요`}
                  </strong>
                  <small>{roomsWithNewActivity.length > 1 ? "얌로그 모임 목록에서 확인해보세요" : "멤버들의 오늘 식탁 보러가기"}</small>
                </span>
                <b aria-hidden="true">→</b>
              </Link>
              <button type="button" className="today-room-nudge-close" onClick={() => nudgeKey && setDismissedNudgeKey(nudgeKey)} aria-label="닫기">×</button>
            </div>
          )}
          {showNoRoomActivityNotice && (
            <div className="today-room-nudge-wrap">
              <div className="today-room-nudge today-room-nudge-static">
                <span className="today-room-nudge-avatars" aria-hidden="true" />
                <span><strong>오늘은 아무도 등록하지 않았어요</strong><small>{myRooms.length === 1 ? `${myRooms[0].name}에서 가장 먼저 기록해보세요` : "먼저 기록해서 모임에 알려보세요"}</small></span>
              </div>
              <button type="button" className="today-room-nudge-close" onClick={() => emptyKey && setDismissedEmptyKey(emptyKey)} aria-label="닫기">×</button>
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
          <div className="meal-slots-heading">
            <div><p className="eyebrow">식사별 기록</p><h2>기록할 식사를 골라주세요</h2></div>
            <Link className="meal-flow-link" href="/diet">기록 흐름 보기 <b aria-hidden="true">→</b></Link>
          </div>
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

      {myRoom ? (
        <section className="home-room-preview wrap" aria-labelledby="home-room-title" data-preview={!signedIn ? "예시" : undefined}>
          <div className="home-room-preview-title">
            <span aria-hidden="true">{myRoom.emoji}</span>
            <div><p className="eyebrow">내 모임 · 오늘</p><h2 id="home-room-title">{myRoom.name}</h2></div>
          </div>
          <div className="home-room-preview-activity">
            <div className="home-room-avatars">{myRoomTodayActivities.map((activity) => <span key={activity.id}>{activity.memberAvatar}</span>)}</div>
            <p><strong>{myRoom.recordedTodayCount}명이 기록했어요</strong></p>
          </div>
          <div className="home-room-preview-photos" aria-label="방금 올라온 모임 식단">
            {myRoomTodayPhotos.map((activity) => (
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

      <section className="ranking-section home-signal-section wrap" aria-labelledby="home-signal-title">
        <header className="section-line-heading home-signal-heading">
          <div><p className="eyebrow">이번 주 당당 신호</p><h2 id="home-signal-title">기록하고, 바꾸고, 골라보세요</h2></div>
          <p>오늘 식사를 이어갈 다음 선택을 한곳에 모았어요. 함께 기록하고, 당류를 확인하고, 내 기준에 맞게 골라보세요.</p>
        </header>
        <div className="home-signal-board">
          <article className="home-signal-panel home-signal-room">
            <header>
              <div><small>함께 기록하기</small><h3>꾸준히 기록 중인 모임</h3></div>
              <span>최근 7일</span>
            </header>
            <p className="home-signal-intro">기록률이 높은 모임을 보며 오늘 한 끼를 함께 이어가요.</p>
            <SignalList items={roomRanking} emptyMessage={signedIn ? "이번 주 집계 조건을 충족한 모임이 아직 없어요." : "로그인하면 이번 주 모임 기록률을 볼 수 있어요."} />
            <Link className="home-signal-action" href="/rooms">모임 기록 보기 <span aria-hidden="true">→</span></Link>
          </article>

          <article className="home-signal-panel home-signal-recipe">
            <header>
              <div><small>바꿔 먹는 방법</small><h3>{isMockSession ? "당류를 확인한 레시피" : "당류를 많이 덜어낸 레시피"}</h3></div>
              <span>재료 기준</span>
            </header>
            <SignalList items={recipeRanking} emptyMessage="당류 비교가 끝난 레시피를 불러오고 있어요." />
            <Link className="home-signal-action" href="/recipes">레시피 둘러보기 <span aria-hidden="true">→</span></Link>
          </article>

          <article className="home-signal-panel home-signal-product">
            <header>
              <div><small>내 기준으로 고르기</small><h3>{productSignalTitle}</h3></div>
              <span>{productSignalBasis}</span>
            </header>
            <SignalList items={productRanking} emptyMessage="조건에 맞는 제품을 준비하고 있어요." />
            <Link className="home-signal-action" href="/search">저당 제품 찾기 <span aria-hidden="true">→</span></Link>
          </article>
        </div>
        <p className="home-signal-note">레시피 수치는 등록 재료 기준 비교이며, 제품 추천은 의료 판단이 아닌 선택 참고 정보예요.</p>
      </section>

      <section className="reading-section wrap">
        <header className="section-line-heading reading-heading"><div><p className="eyebrow">당당 읽을거리</p><h2>고를 때 바로 써먹는 기준</h2></div></header>
        <div className="reading-grid">
          {readingList.slice(0, 4).map((item, index) => (
            <Link className={`reading-card tone-${(index % 4) + 1}`} href={item.slug ? `/reading/${item.slug}` : "/search"} key={item.title}>
              <div className="reading-card-cover">
                <span>{item.category}</span>
                <strong>{item.cover}</strong>
                <small>{item.coverCaption}</small>
              </div>
              <div className="reading-card-copy">
                <h3>{item.title}</h3>
                <div className="reading-card-meta"><small>{item.time} 읽기</small><b>읽어보기 <i aria-hidden="true">→</i></b></div>
              </div>
            </Link>
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
