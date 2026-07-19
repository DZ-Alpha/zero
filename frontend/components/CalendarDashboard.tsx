"use client";

import { useEffect, useMemo, useState } from "react";
import { RecordMealModal } from "@/components/RecordMealModal";
import { DietRecord, getTodayKey, MealType, useDietRecords } from "@/hooks/useDietRecords";
import { useUserSettings } from "@/hooks/useUserSettings";

type DayStatus = "good" | "near" | "over" | "empty";

const monthNames = ["2026년 6월", "2026년 7월", "2026년 8월"];
const monthLengths = [30, 31, 31];
const leadingDays = [1, 3, 6];
const weekdays = ["일", "월", "화", "수", "목", "금", "토"];
const meals: MealType[] = ["아침", "점심", "저녁", "간식"];

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

function dateKeyFor(monthIndex: number, day: number) {
  return `2026-${String(monthIndex + 6).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
}

export function CalendarDashboard() {
  const { recordsByDate, deleteRecord: removeRecord, loadServerMonth, serverLoading, serverError } = useDietRecords();
  const { goals } = useUserSettings();
  const todayKey = useMemo(() => getTodayKey(), []);
  const [month, setMonth] = useState(1);
  const [selectedDay, setSelectedDay] = useState(16);
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState("");
  const [entryMeal, setEntryMeal] = useState<MealType | null>(null);

  const sugarGoal = goals.sugar;

  useEffect(() => {
    void loadServerMonth(2026, month + 6);
  }, [loadServerMonth, month]);

  const days = monthLengths[month];
  const monthData = useMemo(() => Array.from({ length: days }, (_, index) => {
    const day = index + 1;
    const items = recordsByDate[dateKeyFor(month, day)] ?? [];
    return { day, items, sugar: getDaySugar(items), status: getDayStatus(items, sugarGoal) };
  }), [days, month, recordsByDate, sugarGoal]);

  const selected = monthData.find((item) => item.day === selectedDay) ?? monthData[0];
  const selectedDateKey = dateKeyFor(month, selected.day);
  const hasRecord = selected.items.length > 0;
  const canAddRecord = selectedDateKey <= todayKey;
  const recordedDays = monthData.filter((item) => item.status !== "empty").length;
  const withinGoalDays = monthData.filter((item) => item.status === "good" || item.status === "near").length;
  const emptyDays = days - recordedDays;
  const totalSugar = roundOne(monthData.reduce((sum, item) => sum + item.sugar, 0));
  const averageSugar = recordedDays > 0 ? Math.round(totalSugar / recordedDays) : 0;
  const cubes = Math.round(totalSugar / 5);

  const previousWithinGoalDays = useMemo(() => {
    if (month === 0) return 0;
    const comparisonLength = month === 1 ? 16 : monthLengths[month - 1];
    return Array.from({ length: comparisonLength }, (_, index) => recordsByDate[dateKeyFor(month - 1, index + 1)] ?? [])
      .filter((items) => ["good", "near"].includes(getDayStatus(items, sugarGoal))).length;
  }, [month, recordsByDate, sugarGoal]);
  const withinGoalDifference = withinGoalDays - previousWithinGoalDays;

  const allItems = monthData.flatMap((item) => item.items);
  const mostFrequentFood = useMemo(() => {
    const counts = new Map<string, number>();
    allItems.forEach((item) => counts.set(item.name, (counts.get(item.name) ?? 0) + 1));
    return [...counts.entries()].sort((a, b) => b[1] - a[1])[0] ?? ["아직 기록이 없어요", 0];
  }, [allItems]);

  function moveMonth(direction: number) {
    const nextMonth = Math.min(monthNames.length - 1, Math.max(0, month + direction));
    setMonth(nextMonth);
    setSelectedDay(nextMonth === 1 ? 15 : 1);
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
    const [, savedMonth, savedDay] = dateKey.split("-").map(Number);
    const monthIndex = savedMonth - 6;
    if (monthIndex >= 0 && monthIndex < monthNames.length) {
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
        <p>{canAddRecord ? "식사를 고르면 홈과 같은 기록창이 열려요." : "오늘이나 지난 날짜를 골라주세요."}</p>
      </div>
      {canAddRecord && (
        <div className="calendar-meal-buttons" aria-label="기록할 식사 선택">
          {meals.map((meal) => <button type="button" onClick={() => setEntryMeal(meal)} key={meal}>{meal}</button>)}
        </div>
      )}
    </div>
  );

  return (
    <main className="calendar-page page-wrap">
      <section className="page-intro wrap">
        <p className="eyebrow">나의 흐름</p>
        <h1>이번 달은 <span className="calendar-streak">{recordedDays}일</span><br />식단을 기록했어요.</h1>
        <p>날짜를 누르면 그날 먹은 음식과 당류를 보고, 필요 없는 기록은 바로 지울 수 있어요.</p>
      </section>

      <section className="calendar-overview wrap">
        <div className="calendar-panel">
          <header className="calendar-toolbar">
            <button type="button" onClick={() => moveMonth(-1)} disabled={month === 0} aria-label="이전 달">←</button>
            <h2>{monthNames[month]}</h2>
            <button type="button" onClick={() => moveMonth(1)} disabled={month === monthNames.length - 1} aria-label="다음 달">→</button>
          </header>
          {serverLoading && <p className="calendar-server-status" role="status">서버 기록을 불러오는 중이에요.</p>}
          {serverError && <div className="calendar-server-error" role="alert"><span>{serverError} 현재 기기에 저장된 기록은 그대로 볼 수 있어요.</span><button type="button" onClick={() => void loadServerMonth(2026, month + 6)}>다시 불러오기</button></div>}
          <div className="calendar-legend"><span><i className="good" />여유 있음</span><span><i className="near" />목표에 가까움</span><span><i className="over" />목표를 넘음</span><span><i className="empty" />기록 없음</span></div>
          <div className="calendar-weekdays">{weekdays.map((day) => <span key={day}>{day}</span>)}</div>
          <div className="month-grid">
            {Array.from({ length: leadingDays[month] }).map((_, index) => <i key={`blank-${index}`} />)}
            {monthData.map((item) => (
              <button
                type="button"
                className={`${item.status} ${selectedDay === item.day ? "is-selected" : ""}`}
                onClick={() => selectDay(item.day)}
                aria-pressed={selectedDay === item.day}
                aria-label={`${month + 6}월 ${item.day}일, ${item.status === "empty" ? "기록 없음" : `당류 ${item.sugar}g`}`}
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
            <p className="eyebrow">{month + 6}월 {selected.day}일 기록</p>
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

      <section className="month-summary wrap">
        <header className="section-line-heading"><div><p className="eyebrow">지난달과 비교</p><h2>{monthNames[month]} 기록 요약</h2></div><p>{comparisonCopy}</p></header>
        <div className="summary-grid">
          <article><small>기록한 날</small><strong>{recordedDays}<span>일</span></strong><p>기록이 없는 날 {emptyDays}일</p></article>
          <article><small>목표 안의 날</small><strong>{withinGoalDays}<span>일</span></strong><p>설정한 하루 목표 이하</p></article>
          <article><small>이번 달 당류</small><strong>{totalSugar.toLocaleString()}<span>g</span></strong><p>각설탕 약 {cubes}개 분량</p></article>
          <article><small>기록한 날 평균</small><strong>{averageSugar}<span>g</span></strong><p>기록이 있는 날만 계산했어요</p></article>
        </div>
      </section>

      <section className="monthly-report wrap">
        <header><div><p className="eyebrow">월간 리포트</p><h2>이번 달 기록에서 보인 흐름이에요</h2></div><span>{monthNames[month]} 기록</span></header>
        <div className="report-grid">
          <article className="report-main"><small>이번 달 흐름</small><h3>{recordedDays > 0 ? `${recordedDays}일 중 ${withinGoalDays}일은\n목표 안에 있었어요.` : "아직 기록이 없어요."}</h3><p>{recordedDays > 0 ? "잘한 날과 아쉬운 날을 나누기보다, 기록을 이어간 흐름을 확인해보세요. 날짜를 누르면 그날의 식단을 다시 볼 수 있어요." : "식단을 한 번 기록하면 월간 흐름과 자주 먹은 메뉴를 여기에서 정리해드릴게요."}</p></article>
          <article><small>가장 자주 기록한 메뉴</small><h3>{mostFrequentFood[0]}</h3><strong>{mostFrequentFood[1]}<span>회</span></strong><p>식사 기록에 가장 많이 등장했어요.</p></article>
          <article><small>기록이 없는 날</small><h3>{emptyDays > 0 ? `${emptyDays}일은 비어 있어요` : "모든 날을 기록했어요"}</h3><strong>{emptyDays}<span>일</span></strong><p>회색 날짜를 누르면 비어 있는 날을 확인할 수 있어요.</p></article>
        </div>
        <div className="report-archive"><span>다른 달 기록</span>{month !== 0 && <button type="button" onClick={() => { setMonth(0); setSelectedDay(1); }}>2026년 6월 보기</button>}{month !== 1 && <button type="button" onClick={() => { setMonth(1); setSelectedDay(15); }}>2026년 7월 보기</button>}{month !== 2 && <button type="button" onClick={() => { setMonth(2); setSelectedDay(1); }}>2026년 8월 보기</button>}</div>
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
