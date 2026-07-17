"use client";

import { useEffect, useMemo, useState } from "react";
import { addDaysToKey, dateToKey, getTodayKey, keyToDate } from "@/hooks/useDietRecords";

const weekdays = ["일", "월", "화", "수", "목", "금", "토"];

function monthKey(date: Date) {
  return date.getFullYear() * 12 + date.getMonth();
}

function formatDateLabel(key: string) {
  const date = keyToDate(key);
  const isToday = key === getTodayKey();
  return `${date.getMonth() + 1}월 ${date.getDate()}일 ${weekdays[date.getDay()]}요일${isToday ? " · 오늘" : ""}`;
}

export function RecordDateNavigator({
  value,
  onChange,
  min,
  max = getTodayKey(),
}: {
  value: string;
  onChange: (value: string) => void;
  min?: string;
  max?: string;
}) {
  const [open, setOpen] = useState(false);
  const [viewDate, setViewDate] = useState(() => keyToDate(value));

  useEffect(() => {
    setViewDate(keyToDate(value));
  }, [value]);

  const calendar = useMemo(() => {
    const year = viewDate.getFullYear();
    const month = viewDate.getMonth();
    const firstDay = new Date(year, month, 1).getDay();
    const days = new Date(year, month + 1, 0).getDate();
    return { year, month, firstDay, days };
  }, [viewDate]);

  const previousDate = addDaysToKey(value, -1);
  const nextDate = addDaysToKey(value, 1);
  const canMovePrevious = !min || previousDate >= min;
  const canMoveNext = !max || nextDate <= max;
  const minMonth = min ? monthKey(keyToDate(min)) : Number.NEGATIVE_INFINITY;
  const maxMonth = max ? monthKey(keyToDate(max)) : Number.POSITIVE_INFINITY;
  const currentViewMonth = monthKey(viewDate);

  function chooseDate(key: string) {
    onChange(key);
    setOpen(false);
  }

  function moveViewMonth(amount: number) {
    setViewDate((current) => new Date(current.getFullYear(), current.getMonth() + amount, 1));
  }

  return (
    <div className="record-date-navigator">
      <button
        type="button"
        className="record-date-arrow"
        disabled={!canMovePrevious}
        onClick={() => canMovePrevious && onChange(previousDate)}
        aria-label="이전 날짜"
      >
        ←
      </button>
      <button
        type="button"
        className="record-date-current"
        onClick={() => setOpen((current) => !current)}
        aria-expanded={open}
      >
        <span>{formatDateLabel(value)}</span>
        <i aria-hidden="true" />
      </button>
      <button
        type="button"
        className="record-date-arrow"
        disabled={!canMoveNext}
        onClick={() => canMoveNext && onChange(nextDate)}
        aria-label="다음 날짜"
      >
        →
      </button>

      {open && (
        <div className="record-date-popover" role="dialog" aria-label="기록할 날짜 선택">
          <header>
            <button type="button" onClick={() => moveViewMonth(-1)} disabled={currentViewMonth <= minMonth} aria-label="이전 달">←</button>
            <strong>{calendar.year}년 {calendar.month + 1}월</strong>
            <button type="button" onClick={() => moveViewMonth(1)} disabled={currentViewMonth >= maxMonth} aria-label="다음 달">→</button>
          </header>
          <div className="record-date-weekdays">{weekdays.map((day) => <span key={day}>{day}</span>)}</div>
          <div className="record-date-grid">
            {Array.from({ length: calendar.firstDay }, (_, index) => <i key={`blank-${index}`} />)}
            {Array.from({ length: calendar.days }, (_, index) => {
              const day = index + 1;
              const key = dateToKey(new Date(calendar.year, calendar.month, day));
              const disabled = Boolean((min && key < min) || (max && key > max));
              return (
                <button
                  type="button"
                  className={`${key === value ? "is-selected" : ""} ${key === getTodayKey() ? "is-today" : ""}`}
                  disabled={disabled}
                  onClick={() => chooseDate(key)}
                  aria-pressed={key === value}
                  key={key}
                >
                  {day}
                </button>
              );
            })}
          </div>
          <button type="button" className="record-date-today" onClick={() => chooseDate(getTodayKey())}>오늘로 이동</button>
        </div>
      )}
    </div>
  );
}
