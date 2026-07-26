"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AUTH_CHANGE_EVENT } from "@/hooks/useAuthSession";
import { getAccessToken, readJwtPayload } from "@/lib/api/client";
import { createDietRecord, deleteDietRecord, getDietRecordsByMonth } from "@/lib/api/zerocheck";

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
  // source === "server"일 때 실제 삭제 API 대상(meal_log_id). id는 화면
  // key/구분용이라 사진 기록처럼 한 meal_log에 항목이 여럿이면 id와 다를 수 있다.
  recordId?: string;
};

export type DietRecordsByDate = Record<string, DietRecord[]>;

export const DIET_RECORDS_KEY = "dangdang-diet-records-v1";
const LEGACY_CALENDAR_KEY = "dangdang-calendar-records";
const RECORDS_CHANGED_EVENT = "dangdang-diet-records-change";
// 저장/삭제가 서버에 실제로 반영된 뒤 쏘는 신호 — Home/캘린더처럼 각자 별도
// useDietRecords() 인스턴스를 쓰는 화면들이, 서로의 addServerRecord/deleteRecord
// 호출을 모른 채 "마지막으로 불러온 달"을 다시 불러오도록 한다(useDailyGauge도
// 같은 이벤트로 오늘 합계를 다시 가져온다). RECORDS_CHANGED_EVENT는 로컬(local)
// 항목 동기화용이라 서버 합계 갱신 신호로는 못 쓴다.
export const DIET_SAVE_EVENT = "dangdang-diet-save";

