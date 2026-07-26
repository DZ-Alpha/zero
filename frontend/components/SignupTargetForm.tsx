"use client";

import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { readUserProfile, saveUserGoals } from "@/hooks/useUserSettings";
import { ApiError, getAccessToken } from "@/lib/api/client";
import { updateFirstSet, updateHealthProfile } from "@/lib/api/zerocheck";

type Profile = {
  name: string;
  email?: string;
  birthDate?: string;
  birthYear?: string;
  gender: "여성" | "남성";
  height: number;
  weight: number;
  activity: string;
  interests?: string[];
  allergens?: string[];
  healthConsent?: boolean;
};

const activityFactors: Record<string, number> = {
  "주로 앉아서 생활해요": 1.2,
  "가벼운 운동을 주 1~3회 해요": 1.375,
  "운동을 주 3~5회 해요": 1.55,
  "매일 활발하게 움직여요": 1.725,
};

function roundToTen(value: number) {
  return Math.round(value / 10) * 10;
}

function calculateBmr(profile: Profile) {
  const birthYear = Number(profile.birthDate?.slice(0, 4) ?? profile.birthYear);
  const age = new Date().getFullYear() - birthYear;
  if (profile.gender === "남성") {
    return 88.362 + 13.397 * profile.weight + 4.799 * profile.height - 5.677 * age;
  }
  return 447.593 + 9.247 * profile.weight + 3.098 * profile.height - 4.33 * age;
}

