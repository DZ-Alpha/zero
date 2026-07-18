"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { AUTH_CHANGE_EVENT } from "@/hooks/useAuthSession";
import { getAccessToken, readJwtPayload } from "@/lib/api/client";
import { getDietCalendar, getDietOtherFoods } from "@/lib/api/zerocheck";

export type MealType = "아침" | "점심" | "저녁" | "간식";

export type DietRecord = {
  id: string;
  meal: MealType;
  name: string;
  sugar: number;
  calories: number;
  kind?: "레시피" | "식품" | "사진 분석";
  category?: string;
  note?: string;
  href?: string;
  source?: "local" | "server";
};

export type DietRecordsByDate = Record<string, DietRecord[]>;

export const DIET_RECORDS_KEY = "dangdang-diet-records-v1";
const LEGACY_CALENDAR_KEY = "dangdang-calendar-records";
const RECORDS_CHANGED_EVENT = "dangdang-diet-records-change";

const mealSets = [
  ["그릭요거트와 그래놀라", "닭가슴살 곡물 샐러드", "두부 곤약 비빔면", "제로 초코바"],
  ["통밀 토스트와 달걀", "두부 채소 덮밥", "연어 채소 구이", "라임 제로 스파클링"],
  ["플레인 요거트", "현미 연어 포케", "저당 닭가슴살 볶음", "견과류 한 줌"],
] as const;

function pad(value: number) {
  return String(value).padStart(2, "0");
}

function roundOne(value: number) {
  return Math.round((value + Number.EPSILON) * 10) / 10;
}

