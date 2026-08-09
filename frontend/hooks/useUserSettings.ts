"use client";

import { useCallback, useEffect, useState } from "react";
import { AUTH_CHANGE_EVENT } from "@/hooks/useAuthSession";
import { getAccessToken, readJwtPayload } from "@/lib/api/client";
import {
  getAllergenTags,
  getHealthLabelTags,
  getHealthProfile,
  getMyPage,
  getUserPreferences,
  replaceUserPreferences,
  updateFirstSet,
  updateHealthProfile,
  type UserPreferenceItem,
} from "@/lib/api/zerocheck";

export const USER_PROFILE_KEY = "dangdang-signup-profile";
export const USER_GOALS_KEY = "dangdang-goals";
export const USER_SETTINGS_CHANGE_EVENT = "dangdang-user-settings-change";

export type UserProfile = {
  name?: string;
  birthDate?: string;
  birthYear?: string;
  gender?: string;
  height?: number;
  weight?: number;
  activity?: string;
  interests?: string[];
  allergens?: string[];
  allergenCodes?: string[];
  provider?: string;
  email?: string;
  enabledSns?: string[];
  nameLocked?: boolean;
  birthDateLocked?: boolean;
  healthConsent?: boolean;
  marketingConsent?: boolean;
  notifications?: {
    newProducts: boolean;
    weeklyReport: boolean;
  };
};

export type UserGoals = {
  sugar: number;
  calories: number;
  maintenanceCalories?: number;
  bmr?: number;
};

const defaultGoals: UserGoals = { sugar: 50, calories: 2000 };

function settingsSubject(token = getAccessToken()) {
  if (!token) return "guest";
  const payload = readJwtPayload(token);
  return String(payload?.sub ?? payload?.user_id ?? "guest");
}

function scopedSettingsKey(key: string, token = getAccessToken()) {
  return `${key}:user:${settingsSubject(token)}`;
}

function parseStored<T>(key: string, fallback: T, token = getAccessToken()): T {
  if (typeof window === "undefined") return fallback;
  try {
    const stored = window.localStorage.getItem(scopedSettingsKey(key, token));
    return stored ? JSON.parse(stored) as T : fallback;
  } catch {
    return fallback;
  }
}

export function readUserProfile(token = getAccessToken()) {
  return parseStored<UserProfile>(USER_PROFILE_KEY, {}, token);
}

export function readUserGoals(token = getAccessToken()) {
  return { ...defaultGoals, ...parseStored<Partial<UserGoals>>(USER_GOALS_KEY, {}, token) };
}

function notifySettingsChanged() {
  window.dispatchEvent(new Event(USER_SETTINGS_CHANGE_EVENT));
}

export function saveUserProfile(profile: UserProfile) {
  window.localStorage.setItem(scopedSettingsKey(USER_PROFILE_KEY), JSON.stringify(profile));
  notifySettingsChanged();
}

export function saveUserGoals(goals: UserGoals) {
  window.localStorage.setItem(scopedSettingsKey(USER_GOALS_KEY), JSON.stringify(goals));
  notifySettingsChanged();
}

function birthdayForApi(profile: UserProfile) {
  const value = (profile.birthDate ?? "").replace(/\D/g, "");
  if (value.length !== 8) return undefined;
  return `${value.slice(0, 4)}-${value.slice(4, 6)}-${value.slice(6, 8)}`;
}

export type ServerSettingsScope = "profile" | "goals" | "interests" | "allergens";

const HEALTH_LABEL_CODE_BY_NAME: Record<string, string> = {
  "제로": "ZERO_GENERAL",
  "제로슈거": "ZERO_SUGAR",
  "제로칼로리": "ZERO_CALORIE",
  "저당": "LOW_SUGAR",
  "저칼로리": "LOW_CALORIE",
  "무가당·무첨가당": "NO_ADDED_SUGAR",
  "고단백": "HIGH_PROTEIN",
};

function preferenceLabels(preferences: UserPreferenceItem[], type: UserPreferenceItem["preferenceType"]) {
  const healthNameByCode = new Map(
    Object.entries(HEALTH_LABEL_CODE_BY_NAME).map(([name, code]) => [code, name]),
  );
  return preferences
    .filter((preference) => preference.preferenceType === type)
    .map((preference) => type === "INTEREST_CATEGORY" && preference.tagCode
      ? healthNameByCode.get(preference.tagCode) || preference.tagName
      : preference.tagName || preference.customValue)
    .filter((value): value is string => Boolean(value));
}

