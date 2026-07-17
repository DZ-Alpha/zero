"use client";

import { useCallback, useEffect, useState } from "react";
import { AUTH_CHANGE_EVENT } from "@/hooks/useAuthSession";
import { getAccessToken, readJwtPayload } from "@/lib/api/client";
import { getHealthProfile, getMyPage, updateFirstSet, updateHealthProfile } from "@/lib/api/zerocheck";

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

export type ServerSettingsScope = "profile" | "goals" | "interests";

export async function saveUserSettingsToServer(
  token: string,
  profile: UserProfile,
  goals: UserGoals,
  scope: ServerSettingsScope,
) {
  const requests: Promise<unknown>[] = [];

  if (scope === "profile" || scope === "interests") {
    requests.push(updateFirstSet(token, {
      favoriteCategory: scope === "interests" ? profile.interests ?? [] : undefined,
      optionalAgree: profile.healthConsent,
      tall: scope === "profile" && profile.height ? Math.round(profile.height) : undefined,
      weight: scope === "profile" && profile.weight ? profile.weight : undefined,
      birthday: scope === "profile" ? birthdayForApi(profile) : undefined,
    }));
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

    Promise.allSettled([getMyPage(token), getHealthProfile(token)]).then(([myPageResult, healthResult]) => {
      if (!active) return;
      const currentProfile = readUserProfile(token);
      const currentGoals = readUserGoals(token);
      const tokenPayload = readJwtPayload(token);
      const nickname = typeof tokenPayload?.nickname === "string" ? tokenPayload.nickname : undefined;
      const myPage = myPageResult.status === "fulfilled" ? myPageResult.value : null;
      const health = healthResult.status === "fulfilled" ? healthResult.value : null;

      const nextProfile: UserProfile = {
        ...currentProfile,
        name: nickname || currentProfile.name,
        email: myPage?.email ?? currentProfile.email,
        enabledSns: myPage?.enabledSns ?? currentProfile.enabledSns,
        provider: myPage?.enabledSns?.[0]?.toLowerCase() ?? currentProfile.provider,
        interests: myPage?.favorite?.length ? myPage.favorite : currentProfile.interests,
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