function broadcastSave() {
  window.dispatchEvent(new Event(DIET_SAVE_EVENT));
}

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
    broadcastSave();
  }, [updateRecords]);

  // record.source === "server"인 항목은 실제 백엔드 기록(RC-0113~0117)이라
  // DELETE API를 먼저 호출해야 한다. 로컬 전용 항목은 그대로 localStorage에서만 지운다.
  const deleteRecord = useCallback(async (dateKey: string, record: DietRecord) => {
    if (record.source === "server") {
      const token = getAccessToken();
      const recordId = record.recordId ?? record.id.replace(/^server-/, "");
      if (token) {
        try {
          await deleteDietRecord(token, recordId);
        } catch {
          // 삭제 실패해도 화면에서는 지워서 재시도를 유도한다 — 다음 loadServerMonth에서
          // 서버에 남아있으면 다시 나타난다.
        }
      }
      setServerRecordsByDate((current) => ({
        ...current,
        [dateKey]: (current[dateKey] ?? []).filter((item) => item.id !== record.id),
      }));
      // RecordMealModal이 사진 기록을 저장할 때 source:"server"인 항목을 다른
      // 화면에도 즉시 보이도록 localStorage에도 남겨둔다(addRecord 참고) — 이
      // 항목을 지울 때 localStorage 쪽을 안 건드리면, 실제로는 DB에서 지워졌는데도
      // 하드 리프레시를 해도 계속 보이고 계속 404만 나는 유령 기록이 됐었다.
      updateRecords((current) => ({
        ...current,
        [dateKey]: (current[dateKey] ?? []).filter((item) => item.id !== record.id),
      }));
      broadcastSave();
      return;
    }
    updateRecords((current) => ({
      ...current,
      [dateKey]: (current[dateKey] ?? []).filter((item) => item.id !== record.id),
    }));
    broadcastSave();
  }, [updateRecords]);

  // 레시피/상품 기록을 실제 서버에 저장한다(RC-0113). 사진 기록은 /diet/upload +
  // /diet/ai-analyze 단계에서 이미 서버에 저장되므로 이 함수를 쓰지 않는다.
  const addServerRecord = useCallback(async (dateKey: string, values: {
    meal: MealType;
    itemType: "recipe" | "product";
    itemId: string;
    serving?: number;
    sugar: number;
    calories: number;
    name: string;
    category?: string;
    note?: string;
    href?: string;
  }) => {
    const token = getAccessToken();
    if (!token) throw new Error("로그인이 필요해요.");

    const created = await createDietRecord(token, {
      date: dateKey,
      mealType: values.meal,
      itemType: values.itemType,
      itemId: values.itemId,
      serving: values.serving ?? 1,
      sugar: values.sugar,
      calories: values.calories,
    });

    const record: DietRecord = {
      id: `server-${created.id}`,
      meal: values.meal,
      name: values.name,
      sugar: values.sugar,
      calories: values.calories,
      kind: values.itemType === "recipe" ? "레시피" : "식품",
      category: values.category,
      note: values.note,
      href: values.href,
      source: "server",
      recordId: created.id,
    };
    setServerRecordsByDate((current) => ({
      ...current,
      [dateKey]: [...(current[dateKey] ?? []), record],
    }));
    broadcastSave();
    return record;
  }, []);

  const mealTypeToKorean: Record<string, MealType> = {
    BREAKFAST: "아침",
    LUNCH: "점심",
    DINNER: "저녁",
    SNACK: "간식",
    OTHER: "간식",
  };

  const lastMonthRef = useRef<{ year: number; month: number } | null>(null);

  const loadServerMonth = useCallback(async (year: number, month: number) => {
    lastMonthRef.current = { year, month };
    const token = getAccessToken();
    if (!token) return;
    setServerLoading(true);
    setServerError("");

    try {
      // RC-0113~0117 반영 후: /diet/records?year=&month=가 날짜별로 합계+항목을
      // 한 응답에 담아준다 — 예전처럼 캘린더 목록 이후 기록마다 /diet/other-foods를
      // 또 부르는 N+1이 없다(PRODUCTION_HANDOFF.md P1-3).
      const monthData = await getDietRecordsByMonth(token, year, month);
      const monthPrefix = `${year}-${pad(month)}-`;
      const next: DietRecordsByDate = {};
      monthData.list.forEach((day) => {
        next[day.date] = day.list.map((item) => ({
          // entryId(meal_item PK)로 고유해야 한다 — recordId(meal_log_id)는 사진 한 장에서
          // 음식이 여럿 인식되면 항목마다 동일해서, 이걸 id로 쓰면 목록 key가 겹쳐 삭제가
          // 엉뚱한 항목에 걸리거나 안 먹히는 버그가 있었다.
          id: `server-${item.entryId}`,
          meal: mealTypeToKorean[item.mealType] ?? "간식",
          name: item.name,
          sugar: Number(item.sugar ?? 0),
          calories: Number(item.calories ?? 0),
          kind: item.itemType === "recipe" ? "레시피" : item.itemType === "product" ? "식품" : "사진 분석",
          note: item.itemType === "photo" ? "서버에 저장된 사진 분석 결과예요." : undefined,
          source: "server" as const,
          recordId: item.recordId,
        }));
      });

      setServerRecordsByDate((current) => ({
        ...Object.fromEntries(Object.entries(current).filter(([key]) => !key.startsWith(monthPrefix))),
        ...next,
      }));

      // RecordMealModal이 사진 기록을 확정하면(saveItem) 다른 화면에도 바로 보이게
      // localStorage에도 source:"server" 항목을 임시로 남겨둔다(addRecord) — 이 달의
      // 진짜 서버 데이터를 방금 받아왔으니 그 임시 항목은 이제 필요 없다. 안 지우면
      // (a) entryId 기준 새 항목과 id가 달라 같은 기록이 중복으로 두 번 보이고
      // (b) 그 임시 항목은 지워도 삭제 대상(recordId)만 사라질 뿐 localStorage에는
      // 영원히 남아서, 실제로 DB에서 지워진 뒤에도 하드 리프레시로도 안 없어지는
      // 유령 기록이 된다.
      updateRecords((current) => {
        let changed = false;
        const pruned: DietRecordsByDate = { ...current };
        Object.keys(pruned).forEach((dateKey) => {
          if (!dateKey.startsWith(monthPrefix)) return;
          const withoutServerOnly = pruned[dateKey].filter((item) => item.source !== "server");
          if (withoutServerOnly.length !== pruned[dateKey].length) {
            pruned[dateKey] = withoutServerOnly;
            changed = true;
          }
        });
        return changed ? pruned : current;
      });
    } catch {
      setServerError("서버의 식단 기록을 불러오지 못했어요.");
    } finally {
      setServerLoading(false);
    }
  }, [updateRecords]);

  // 다른 useDietRecords() 인스턴스(RecordMealModal 등)가 저장/삭제에 성공하면
  // DIET_SAVE_EVENT를 쏜다 — 이 인스턴스가 이미 불러온 적 있는 달이 있으면
  // (Home/캘린더는 마운트 시 loadServerMonth를 호출해둔다) 그 달을 다시 불러와
  // 새로고침 없이도 최신 합계로 갱신한다.
  useEffect(() => {
    function reloadOnSave() {
      const target = lastMonthRef.current;
      if (target) void loadServerMonth(target.year, target.month);
    }
    window.addEventListener(DIET_SAVE_EVENT, reloadOnSave);
    return () => window.removeEventListener(DIET_SAVE_EVENT, reloadOnSave);
  }, [loadServerMonth]);

  const recordsByDate = useMemo(() => {
    const merged: DietRecordsByDate = { ...localRecordsByDate };
    Object.entries(serverRecordsByDate).forEach(([dateKey, serverItems]) => {
      const localItems = merged[dateKey] ?? [];
      const ids = new Set(localItems.map((item) => item.id));
      merged[dateKey] = [...localItems, ...serverItems.filter((item) => !ids.has(item.id))];
    });
    return merged;
  }, [localRecordsByDate, serverRecordsByDate]);

  return { ready, recordsByDate, addRecord, addServerRecord, deleteRecord, loadServerMonth, serverLoading, serverError };
}
