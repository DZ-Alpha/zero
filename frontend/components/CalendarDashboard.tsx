"use client";

import { useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import { RecordMealModal } from "@/components/RecordMealModal";
import { useAuthSession } from "@/hooks/useAuthSession";
import { DietRecord, getTodayKey, MealType, useDietRecords } from "@/hooks/useDietRecords";
import { useUserSettings } from "@/hooks/useUserSettings";

// 서버 기록이 도착하기 전에는 recordedDays가 0이라 "첫 기록" 빈 상태가 잠깐
// 스쳐 지나갔다. 로그인 상태에서 이번 달 응답이 정리될 때까지는 라우트 로딩
// 화면(app/loading.tsx와 같은 모양)을 그대로 보여준다. 응답이 영영 안 오는
// 경우를 대비해 최대 대기 시간을 둔다.
const BOOTSTRAP_MAX_WAIT_MS = 1500;

type DayStatus = "good" | "near" | "over" | "empty";

const weekdays = ["일", "월", "화", "수", "목", "금", "토"];
const meals: MealType[] = ["아침", "점심", "저녁", "간식"];

function recentMonths() {
  const today = new Date();
  return [-2, -1, 0].map((offset) => {
    const date = new Date(today.getFullYear(), today.getMonth() + offset, 1);
    return {
      year: date.getFullYear(),
      month: date.getMonth() + 1,
      label: `${date.getFullYear()}년 ${date.getMonth() + 1}월`,
      days: new Date(date.getFullYear(), date.getMonth() + 1, 0).getDate(),
      leading: date.getDay(),
    };
  });
}

function roundOne(value: number) {
  return Math.round((value + Number.EPSILON) * 10) / 10;
}

function getDaySugar(items: DietRecord[]) {
  return roundOne(items.reduce((sum, item) => sum + item.sugar, 0));
}

function getDayStatus(items: DietRecord[], sugarGoal = 50): DayStatus {
  if (items.length === 0) return "empty";
  const sugar = getDaySugar(items);
  if (sugar <= sugarGoal * 0.8) return "good";
  if (sugar <= sugarGoal) return "near";
  return "over";
}

function statusTitle(status: DayStatus) {
  if (status === "good") return "이날 목표 안에서 잘 골랐어요";
  if (status === "near") return "이날 목표에 가까웠어요";
  if (status === "over") return "이날 목표를 조금 넘었어요";
  return "이날은 기록이 없어요";
}

function dateKeyFor(option: ReturnType<typeof recentMonths>[number], day: number) {
  return `${option.year}-${String(option.month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
}

// 현재 달을 기준으로 최근 세 달을 구성해 운영 날짜가 바뀌어도 달력이 자연스럽게 이어진다.
export function CalendarDashboard() {
  const { ready, recordsByDate, deleteRecord: removeRecord, loadServerMonth, serverLoading, serverError } = useDietRecords();
  const { ready: authReady, signedIn } = useAuthSession();
  const { goals } = useUserSettings();
  const [serverSettled, setServerSettled] = useState(false);
  const sawServerLoading = useRef(false);
  const todayKey = useMemo(() => getTodayKey(), []);
  const monthOptions = useMemo(() => recentMonths(), []);
  const [month, setMonth] = useState(monthOptions.length - 1);
  const [selectedDay, setSelectedDay] = useState(() => Number(getTodayKey().slice(-2)));
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState("");
  const [entryMeal, setEntryMeal] = useState<MealType | null>(null);

  const sugarGoal = goals.sugar;

  useEffect(() => {
    void loadServerMonth(monthOptions[month].year, monthOptions[month].month);
  }, [loadServerMonth, month, monthOptions]);

  useEffect(() => {
    if (serverLoading) {
      sawServerLoading.current = true;
      return;
    }
    if (sawServerLoading.current) setServerSettled(true);
  }, [serverLoading]);

  useEffect(() => {
    const timer = setTimeout(() => setServerSettled(true), BOOTSTRAP_MAX_WAIT_MS);
    return () => clearTimeout(timer);
  }, []);

  const bootstrapping = !ready || !authReady || (signedIn && !serverSettled);

  const monthOption = monthOptions[month];
  const days = monthOption.days;
  const monthData = useMemo(() => Array.from({ length: days }, (_, index) => {
    const day = index + 1;
    const items = recordsByDate[dateKeyFor(monthOption, day)] ?? [];
    return { day, items, sugar: getDaySugar(items), status: getDayStatus(items, sugarGoal) };
  }), [days, monthOption, recordsByDate, sugarGoal]);

  const selected = monthData.find((item) => item.day === selectedDay) ?? monthData[0];
  const selectedDateKey = dateKeyFor(monthOption, selected.day);
  const hasRecord = selected.items.length > 0;
  const canAddRecord = selectedDateKey <= todayKey;
  const recordedDays = monthData.filter((item) => item.status !== "empty").length;
  const withinGoalDays = monthData.filter((item) => item.status === "good" || item.status === "near").length;
  const emptyDays = days - recordedDays;
  const goodDays = monthData.filter((item) => item.status === "good").length;
  const nearDays = monthData.filter((item) => item.status === "near").length;
  const overDays = monthData.filter((item) => item.status === "over").length;
  const totalSugar = roundOne(monthData.reduce((sum, item) => sum + item.sugar, 0));
  const averageSugar = recordedDays > 0 ? Math.round(totalSugar / recordedDays) : 0;
  const cubes = Math.round(totalSugar / 5);

  const previousWithinGoalDays = useMemo(() => {
    if (month === 0) return 0;
    const previous = monthOptions[month - 1];
    const comparisonLength = month === monthOptions.length - 1 ? Math.min(Number(todayKey.slice(-2)), previous.days) : previous.days;
    return Array.from({ length: comparisonLength }, (_, index) => recordsByDate[dateKeyFor(previous, index + 1)] ?? [])
      .filter((items) => ["good", "near"].includes(getDayStatus(items, sugarGoal))).length;
  }, [month, monthOptions, recordsByDate, sugarGoal, todayKey]);
  const withinGoalDifference = withinGoalDays - previousWithinGoalDays;

  const allItems = monthData.flatMap((item) => item.items);
  const mostFrequentFood = useMemo(() => {
    const counts = new Map<string, number>();
    allItems.forEach((item) => counts.set(item.name, (counts.get(item.name) ?? 0) + 1));
    return [...counts.entries()].sort((a, b) => b[1] - a[1])[0] ?? ["아직 기록이 없어요", 0];
  }, [allItems]);
  const savedSugar = roundOne(Math.max(0, recordedDays * sugarGoal - totalSugar));
  const longestStreak = monthData.reduce((result, item) => {
    const current = item.status === "empty" ? 0 : result.current + 1;
    return { current, best: Math.max(result.best, current) };
  }, { current: 0, best: 0 }).best;
  const bestFood = allItems.length > 0
    ? [...allItems].sort((a, b) => a.sugar - b.sugar)[0]
    : null;
  const bestMeal = meals.map((meal) => {
    const items = allItems.filter((item) => item.meal === meal);
    return { meal, average: items.length > 0 ? items.reduce((sum, item) => sum + item.sugar, 0) / items.length : Number.POSITIVE_INFINITY };
  }).sort((a, b) => a.average - b.average)[0];
  const progress = recordedDays > 0 ? Math.round((withinGoalDays / recordedDays) * 100) : 0;
  const level = recordedDays >= 24 ? "꾸준한 정원사" : recordedDays >= 14 ? "습관을 키우는 중" : recordedDays >= 7 ? "새싹 기록가" : "첫잎을 틔우는 중";
  const chartPoints = monthData.filter((item) => item.status !== "empty").map((item) => {
    const x = days <= 1 ? 0 : ((item.day - 1) / (days - 1)) * 100;
    const y = 96 - Math.min(90, (item.sugar / Math.max(sugarGoal * 1.25, 1)) * 82);
    return `${x},${y}`;
  }).join(" ");

  function moveMonth(direction: number) {
    const nextMonth = Math.min(monthOptions.length - 1, Math.max(0, month + direction));
    setMonth(nextMonth);
    setSelectedDay(nextMonth === monthOptions.length - 1 ? Number(todayKey.slice(-2)) : 1);
    setPendingDeleteId(null);
    setActionMessage("");
  }

  function selectDay(day: number) {
    setSelectedDay(day);
    setPendingDeleteId(null);
    setActionMessage("");
  }

  async function deleteRecord(record: DietRecord) {
    await removeRecord(selectedDateKey, record);
    setPendingDeleteId(null);
    setActionMessage("기록을 삭제했어요.");
  }

  function handleRecordSaved(dateKey: string, record: DietRecord) {
    const [savedYear, savedMonth, savedDay] = dateKey.split("-").map(Number);
    const monthIndex = monthOptions.findIndex((item) => item.year === savedYear && item.month === savedMonth);
    if (monthIndex >= 0) {
      setMonth(monthIndex);
      setSelectedDay(savedDay);
    }
    setActionMessage(`${record.name}을 ${record.meal}에 저장했어요.`);
  }

  const comparisonCopy = month === 0
    ? "첫 달의 흐름을 차곡차곡 기록하고 있어요."
    : withinGoalDifference > 0
      ? `지난달 같은 기간보다 목표 안의 날이 ${withinGoalDifference}일 늘었어요.`
      : withinGoalDifference < 0
        ? `지난달 같은 기간보다 목표 안의 날이 ${Math.abs(withinGoalDifference)}일 적어요.`
        : "지난달 같은 기간과 목표 안의 날이 같아요.";

  const recordAdd = (
    <div className={`calendar-record-add ${canAddRecord ? "" : "is-disabled"}`}>
      <div>
        <strong>{canAddRecord ? "이날 식단을 더 기록할까요?" : "아직 기록할 수 없는 날짜예요"}</strong>
        {!canAddRecord && <p>오늘이나 지난 날짜를 골라주세요.</p>}
      </div>
      {canAddRecord && (
        <div className="calendar-meal-buttons" aria-label="기록할 식사 선택">
          {meals.map((meal) => <button type="button" onClick={() => setEntryMeal(meal)} key={meal}>{meal}</button>)}
        </div>
      )}
    </div>
  );

  if (bootstrapping) {
    return (
      <main className="route-loading page-wrap" aria-live="polite">
        <div className="route-loading-mark" aria-hidden="true" />
        <div><i /><i /><i /></div>
        <p>기록을 불러오고 있어요.</p>
      </main>
    );
  }

  return (
    <main className="calendar-page page-wrap">
      <section className="page-intro wrap">
        <p className="eyebrow">나의 흐름</p>
        <h1>{recordedDays === 0 ? "오늘 한 끼부터 기록해볼까요?" : <>이번 달은 <span className="calendar-streak">{recordedDays}일</span><br />식단을 기록했어요.</>}</h1>
      </section>

      {recordedDays === 0 && (
        <section className="calendar-empty-kickoff wrap" aria-labelledby="calendar-kickoff-title">
          <div>
            <span aria-hidden="true">＋</span>
            <div>
              <p className="eyebrow">첫 기록</p>
              <h2 id="calendar-kickoff-title">지금 먹은 식사를 남겨보세요</h2>
            </div>
          </div>
          <div className="calendar-kickoff-meals" aria-label="오늘 기록할 식사 선택">
            {meals.map((meal) => <button type="button" onClick={() => setEntryMeal(meal)} key={meal}>{meal}</button>)}
          </div>
        </section>
      )}

      <section className="calendar-overview wrap">
        <div className="calendar-panel">
          <header className="calendar-toolbar">
            <button type="button" onClick={() => moveMonth(-1)} disabled={month === 0} aria-label="이전 달">←</button>
            <h2>{monthOption.label}</h2>
            <button type="button" onClick={() => moveMonth(1)} disabled={month === monthOptions.length - 1} aria-label="다음 달">→</button>
          </header>
          {serverLoading && <p className="calendar-server-status" role="status">서버 기록을 불러오는 중이에요.</p>}
          {serverError && <div className="calendar-server-error" role="alert"><span>{serverError} 현재 기기에 저장된 기록은 그대로 볼 수 있어요.</span><button type="button" onClick={() => void loadServerMonth(monthOption.year, monthOption.month)}>다시 불러오기</button></div>}
          <div className="calendar-legend"><span><i className="good" />여유 있음</span><span><i className="near" />목표에 가까움</span><span><i className="over" />목표를 넘음</span><span><i className="empty" />기록 없음</span></div>
          <div className="calendar-weekdays">{weekdays.map((day) => <span key={day}>{day}</span>)}</div>
          <div className="month-grid">
            {Array.from({ length: monthOption.leading }).map((_, index) => <i key={`blank-${index}`} />)}
            {monthData.map((item) => (
              <button
                type="button"
                className={`${item.status} ${selectedDay === item.day ? "is-selected" : ""}`}
                onClick={() => selectDay(item.day)}
                aria-pressed={selectedDay === item.day}
                aria-label={`${monthOption.month}월 ${item.day}일, ${item.status === "empty" ? "기록 없음" : `당류 ${item.sugar}g`}`}
                key={item.day}
              >
                <span>{item.day}</span>
                <b>{item.status === "empty" ? "기록 없음" : `${item.sugar}g`}</b>
              </button>
            ))}
          </div>
        </div>

        <aside className={`selected-day-panel ${hasRecord ? `status-${selected.status}` : "is-empty"}`}>
          <div className="selected-day-content" key={`${month}-${selected.day}-${selected.items.length}`}>
            <p className="eyebrow">{monthOption.month}월 {selected.day}일 기록</p>
            {actionMessage && <p className="record-action-message" role="status">{actionMessage}</p>}

            {hasRecord ? (
              <>
                <h2>{statusTitle(selected.status)}</h2>
                <div className="selected-day-score"><strong>{selected.sugar}<small>g</small></strong><span>당류</span></div>
                <div className="day-food-list">
                  {meals.map((meal) => {
                    const mealItems = selected.items.filter((item) => item.meal === meal);
                    const mealSugar = roundOne(mealItems.reduce((sum, item) => sum + item.sugar, 0));
                    const mealCalories = mealItems.reduce((sum, item) => sum + item.calories, 0);
                    return (
                      <section className="day-meal-group" key={meal}>
                        <header><strong>{meal}</strong><span>{mealItems.length > 0 ? `당류 ${mealSugar}g · ${mealCalories}kcal` : "기록 없음"}</span></header>
                        {mealItems.length > 0 ? mealItems.map((item) => (
                          <article className="day-food-item" key={item.id}>
                            <div className="day-food-copy"><b>{item.name}</b><small>당류 {item.sugar}g · {item.calories}kcal</small></div>
                            <button type="button" onClick={() => setPendingDeleteId(item.id)} aria-label={`${item.name} 기록 삭제`}>삭제</button>
                            {pendingDeleteId === item.id && (
                              <div className="record-delete-confirm" role="alertdialog" aria-label="기록 삭제 확인">
                                <p>이 기록을 삭제할까요?</p>
                                <button type="button" onClick={() => setPendingDeleteId(null)}>취소</button>
                                <button type="button" onClick={() => void deleteRecord(item)}>삭제하기</button>
                              </div>
                            )}
                          </article>
                        )) : <p className="day-meal-empty">아직 기록하지 않았어요.</p>}
                      </section>
                    );
                  })}
                </div>
                <p className={`day-advice ${selected.status}`}>{selected.status === "good" ? `목표까지 ${roundOne(sugarGoal - selected.sugar)}g 남았어요.` : selected.status === "near" ? `목표까지 ${roundOne(sugarGoal - selected.sugar)}g 남았어요. 먹은 양을 바꾸면 다시 계산할 수 있어요.` : `목표보다 ${roundOne(selected.sugar - sugarGoal)}g 높았어요. 기록은 그대로 두고 다음 날의 흐름을 살펴보세요.`}</p>
                {recordAdd}
              </>
            ) : (
              <div className="empty-day-state">
                <span aria-hidden="true">—</span>
                <h2>{statusTitle("empty")}</h2>
                <p>기록하지 않은 날에는 당류와 음식 목록을 표시하지 않아요.</p>
                {recordAdd}
              </div>
            )}
          </div>
        </aside>
      </section>

      <section className="monthly-insights wrap" aria-labelledby="monthly-report-title">
            <header>
              <div><p className="eyebrow">월간 리포트</p><h2 id="monthly-report-title">{monthOption.label}, 기록이 만든 변화</h2></div>
              <p><strong>{comparisonCopy}</strong><span>빈 날도 흐름의 일부예요. 다시 기록한 오늘부터 이어가면 돼요.</span></p>
            </header>

            <div className="monthly-kpis">
              <article><small>목표에서 아낀 당류</small><strong>{savedSugar}<span>g</span></strong><p>기록한 날의 하루 목표와 비교</p></article>
              <article><small>이어 쓴 기록</small><strong>{longestStreak}<span>일</span></strong><p>{level}</p></article>
              <article><small>가장 가벼운 한 끼</small><strong>{bestFood?.name ?? "한 끼씩 찾는 중"}</strong><p>{bestFood ? `당류 ${roundOne(bestFood.sugar)}g` : "첫 기록부터 함께 찾아봐요"}</p></article>
              <article><small>편안했던 시간대</small><strong>{Number.isFinite(bestMeal.average) ? bestMeal.meal : "기록을 기다려요"}</strong><p>{Number.isFinite(bestMeal.average) ? `평균 당류 ${roundOne(bestMeal.average)}g` : "식사별 흐름을 모으고 있어요"}</p></article>
            </div>

            <div className="monthly-visuals">
              <article className="habit-map"><header><div><small>언제 기록했는지</small><h3>{recordedDays}일의 기록이 모였어요</h3></div><span>최장 {longestStreak}일 연속</span></header><div>{monthData.map((item) => <i className={item.status} title={`${item.day}일 ${item.status === "empty" ? "기록 없음" : `당류 ${item.sugar}g`}`} key={item.day} />)}</div><ul className="habit-legend"><li><i className="good" />목표 안<b>{goodDays}일</b></li><li><i className="near" />아슬했던 날<b>{nearDays}일</b></li><li><i className="over" />넘긴 날<b>{overDays}일</b></li><li><i />아직 빈 날<b>{emptyDays}일</b></li></ul><p>빈칸을 채우는 것보다 다시 이어 쓴 날을 기억해요.</p></article>
              <article className="goal-ring-card"><div className="goal-ring" style={{ "--progress": `${progress * 3.6}deg` } as CSSProperties}><span><b>{progress}%</b>목표 안</span></div><div><small>기록한 날의 결과</small><h3>{withinGoalDays}일 모두 목표 안</h3><p>하루 평균 {averageSugar}g, 목표보다 {Math.max(0, roundOne(sugarGoal - averageSugar))}g 가벼웠어요.</p><dl className="goal-ring-stats"><div><dt>기록한 날</dt><dd>{recordedDays}일</dd></div><div><dt>하루 평균</dt><dd>{averageSugar}g</dd></div><div><dt>하루 목표</dt><dd>{sugarGoal}g</dd></div></dl></div></article>
              <article className="sugar-trend"><header><div><small>날짜별 당류</small><h3>오르내려도 목표선 안이에요</h3></div><span>하루 목표 {sugarGoal}g</span></header><svg viewBox="0 0 100 100" preserveAspectRatio="none" role="img" aria-label="이번 달 당류 변화"><line x1="0" y1="30.4" x2="100" y2="30.4" /><polyline points={chartPoints} /></svg><p>기록한 날 평균은 {averageSugar}g이에요. 높은 날 다음에도 기록을 이어간 점이 좋아요.</p></article>
              <article className="growth-card"><small>다음 기록 제안</small><strong>{bestMeal.meal}</strong><h3>{Number.isFinite(bestMeal.average) ? `${bestMeal.meal}은 평균 ${roundOne(bestMeal.average)}g이었어요.` : "한 끼부터 가볍게 기록해보세요."}</h3><p>{mostFrequentFood[1] > 1 ? `${mostFrequentFood[0]} 메뉴처럼 자주 먹는 것부터 적으면 변화가 더 잘 보여요.` : "완벽하게 적기보다 오늘 먹은 한 가지부터 남겨보세요."}</p></article>
            </div>

            <div className="report-archive"><span>다른 달 기록</span>{monthOptions.map((item, index) => index !== month ? <button type="button" key={item.label} onClick={() => { setMonth(index); setSelectedDay(1); }}>{item.label} 보기</button> : null)}</div>
      </section>

      {entryMeal && (
        <RecordMealModal
          meal={entryMeal}
          initialDate={selectedDateKey}
          existingRecordsByDate={recordsByDate}
          minDate="2026-06-01"
          maxDate={todayKey}
          onClose={() => setEntryMeal(null)}
          onSaved={handleRecordSaved}
        />
      )}
    </main>
  );
}