export async function savePreferenceLabelsToServer(
  token: string,
  interests: string[],
  allergens: string[],
) {
  const [healthLabels, allergenTags, current] = await Promise.all([
    getHealthLabelTags(),
    getAllergenTags(),
    getUserPreferences(token),
  ]);
  const healthByCode = new Map(healthLabels.list.map((tag) => [tag.code, tag]));
  const allergenByName = new Map(allergenTags.list.map((tag) => [tag.name.replace(/\s/g, ""), tag]));
  const interestTagIds = interests
    .map((label) => healthByCode.get(HEALTH_LABEL_CODE_BY_NAME[label])?.id)
    .filter((id): id is string => Boolean(id));
  const selectedAllergens = allergens.filter((label) => label !== "해당 없음");
  const allergenTagIds = selectedAllergens
    .map((label) => allergenByName.get(label.replace(/\s/g, ""))?.id)
    .filter((id): id is string => Boolean(id));
  const cautionIngredients = current.preferences
    .filter((preference) => preference.preferenceType === "CAUTION_INGREDIENT")
    .map((preference) => preference.customValue)
    .filter((value): value is string => Boolean(value));

  if (interestTagIds.length !== new Set(interests).size) {
    throw new Error("선택한 관심 기준을 서버 태그와 연결하지 못했습니다.");
  }
  if (allergenTagIds.length !== new Set(selectedAllergens).size) {
    throw new Error("선택한 알레르기 성분을 서버 태그와 연결하지 못했습니다.");
  }

  return replaceUserPreferences(token, { interestTagIds, allergenTagIds, cautionIngredients });
}

export async function saveUserSettingsToServer(
  token: string,
  profile: UserProfile,
  goals: UserGoals,
  scope: ServerSettingsScope,
) {
  const requests: Promise<unknown>[] = [];

  if (scope === "profile" || scope === "interests") {
    requests.push(updateFirstSet(token, {
      nickname: scope === "profile" ? profile.name?.trim() || undefined : undefined,
      email: scope === "profile" ? profile.email?.trim() || undefined : undefined,
      favoriteCategory: scope === "interests" ? profile.interests ?? [] : undefined,
      optionalAgree: profile.healthConsent,
      tall: scope === "profile" && profile.height ? Math.round(profile.height) : undefined,
      weight: scope === "profile" && profile.weight ? profile.weight : undefined,
      birthday: scope === "profile" ? birthdayForApi(profile) : undefined,
    }));
  }

  if (scope === "interests" || scope === "allergens") {
    requests.push(savePreferenceLabelsToServer(
      token,
      profile.interests ?? [],
      profile.allergens ?? [],
    ));
  }

  if ((scope === "profile" || scope === "goals") && profile.healthConsent) {
    const birthYear = Number((profile.birthDate || profile.birthYear || "").replace(/\D/g, "").slice(0, 4));
    requests.push(updateHealthProfile(token, {
      consent: true,
      birthYear: Number.isFinite(birthYear) && birthYear > 0 ? birthYear : undefined,
      gender: profile.gender,
      heightCm: profile.height,
      weightKg: profile.weight,
      activityLevel: profile.activity,
      healthGoal: "BALANCE",
      dailyCalorieTarget: goals.calories,
      dailySugarTargetG: goals.sugar,
    }));
  }

  await Promise.all(requests);
}

