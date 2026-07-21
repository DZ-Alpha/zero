"use client";

import Link from "next/link";
import { useState } from "react";
import { ConfirmDialog } from "@/components/SystemFeedback";
import { useAuthSession } from "@/hooks/useAuthSession";
import { AUTH_CHANGE_EVENT, AUTH_KEY, LEGACY_AUTH_KEY } from "@/hooks/useAuthSession";
import { saveUserSettingsToServer, UserGoals, UserProfile, useUserSettings } from "@/hooks/useUserSettings";
import { ApiError, clearAccessToken } from "@/lib/api/client";
import { deleteAccount, unlinkSocialAccount } from "@/lib/api/zerocheck";

type Editor = "profile" | "goals" | "interests" | "allergens" | "notifications";

const interestOptions = ["제로슈거", "저당", "저칼로리", "고단백", "간편식", "저당 레시피"];
const allergenOptions = ["우유", "대두", "땅콩", "견과류", "밀", "달걀", "갑각류"];
const providerNames: Record<string, string> = { google: "Google", kakao: "카카오", naver: "NAVER", apple: "Apple" };
// 백엔드 SOCIAL_CODES(NA/KA/GL/AP/ADM) ↔ provider 경로 매핑
const snsByCode: Record<string, { provider: string; label: string }> = {
  NA: { provider: "naver", label: "NAVER" },
  KA: { provider: "kakao", label: "카카오" },
  GL: { provider: "google", label: "Google" },
  AP: { provider: "apple", label: "Apple" },
  ADM: { provider: "admin", label: "관리자" },
};

function digits(value = "") {
  return value.replace(/\D/g, "").slice(0, 8);
}

function formatBirthDate(value = "") {
  const valueDigits = digits(value);
  if (valueDigits.length <= 4) return valueDigits;
  if (valueDigits.length <= 6) return `${valueDigits.slice(0, 4)}.${valueDigits.slice(4)}`;
  return `${valueDigits.slice(0, 4)}.${valueDigits.slice(4, 6)}.${valueDigits.slice(6)}`;
}

function calculateAge(profile: UserProfile) {
  const birth = digits(profile.birthDate || profile.birthYear);
  if (birth.length < 4) return null;
  const today = new Date();
  let age = today.getFullYear() - Number(birth.slice(0, 4));
  if (birth.length === 8) {
    const month = Number(birth.slice(4, 6));
    const day = Number(birth.slice(6, 8));
    if (today.getMonth() + 1 < month || (today.getMonth() + 1 === month && today.getDate() < day)) age -= 1;
  }
  return age;
}