export function dateToKey(date: Date) {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

export function getTodayKey() {
  return dateToKey(new Date());
}

export function keyToDate(key: string) {
  const [year, month, day] = key.split("-").map(Number);
  return new Date(year, month - 1, day);
}

export function addDaysToKey(key: string, amount: number) {
  const next = keyToDate(key);
  next.setDate(next.getDate() + amount);
  return dateToKey(next);
}

function createDayRecords(monthIndex: number, day: number): DietRecord[] {
  const isEmpty = monthIndex === 0
    ? day % 8 === 0 || day === 13
    : monthIndex === 1
      ? day > 16 || [3, 9, 12].includes(day)
      : true;

  if (isEmpty) return [];

  const score = (day * 7 + monthIndex * 5) % 10;
  const totalSugar = score < 6 ? 25 + (day % 13) : score < 8 ? 42 + (day % 8) : 53 + (day % 11);
  const portions = [0.16, 0.42, 0.29];
  const sugars = portions.map((portion) => roundOne(totalSugar * portion));
  sugars.push(roundOne(totalSugar - sugars.reduce((sum, value) => sum + value, 0)));
  const names = mealSets[(day + monthIndex) % mealSets.length];
  const meals: MealType[] = ["아침", "점심", "저녁", "간식"];
  const calories = [310 + (day % 4) * 20, 480 + (day % 5) * 25, 390 + (day % 4) * 30, 90 + (day % 3) * 35];

  return meals.map((meal, index) => ({
    id: `seed-${monthIndex}-${day}-${meal}`,
    meal,
    name: names[index],
    sugar: sugars[index],
    calories: calories[index],
    kind: index === 3 ? "식품" : "레시피",
    category: meal,
    note: "식단 기록에 저장된 음식이에요.",
    href: "/diet",
  }));
}

function createSeedRecords(): DietRecordsByDate {
  const records: DietRecordsByDate = {};
  [30, 31, 31].forEach((days, monthIndex) => {
    for (let day = 1; day <= days; day += 1) {
      const key = `2026-${pad(monthIndex + 6)}-${pad(day)}`;
      records[key] = createDayRecords(monthIndex, day);
    }
  });
  return records;
}

function migrateLegacyRecords(raw: string): DietRecordsByDate | null {
  try {
    const legacy = JSON.parse(raw) as Array<Record<string, DietRecord[]>>;
    if (!Array.isArray(legacy)) return null;

    const migrated: DietRecordsByDate = {};
    legacy.forEach((monthRecords, monthIndex) => {
      Object.entries(monthRecords ?? {}).forEach(([day, items]) => {
        const key = `2026-${pad(monthIndex + 6)}-${pad(Number(day))}`;
        migrated[key] = Array.isArray(items) ? items : [];
      });
    });
    return migrated;
  } catch {
    return null;
  }
}

function readStoredRecords() {
  const token = getAccessToken();
  const subject = token ? readJwtPayload(token)?.sub : null;
  const storageKey = subject ? `${DIET_RECORDS_KEY}:user:${String(subject)}` : DIET_RECORDS_KEY;

  // 실제 계정이 없는 상태에서는 과거 데모·게스트 기록을 사용자 기록처럼 보여주지 않는다.
  if (!subject) return {};

  const stored = window.localStorage.getItem(storageKey);
  if (stored) {
    try {
      return JSON.parse(stored) as DietRecordsByDate;
    } catch {
      window.localStorage.removeItem(storageKey);
    }
  }

  window.localStorage.setItem(storageKey, JSON.stringify({}));
  return {};
}

function recordsStorageKey() {
  const token = getAccessToken();
  const subject = token ? readJwtPayload(token)?.sub : null;
  return subject ? `${DIET_RECORDS_KEY}:user:${String(subject)}` : DIET_RECORDS_KEY;
}

function broadcastRecords(records: DietRecordsByDate) {
  window.dispatchEvent(new CustomEvent<DietRecordsByDate>(RECORDS_CHANGED_EVENT, { detail: records }));
}

export function useDietRecords() {
  const [localRecordsByDate, setLocalRecordsByDate] = useState<DietRecordsByDate>({});
  const [serverRecordsByDate, setServerRecordsByDate] = useState<DietRecordsByDate>({});
  const [serverLoading, setServerLoading] = useState(false);
  const [serverError, setServerError] = useState("");
  const [ready, setReady] = useState(false);

  useEffect(() => {
    setLocalRecordsByDate(readStoredRecords());
    setReady(true);

    function syncFromStorage(event: StorageEvent) {
      if (event.key !== recordsStorageKey() || !event.newValue) return;
      try {
        setLocalRecordsByDate(JSON.parse(event.newValue) as DietRecordsByDate);
      } catch {
        // 다른 탭에서 저장 중인 순간에는 기존 화면을 유지해요.
      }
    }

    function syncInPage(event: Event) {
      setLocalRecordsByDate((event as CustomEvent<DietRecordsByDate>).detail);
    }

    function syncAccountRecords() {
      setLocalRecordsByDate(readStoredRecords());
      setServerRecordsByDate({});
      setServerError("");
    }

    window.addEventListener("storage", syncFromStorage);
    window.addEventListener(RECORDS_CHANGED_EVENT, syncInPage);
    window.addEventListener(AUTH_CHANGE_EVENT, syncAccountRecords);
    return () => {
      window.removeEventListener("storage", syncFromStorage);
      window.removeEventListener(RECORDS_CHANGED_EVENT, syncInPage);
      window.removeEventListener(AUTH_CHANGE_EVENT, syncAccountRecords);
    };
  }, []);

  const updateRecords = useCallback((updater: (current: DietRecordsByDate) => DietRecordsByDate) => {
    const current = readStoredRecords();
    const next = updater(current);
    window.localStorage.setItem(recordsStorageKey(), JSON.stringify(next));
    setLocalRecordsByDate(next);
    broadcastRecords(next);
  }, []);

  const addRecord = useCallback((dateKey: string, record: DietRecord) => {
    updateRecords((current) => ({
      ...current,
      [dateKey]: [...(current[dateKey] ?? []), record],
    }));
  }, [updateRecords]);

  const deleteRecord = useCallback((dateKey: string, recordId: string) => {
    updateRecords((current) => ({
      ...current,
      [dateKey]: (current[dateKey] ?? []).filter((item) => item.id !== recordId),
    }));
  }, [updateRecords]);

  const loadServerMonth = useCallback(async (year: number, month: number) => {
    const token = getAccessToken();
    if (!token) return;
    setServerLoading(true);
    setServerError("");

    try {
      const calendar = await getDietCalendar(token, year, month);
      const rows = await Promise.all(calendar.list.map(async (entry, entryIndex) => {
        const id = new URL(entry.url, "http://local").searchParams.get("id");
        if (!id) return [] as Array<[string, DietRecord]>;

        const mealMap: Record<string, MealType> = {
          BREAKFAST: "아침",
          LUNCH: "점심",
          DINNER: "저녁",
          SNACK: "간식",
          OTHER: "간식",
        };
        const meal = mealMap[entry.name.toUpperCase()] ?? "간식";

        try {
          const analysis = await getDietOtherFoods(token, id);
          const items = analysis["list-diet"] ?? [];
          if (items.length === 0) {
            return [[entry.date, {
              id: `server-${id}`,
              meal,
              name: analysis.status === "PENDING" ? "사진 분석을 기다리고 있어요" : "사진으로 등록한 식단",
              sugar: Number(analysis.dang ?? 0),
              calories: Number(analysis.calo ?? 0),
              kind: "사진 분석" as const,
              note: analysis.message ?? "서버에 저장된 사진 식단이에요.",
              href: entry.url,
              source: "server" as const,
            }]] as Array<[string, DietRecord]>;
          }

          return items.map((item, itemIndex) => [entry.date, {
            id: `server-${id}-${itemIndex}`,
            meal,
            name: item.name || `사진 식단 ${entryIndex + 1}`,
            sugar: Number(item.dang ?? 0),
            calories: Number(item.calo ?? 0),
            kind: "사진 분석" as const,
            category: meal,
            note: "서버에 저장된 사진 분석 결과예요.",
            href: entry.url,
            source: "server" as const,
          }]) as Array<[string, DietRecord]>;
        } catch {
          return [[entry.date, {
            id: `server-${id}`,
            meal,
            name: "사진으로 등록한 식단",
            sugar: 0,
            calories: 0,
            kind: "사진 분석" as const,
            note: "분석 결과를 불러오지 못했어요.",
            href: entry.url,
            source: "server" as const,
          }]] as Array<[string, DietRecord]>;
        }
      }));

      const monthPrefix = `${year}-${pad(month)}-`;
      setServerRecordsByDate((current) => {
        const next = Object.fromEntries(Object.entries(current).filter(([key]) => !key.startsWith(monthPrefix))) as DietRecordsByDate;
        rows.flat().forEach(([dateKey, record]) => {
          next[dateKey] = [...(next[dateKey] ?? []), record];
        });
        return next;
      });
    } catch {
      setServerError("서버의 사진 기록을 불러오지 못했어요.");
    } finally {
      setServerLoading(false);
    }
  }, []);

  const recordsByDate = useMemo(() => {
    const merged: DietRecordsByDate = { ...localRecordsByDate };
    Object.entries(serverRecordsByDate).forEach(([dateKey, serverItems]) => {
      const localItems = merged[dateKey] ?? [];
      const ids = new Set(localItems.map((item) => item.id));
      merged[dateKey] = [...localItems, ...serverItems.filter((item) => !ids.has(item.id))];
    });
    return merged;
  }, [localRecordsByDate, serverRecordsByDate]);

  return { ready, recordsByDate, addRecord, deleteRecord, loadServerMonth, serverLoading, serverError };
}