export function useUserSettings() {
  const [profile, setProfile] = useState<UserProfile>({});
  const [goals, setGoals] = useState<UserGoals>(defaultGoals);
  const [ready, setReady] = useState(false);
  const [sessionRevision, setSessionRevision] = useState(0);

  const sync = useCallback(() => {
    setProfile(readUserProfile());
    setGoals(readUserGoals());
    setReady(true);
  }, []);

  useEffect(() => {
    sync();
    const syncSession = () => {
      sync();
      setSessionRevision((current) => current + 1);
    };
    window.addEventListener("storage", sync);
    window.addEventListener(USER_SETTINGS_CHANGE_EVENT, sync);
    window.addEventListener(AUTH_CHANGE_EVENT, syncSession);
    return () => {
      window.removeEventListener("storage", sync);
      window.removeEventListener(USER_SETTINGS_CHANGE_EVENT, sync);
      window.removeEventListener(AUTH_CHANGE_EVENT, syncSession);
    };
  }, [sync]);

  useEffect(() => {
    const token = getAccessToken();
    if (!token) return;
    let active = true;

    Promise.allSettled([getMyPage(token), getHealthProfile(token), getUserPreferences(token)]).then(([myPageResult, healthResult, preferenceResult]) => {
      if (!active) return;
      const currentProfile = readUserProfile(token);
      const currentGoals = readUserGoals(token);
      const tokenPayload = readJwtPayload(token);
      const nickname = typeof tokenPayload?.nickname === "string" ? tokenPayload.nickname : undefined;
      const myPage = myPageResult.status === "fulfilled" ? myPageResult.value : null;
      const health = healthResult.status === "fulfilled" ? healthResult.value : null;
      const preferences = preferenceResult.status === "fulfilled" ? preferenceResult.value.preferences : null;
      const databaseInterests = preferences ? preferenceLabels(preferences, "INTEREST_CATEGORY") : null;
      const databaseAllergens = preferences ? preferenceLabels(preferences, "ALLERGEN") : null;
      const databaseAllergenCodes = preferences
        ? preferences
          .filter((preference) => preference.preferenceType === "ALLERGEN")
          .map((preference) => preference.tagCode)
          .filter((value): value is string => Boolean(value))
        : null;
      const hasDatabasePreferences = Boolean(preferences?.length);

      const nextProfile: UserProfile = {
        ...currentProfile,
        // 마이페이지에서 직접 바꾼 이름(myPage.nickname)이 있으면 그게 우선 —
        // 그렇지 않으면 로그인 시점 소셜 프로필 이름(JWT nickname)을 쓴다.
        name: myPage?.nickname || nickname || currentProfile.name,
        email: myPage?.email ?? currentProfile.email,
        enabledSns: myPage?.enabledSns ?? currentProfile.enabledSns,
        provider: myPage?.enabledSns?.[0]?.toLowerCase() ?? currentProfile.provider,
        interests: hasDatabasePreferences
          ? databaseInterests ?? []
          : myPage?.favorite?.length ? myPage.favorite : currentProfile.interests,
        allergens: hasDatabasePreferences ? databaseAllergens ?? [] : currentProfile.allergens,
        allergenCodes: hasDatabasePreferences ? databaseAllergenCodes ?? [] : currentProfile.allergenCodes,
        height: health?.heightCm ?? myPage?.healthStat?.tall ?? currentProfile.height,
        weight: health?.weightKg ?? myPage?.healthStat?.weight ?? currentProfile.weight,
        birthYear: health?.birthYear ? String(health.birthYear) : currentProfile.birthYear,
        gender: health?.gender ?? currentProfile.gender,
        activity: health?.activityLevel ?? currentProfile.activity,
        healthConsent: health?.consent ?? currentProfile.healthConsent,
      };
      const nextGoals: UserGoals = {
        ...currentGoals,
        calories: health?.dailyCalorieTarget ?? currentGoals.calories,
        sugar: health?.dailySugarTargetG ?? currentGoals.sugar,
      };

      window.localStorage.setItem(scopedSettingsKey(USER_PROFILE_KEY, token), JSON.stringify(nextProfile));
      window.localStorage.setItem(scopedSettingsKey(USER_GOALS_KEY, token), JSON.stringify(nextGoals));
      setProfile(nextProfile);
      setGoals(nextGoals);
      notifySettingsChanged();

      if (preferences && preferences.length === 0) {
        const legacyInterests = nextProfile.interests ?? [];
        const legacyAllergens = nextProfile.allergens ?? [];
        if (legacyInterests.length > 0 || legacyAllergens.some((item) => item !== "해당 없음")) {
          void savePreferenceLabelsToServer(token, legacyInterests, legacyAllergens)
            .then((saved) => {
              if (!active) return;
              const allergenCodes = saved.preferences
                .filter((preference) => preference.preferenceType === "ALLERGEN")
                .map((preference) => preference.tagCode)
                .filter((value): value is string => Boolean(value));
              const migratedProfile = { ...readUserProfile(token), allergenCodes };
              window.localStorage.setItem(
                scopedSettingsKey(USER_PROFILE_KEY, token),
                JSON.stringify(migratedProfile),
              );
              setProfile(migratedProfile);
              notifySettingsChanged();
            })
            .catch(() => undefined);
        }
      }
    });

    return () => {
      active = false;
    };
  }, [sessionRevision]);

  const updateProfile = useCallback((patch: Partial<UserProfile>) => {
    saveUserProfile({ ...readUserProfile(), ...patch });
  }, []);

  const updateGoals = useCallback((patch: Partial<UserGoals>) => {
    saveUserGoals({ ...readUserGoals(), ...patch });
  }, []);

  return { ready, profile, goals, updateProfile, updateGoals };
}