export function SignupTargetForm({ provider }: { provider: string }) {
  const router = useRouter();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [calorieTarget, setCalorieTarget] = useState(2000);
  const [sugarTarget, setSugarTarget] = useState(50);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState("");

  useEffect(() => {
    const nextProfile = readUserProfile() as Profile;
    if (!nextProfile.name) {
      router.replace(`/signup/profile?provider=${provider}`);
      return;
    }

    try {
      const bmr = calculateBmr(nextProfile);
      const maintenance = roundToTen(bmr * (activityFactors[nextProfile.activity] ?? 1.2));
      setProfile(nextProfile);
      setCalorieTarget(maintenance);
      setSugarTarget(Math.round((maintenance * 0.1) / 4));
    } catch {
      router.replace(`/signup/profile?provider=${provider}`);
    }
  }, [provider, router]);

  const estimates = useMemo(() => {
    if (!profile) return null;
    const bmr = roundToTen(calculateBmr(profile));
    const maintenance = roundToTen(bmr * (activityFactors[profile.activity] ?? 1.2));
    const sugarReference = Math.round((maintenance * 0.1) / 4);
    return { bmr, maintenance, sugarReference };
  }, [profile]);

  if (!profile || !estimates) {
    return <div className="target-loading" role="status">입력한 정보를 불러오는 중이에요.</div>;
  }

  const calorieMinimum = Math.max(1000, roundToTen(estimates.maintenance - 900));
  const calorieMaximum = roundToTen(estimates.maintenance + 700);
  const calorieMessage = calorieTarget < estimates.bmr
    ? "기초대사량보다 낮아요. 오래 유지하기보다 전문가와 먼저 상의해 주세요."
    : calorieTarget < estimates.maintenance * 0.8
      ? "감량 폭이 큰 목표예요. 부담이 느껴지면 조금 높여 시작해도 좋아요."
      : calorieTarget < estimates.maintenance * 0.95
        ? "유지 열량보다 조금 낮아요. 천천히 줄여가려는 목표에 가까워요."
        : calorieTarget <= estimates.maintenance * 1.05
          ? "현재 활동량을 기준으로 체중 유지에 가까운 목표예요."
          : "유지 열량보다 높아요. 체중 관리가 목표라면 조금 낮춰보세요.";

  const sugarMessage = sugarTarget < estimates.sugarReference * 0.55
    ? "꽤 낮은 목표예요. 처음부터 무리하기보다 조금씩 낮춰도 괜찮아요."
    : sugarTarget <= estimates.sugarReference
      ? "하루 열량의 10% 안쪽을 참고해 잡은 목표예요."
      : sugarTarget <= estimates.sugarReference * 1.2
        ? "참고값과 가까워요. 평소 식습관에 맞춰 시작해 보세요."
        : "참고값보다 높아요. 당류를 줄이고 싶다면 조금 낮춰보세요.";

  async function completeSignup() {
    if (!estimates || !profile) return;
    setSaving(true);
    setSaveError("");

    const token = getAccessToken();
    if (!token) {
      setSaveError("로그인 정보를 확인하지 못했어요. 소셜 로그인을 다시 시작해 주세요.");
      setSaving(false);
      return;
    }

    try {
      const birthday = profile.birthDate?.length === 8
        ? `${profile.birthDate.slice(0, 4)}-${profile.birthDate.slice(4, 6)}-${profile.birthDate.slice(6)}`
        : undefined;
      const baseRequest = updateFirstSet(token, {
        email: profile.email?.trim() || undefined,
        favoriteCategory: profile.interests,
        isAllergic: Boolean(profile.allergens?.length && !profile.allergens.includes("해당 없음")),
        optionalAgree: Boolean(profile.healthConsent),
        tall: profile.healthConsent ? profile.height : undefined,
        weight: profile.healthConsent ? profile.weight : undefined,
        birthday: profile.healthConsent ? birthday : undefined,
      });
      const healthRequest = profile.healthConsent
        ? updateHealthProfile(token, {
            consent: true,
            birthYear: Number(profile.birthDate?.slice(0, 4) ?? profile.birthYear),
            gender: profile.gender,
            heightCm: profile.height,
            weightKg: profile.weight,
            activityLevel: profile.activity,
            healthGoal: "BALANCE",
            dailyCalorieTarget: calorieTarget,
            dailySugarTargetG: sugarTarget,
          })
        : Promise.resolve(null);
      await Promise.all([baseRequest, healthRequest]);
      saveUserGoals({
        calories: calorieTarget,
        sugar: sugarTarget,
        maintenanceCalories: estimates.maintenance,
        bmr: estimates.bmr,
      });
      router.push(`/signup/success?provider=${provider}`);
    } catch (error) {
      setSaveError(error instanceof ApiError && error.status === 409
        ? "이미 다른 계정에서 쓰고 있는 이메일이에요. 이전 화면에서 다른 이메일을 입력해 주세요."
        : "정보를 서버에 저장하지 못했어요. 연결을 확인한 뒤 다시 저장해 주세요.");
      setSaving(false);
    }
  }

  return (
    <div className="target-form-shell">
      <div className="target-form-title">
        <p className="eyebrow">하루 목표 설정</p>
        <h1>{profile.name}님에게 맞는<br />시작점을 계산했어요.</h1>
        <p>계산값을 그대로 써도 되고, 생활 방식에 맞게 조정해도 괜찮아요.</p>
      </div>

      <div className="target-reference">
        <div><span>예상 기초대사량</span><strong>{estimates.bmr.toLocaleString()}kcal</strong></div>
        <div><span>현재 활동량을 더한 유지 열량</span><strong>{estimates.maintenance.toLocaleString()}kcal</strong></div>
      </div>

      <section className="target-control calorie-target">
        <header><div><span>하루 칼로리</span><small>계산한 시작점 {estimates.maintenance.toLocaleString()}kcal</small></div><strong>{calorieTarget.toLocaleString()}<i>kcal</i></strong></header>
        <input
          type="range"
          min={calorieMinimum}
          max={calorieMaximum}
          step="10"
          value={calorieTarget}
          onChange={(event) => setCalorieTarget(Number(event.target.value))}
          aria-label="하루 칼로리 목표"
          style={{ "--range-progress": `${((calorieTarget - calorieMinimum) / (calorieMaximum - calorieMinimum)) * 100}%` } as React.CSSProperties}
        />
        <p>{calorieMessage}</p>
      </section>

      <section className="target-control sugar-target">
        <header><div><span>하루 당류</span><small>열량의 10%로 계산한 참고값 {estimates.sugarReference}g</small></div><strong>{sugarTarget}<i>g</i></strong></header>
        <input
          type="range"
          min="15"
          max={Math.max(90, estimates.sugarReference + 35)}
          step="1"
          value={sugarTarget}
          onChange={(event) => setSugarTarget(Number(event.target.value))}
          aria-label="하루 당류 목표"
          style={{ "--range-progress": `${((sugarTarget - 15) / (Math.max(90, estimates.sugarReference + 35) - 15)) * 100}%` } as React.CSSProperties}
        />
        <p>{sugarMessage}</p>
      </section>

      <p className="target-note">당류 목표는 영양성분표의 ‘당류’를 기록하기 위한 개인 기준이에요. 세계보건기구가 안내하는 ‘유리당’과는 범위가 다를 수 있어요.</p>

      {saveError && <div className="settings-editor-message is-error" role="alert"><p>{saveError}</p></div>}

      <footer className="signup-actions target-actions">
        <button type="button" className="auth-secondary" onClick={() => router.back()}>이전</button>
        <button type="button" className="auth-primary" onClick={completeSignup} disabled={saving}>{saving ? "목표를 저장하고 있어요" : "이 목표로 시작하기"}</button>
      </footer>
    </div>
  );
}