export function PersonalPage() {
  const { ready: authReady, signedIn, token } = useAuthSession();
  const { ready: settingsReady, profile, goals, updateProfile, updateGoals } = useUserSettings();
  const [editor, setEditor] = useState<Editor | null>(null);
  const [profileDraft, setProfileDraft] = useState<UserProfile>({});
  const [goalsDraft, setGoalsDraft] = useState<UserGoals>(goals);
  const [selectionDraft, setSelectionDraft] = useState<string[]>([]);
  const [notificationDraft, setNotificationDraft] = useState({ newProducts: true, weeklyReport: true });
  const [message, setMessage] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveFailed, setSaveFailed] = useState(false);
  const [confirmingWithdrawal, setConfirmingWithdrawal] = useState(false);
  const [withdrawing, setWithdrawing] = useState(false);
  const [unlinkTarget, setUnlinkTarget] = useState<string | null>(null);
  const [unlinking, setUnlinking] = useState(false);

  if (!authReady || !settingsReady) {
    return <main className="personal-page page-wrap"><div className="mypage-auth-loading wrap" aria-label="계정 확인 중" /></main>;
  }

  if (!signedIn) {
    return (
      <main className="personal-page page-wrap">
        <section className="mypage-auth-gate wrap">
          <div className="mypage-gate-symbol" aria-hidden="true">
            <svg viewBox="0 0 32 32"><circle cx="16" cy="11" r="5" /><path d="M7 27c.8-6.1 3.8-9.1 9-9.1s8.2 3 9 9.1" /></svg>
          </div>
          <p className="eyebrow">회원 전용</p>
          <h1>마이페이지는<br />로그인 후 볼 수 있어요.</h1>
          <p>하루 목표, 관심 기준과 저장한 메뉴는 계정에 안전하게 이어서 보관해요.</p>
          <div className="mypage-gate-actions"><Link href="/login">로그인하기</Link><Link href="/signup">회원가입하기</Link></div>
          <small>메인 화면은 로그인하지 않아도 기본 기록으로 미리 볼 수 있어요.</small>
        </section>
      </main>
    );
  }

  const name = profile.name?.trim() || "사용자";
  const age = calculateAge(profile);
  const interests = profile.interests ?? [];
  const allergens = profile.allergens ?? [];
  const notifications = profile.notifications ?? { newProducts: true, weeklyReport: true };

  function openEditor(nextEditor: Editor) {
    setEditor(nextEditor);
    setMessage("");
    setProfileDraft({ ...profile });
    setGoalsDraft({ ...goals });
    setSelectionDraft(nextEditor === "interests" ? interests : allergens);
    setNotificationDraft({ ...notifications });
  }

  function toggleSelection(value: string) {
    setSelectionDraft((current) => current.includes(value) ? current.filter((item) => item !== value) : [...current, value]);
  }

  async function saveEditor() {
    if (!editor) return;
    setSaving(true);
    setMessage("");
    setSaveFailed(false);

    try {
      if (editor === "profile") {
        const patch: Partial<UserProfile> = {
        name: profileDraft.name?.trim() || profile.name,
        birthDate: digits(profileDraft.birthDate),
        birthYear: digits(profileDraft.birthDate || profileDraft.birthYear).slice(0, 4),
        gender: profileDraft.gender,
        height: Number(profileDraft.height) || undefined,
        weight: Number(profileDraft.weight) || undefined,
        activity: profileDraft.activity,
        };
        const nextProfile = { ...profile, ...patch };
        if (token) await saveUserSettingsToServer(token, nextProfile, goals, "profile");
        updateProfile(patch);
        setMessage(token ? "기본 정보를 저장했어요." : "이 기기에 기본 정보를 저장했어요.");
      }
      if (editor === "goals") {
        const patch = { sugar: Math.max(1, Number(goalsDraft.sugar)), calories: Math.max(500, Number(goalsDraft.calories)) };
        const nextGoals = { ...goals, ...patch };
        if (token && profile.healthConsent) await saveUserSettingsToServer(token, profile, nextGoals, "goals");
        updateGoals(patch);
        setMessage(token && profile.healthConsent
          ? "하루 목표를 저장했어요. 홈과 상품 분석에도 바로 반영돼요."
          : "하루 목표를 이 기기에 저장했어요. 건강정보 저장에 동의하면 다른 기기에서도 같은 목표를 사용할 수 있어요.");
      }
      if (editor === "interests") {
        const nextProfile = { ...profile, interests: selectionDraft };
        if (token) await saveUserSettingsToServer(token, nextProfile, goals, "interests");
        updateProfile({ interests: selectionDraft });
        setMessage(token ? "관심 기준을 저장했어요." : "이 기기에 관심 기준을 저장했어요.");
      }
      if (editor === "allergens") {
        updateProfile({ allergens: selectionDraft });
        setMessage("주의 성분은 이 기기에 저장했어요. 서버 저장 기능은 준비 중이에요.");
      }
      if (editor === "notifications") {
        updateProfile({ notifications: notificationDraft });
        setMessage("알림 설정은 이 기기에 저장했어요. 서버 저장 기능은 준비 중이에요.");
      }
      setEditor(null);
    } catch {
      setMessage("서버에 저장하지 못했어요. 연결을 확인한 뒤 다시 시도해 주세요.");
      setSaveFailed(true);
    } finally {
      setSaving(false);
    }
  }

  const providerName = providerNames[profile.provider ?? ""] ?? "소셜";
  const connectedSns = (profile.enabledSns ?? [])
    .map((code) => ({ code, ...snsByCode[code] }))
    .filter((item): item is { code: string; provider: string; label: string } => Boolean(item.provider) && item.provider !== "admin");

  async function unlinkSns() {
    if (!token || !unlinkTarget) return;
    const target = snsByCode[unlinkTarget];
    if (!target) return;
    setUnlinking(true);
    try {
      const result = await unlinkSocialAccount(token, target.provider);
      updateProfile({ enabledSns: result.enabledSns });
      setMessage(`${target.label} 연결을 해제했어요.`);
      setUnlinkTarget(null);
    } catch (error) {
      setUnlinkTarget(null);
      setMessage(error instanceof ApiError && error.status === 409
        ? "마지막으로 남은 로그인 수단은 해제할 수 없어요."
        : "연결 해제를 처리하지 못했어요. 잠시 후 다시 시도해 주세요.");
    } finally {
      setUnlinking(false);
    }
  }

  async function withdrawAccount() {
    if (!token) {
      setConfirmingWithdrawal(false);
      setMessage("로그인 정보를 확인할 수 없어요. 다시 로그인한 뒤 탈퇴를 진행해 주세요.");
      return;
    }
    setWithdrawing(true);
    try {
      await deleteAccount(token);
      window.localStorage.removeItem(AUTH_KEY);
      window.localStorage.removeItem(LEGACY_AUTH_KEY);
      clearAccessToken();
      window.dispatchEvent(new Event(AUTH_CHANGE_EVENT));
      window.location.replace("/?accountDeleted=true");
    } catch {
      setConfirmingWithdrawal(false);
      setMessage("회원 탈퇴를 처리하지 못했어요. 잠시 후 다시 시도해 주세요.");
    } finally {
      setWithdrawing(false);
    }
  }

  return (
    <main className="personal-page page-wrap">
      <section className="page-intro wrap">
        <p className="eyebrow">마이 당당</p>
        <h1>{name}님의 기준을<br />한곳에서 관리해요.</h1>
        <p>여기에서 바꾼 목표와 관심 기준은 홈, 식단 기록과 상품 안내에 함께 반영돼요.</p>
      </section>

      <section className="profile-summary wrap">
        <div className="profile-person"><span>{name.slice(0, 1)}</span><div><small>{providerName} 계정으로 연결했어요</small><h2>{name}</h2><p>연결된 이름은 계정에서, 나머지 정보는 여기에서 관리해요.</p></div><button type="button" onClick={() => openEditor("profile")}>기본 정보 바꾸기</button></div>
        <div className="profile-goal"><p className="eyebrow">현재 하루 목표</p><div><span>당류</span><strong>{goals.sugar}g</strong></div><div><span>칼로리</span><strong>{goals.calories.toLocaleString()}kcal</strong></div><button type="button" className="profile-goal-edit" onClick={() => openEditor("goals")}>목표 바꾸기</button></div>
      </section>

      {message && <p className="settings-save-message wrap" role="status">{message}</p>}

      <section className="settings-list wrap">
        <article><header><div><span>01</span><h2>신체와 활동 정보</h2></div><button type="button" onClick={() => openEditor("profile")}>정보 바꾸기</button></header><dl><div><dt>나이</dt><dd>{age === null ? "미입력" : `${age}세`}</dd></div><div><dt>성별</dt><dd>{profile.gender || "미입력"}</dd></div><div><dt>키</dt><dd>{profile.height ? `${profile.height}cm` : "미입력"}</dd></div><div><dt>몸무게</dt><dd>{profile.weight ? `${profile.weight}kg` : "미입력"}</dd></div><div><dt>활동량</dt><dd>{profile.activity || "미입력"}</dd></div></dl></article>
        <article><header><div><span>02</span><h2>관심 있는 기준</h2></div><button type="button" onClick={() => openEditor("interests")}>기준 바꾸기</button></header>{interests.length > 0 ? <div className="setting-tags">{interests.map((item) => <span key={item}>{item}</span>)}</div> : <p className="setting-empty">아직 고른 기준이 없어요.</p>}<p>식품과 레시피를 추천할 때 이 기준을 먼저 살펴봐요.</p></article>
        <article><header><div><span>03</span><h2>주의할 성분</h2></div><button type="button" onClick={() => openEditor("allergens")}>성분 바꾸기</button></header>{allergens.length > 0 ? <div className="setting-tags warning">{allergens.map((item) => <span key={item}>{item}</span>)}</div> : <p className="setting-empty">등록한 주의 성분이 없어요.</p>}<p>식품과 사진 분석 결과에 이 성분이 있으면 먼저 알려드려요.</p></article>
        <article><header><div><span>04</span><h2>계정과 알림</h2></div><button type="button" onClick={() => openEditor("notifications")}>알림 바꾸기</button></header><dl><div><dt>연결 계정</dt><dd>{connectedSns.length > 0 ? connectedSns.map((item) => item.label).join(", ") : providerName}</dd></div><div><dt>신제품 알림</dt><dd>{notifications.newProducts ? "받기" : "받지 않기"}</dd></div><div><dt>주간 리포트</dt><dd>{notifications.weeklyReport ? "일요일에 받기" : "받지 않기"}</dd></div></dl>{connectedSns.length > 0 && <div className="sns-manage">{connectedSns.map((item) => <span key={item.code}>{item.label}<button type="button" onClick={() => setUnlinkTarget(item.code)} disabled={unlinking || connectedSns.length === 1}>해제</button></span>)}<small>{connectedSns.length === 1 ? "마지막 로그인 수단은 해제할 수 없어요." : "연결을 해제해도 계정 정보는 유지돼요."}</small></div>}</article>
      </section>

      <section className="profile-links wrap"><Link href="/diet"><span>내 월간 리포트</span><b>캘린더에서 보기 →</b></Link><Link href="/recipes"><span>저장한 레시피와 식품</span><b>즐겨찾기 보기 →</b></Link></section>
      <section className="account-danger-zone wrap"><div><h2>계정 관리</h2><p>탈퇴하면 연결된 계정과 저장한 사용자 정보를 되돌릴 수 없어요.</p></div><button type="button" onClick={() => setConfirmingWithdrawal(true)}>회원 탈퇴</button></section>

      {editor && (
        <div className="settings-editor-backdrop" role="presentation" onMouseDown={() => setEditor(null)}>
          <section className="settings-editor" role="dialog" aria-modal="true" aria-label="마이페이지 설정 바꾸기" onMouseDown={(event) => event.stopPropagation()}>
            <header><div><p className="eyebrow">마이페이지 설정</p><h2>{editor === "profile" ? "기본 정보 바꾸기" : editor === "goals" ? "하루 목표 바꾸기" : editor === "interests" ? "관심 기준 바꾸기" : editor === "allergens" ? "주의할 성분 바꾸기" : "알림 바꾸기"}</h2></div><button type="button" onClick={() => setEditor(null)} aria-label="닫기">×</button></header>

            {editor === "profile" && (
              <div className="settings-editor-fields">
                <label><span>이름 또는 닉네임</span><input value={profileDraft.name ?? ""} onChange={(event) => setProfileDraft((current) => ({ ...current, name: event.target.value }))} /><small>마이페이지에서 언제든 바꿀 수 있어요.</small></label>
                <label><span>생년월일</span><input value={formatBirthDate(profileDraft.birthDate || profileDraft.birthYear)} onChange={(event) => setProfileDraft((current) => ({ ...current, birthDate: digits(event.target.value) }))} inputMode="numeric" placeholder="예: 20001006" readOnly={profile.birthDateLocked} />{profile.birthDateLocked && <small>소셜 계정에서 불러온 생년월일이에요.</small>}</label>
                <label><span>성별</span><select value={profileDraft.gender ?? ""} onChange={(event) => setProfileDraft((current) => ({ ...current, gender: event.target.value }))}><option value="">골라주세요</option><option>여성</option><option>남성</option></select></label>
                <label><span>키</span><div className="unit-input"><input value={profileDraft.height ?? ""} onChange={(event) => setProfileDraft((current) => ({ ...current, height: Number(event.target.value) }))} inputMode="decimal" /><b>cm</b></div></label>
                <label><span>몸무게</span><div className="unit-input"><input value={profileDraft.weight ?? ""} onChange={(event) => setProfileDraft((current) => ({ ...current, weight: Number(event.target.value) }))} inputMode="decimal" /><b>kg</b></div></label>
                <label className="full"><span>평소 활동량</span><select value={profileDraft.activity ?? ""} onChange={(event) => setProfileDraft((current) => ({ ...current, activity: event.target.value }))}><option value="">골라주세요</option><option>주로 앉아서 생활해요</option><option>가벼운 운동을 주 1~3회 해요</option><option>운동을 주 3~5회 해요</option><option>매일 활발하게 움직여요</option></select></label>
              </div>
            )}

            {editor === "goals" && (
              <div className="settings-goal-editor">
                <label><span>하루 당류</span><div><input type="number" min="1" max="150" value={goalsDraft.sugar} onChange={(event) => setGoalsDraft((current) => ({ ...current, sugar: Number(event.target.value) }))} /><b>g</b></div></label>
                <label><span>하루 칼로리</span><div><input type="number" min="500" max="5000" step="10" value={goalsDraft.calories} onChange={(event) => setGoalsDraft((current) => ({ ...current, calories: Number(event.target.value) }))} /><b>kcal</b></div></label>
                <p>바꾼 값은 오늘 게이지와 상품을 더했을 때의 예상 수치에 바로 사용돼요.</p>
              </div>
            )}

            {(editor === "interests" || editor === "allergens") && (
              <div className={`settings-choice-grid ${editor === "allergens" ? "is-warning" : ""}`}>
                {(editor === "interests" ? interestOptions : allergenOptions).map((item) => <button type="button" className={selectionDraft.includes(item) ? "is-selected" : ""} onClick={() => toggleSelection(item)} key={item}>{item}</button>)}
              </div>
            )}

            {editor === "notifications" && (
              <div className="settings-notification-list">
                <label><span><b>관심 카테고리 신제품</b><small>새 제품이 등록되면 알려드려요.</small></span><input type="checkbox" checked={notificationDraft.newProducts} onChange={(event) => setNotificationDraft((current) => ({ ...current, newProducts: event.target.checked }))} /></label>
                <label><span><b>주간 식단 리포트</b><small>일주일의 기록을 일요일에 정리해드려요.</small></span><input type="checkbox" checked={notificationDraft.weeklyReport} onChange={(event) => setNotificationDraft((current) => ({ ...current, weeklyReport: event.target.checked }))} /></label>
              </div>
            )}

            {message && <div className={`settings-editor-message ${saveFailed ? "is-error" : ""}`} role={saveFailed ? "alert" : "status"}><p>{message}</p>{saveFailed && <button type="button" onClick={saveEditor} disabled={saving}>다시 저장하기</button>}</div>}
            <footer><button type="button" onClick={() => setEditor(null)} disabled={saving}>취소</button><button type="button" onClick={saveEditor} disabled={saving}>{saving ? "저장하고 있어요" : "바꾼 내용 저장하기"}</button></footer>
          </section>
        </div>
      )}
      {confirmingWithdrawal && <ConfirmDialog title="정말 회원 탈퇴할까요?" description="식단 기록, 하루 목표와 관심 기준이 모두 삭제돼요. 삭제한 정보는 다시 복구할 수 없어요." confirmLabel="회원 탈퇴하기" destructive busy={withdrawing} onClose={() => setConfirmingWithdrawal(false)} onConfirm={withdrawAccount} />}
      {unlinkTarget && <ConfirmDialog title={`${snsByCode[unlinkTarget]?.label ?? "SNS"} 연결을 해제할까요?`} description="해제한 SNS로는 더 이상 로그인할 수 없어요. 다른 로그인 수단이 남아 있는지 확인해 주세요." confirmLabel="연결 해제하기" destructive busy={unlinking} onClose={() => setUnlinkTarget(null)} onConfirm={unlinkSns} />}
    </main>
  );
}
