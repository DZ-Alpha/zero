"use client";

import { useRouter } from "next/navigation";
import Link from "next/link";
import { useMemo, useState } from "react";
import { HEALTH_LABELS } from "@/data/taxonomy";
import { saveUserProfile } from "@/hooks/useUserSettings";

const providerNames: Record<string, string> = { google: "Google", kakao: "카카오", naver: "NAVER", apple: "Apple" };
const interests = [...HEALTH_LABELS];
const allergens = ["우유", "대두", "땅콩", "호두", "밀", "난류", "새우", "게", "복숭아", "토마토", "해당 없음"];

export type OAuthSignupProfile = {
  name?: string;
  birthDate?: string;
  email?: string;
};

function isValidEmail(value: string) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value.trim());
}

function birthDateDigits(value = "") {
  return value.replace(/\D/g, "").slice(0, 8);
}

function formatBirthDate(value: string) {
  const digits = birthDateDigits(value);
  if (digits.length <= 4) return digits;
  if (digits.length <= 6) return `${digits.slice(0, 4)}.${digits.slice(4)}`;
  return `${digits.slice(0, 4)}.${digits.slice(4, 6)}.${digits.slice(6)}`;
}

function birthDateToIso(value: string) {
  const digits = birthDateDigits(value);
  if (digits.length !== 8) return "";
  return `${digits.slice(0, 4)}-${digits.slice(4, 6)}-${digits.slice(6)}`;
}

function isValidBirthDate(value: string) {
  const iso = birthDateToIso(value);
  if (!iso) return false;
  const [year, month, day] = iso.split("-").map(Number);
  const date = new Date(year, month - 1, day);
  const today = new Date();
  return year >= 1900
    && date.getFullYear() === year
    && date.getMonth() === month - 1
    && date.getDate() === day
    && date <= today;
}

export function SignupProfileForm({ provider, oauthProfile = {} }: { provider: string; oauthProfile?: OAuthSignupProfile }) {
  const router = useRouter();
  const [step, setStep] = useState(1);
  const [name, setName] = useState(oauthProfile.name?.trim() ?? "");
  const [email, setEmail] = useState(oauthProfile.email?.trim() ?? "");
  const [birthDate, setBirthDate] = useState(birthDateDigits(oauthProfile.birthDate));
  const [activity, setActivity] = useState("");
  const [gender, setGender] = useState("");
  const [height, setHeight] = useState("");
  const [weight, setWeight] = useState("");
  const [selectedInterests, setSelectedInterests] = useState<string[]>(["저당"]);
  const [selectedAllergens, setSelectedAllergens] = useState<string[]>([]);
  const [consents, setConsents] = useState({ age: false, terms: false, privacy: false, health: false, marketing: false });
  const [attempted, setAttempted] = useState(false);
  const providerName = providerNames[provider] ?? "소셜";
  const nameLocked = Boolean(oauthProfile.name?.trim());
  const birthDateLocked = isValidBirthDate(birthDateDigits(oauthProfile.birthDate));

  const canContinue = useMemo(() => {
    if (step === 1) {
      const validHeight = Number(height) >= 120 && Number(height) <= 230;
      const validWeight = Number(weight) >= 30 && Number(weight) <= 250;
      return name.trim().length >= 2 && isValidEmail(email) && isValidBirthDate(birthDate) && Boolean(activity) && Boolean(gender) && validHeight && validWeight;
    }
    if (step === 2) return selectedInterests.length > 0;
    return consents.age && consents.terms && consents.privacy;
  }, [activity, birthDate, consents, email, gender, height, name, selectedInterests.length, step, weight]);

  const validationMessage = useMemo(() => {
    if (step === 1) {
      if (name.trim().length < 2) return "사용할 이름이나 닉네임을 두 글자 이상 입력해 주세요.";
      if (!isValidEmail(email)) return "이메일 주소를 확인해 주세요.";
      if (!isValidBirthDate(birthDate)) return "생년월일 8자리를 확인해 주세요.";
      if (!gender) return "성별을 골라주세요.";
      if (!(Number(height) >= 120 && Number(height) <= 230)) return "키는 120~230cm 사이로 입력해 주세요.";
      if (!(Number(weight) >= 30 && Number(weight) <= 250)) return "몸무게는 30~250kg 사이로 입력해 주세요.";
      if (!activity) return "평소 활동량을 골라주세요.";
    }
    if (step === 2 && selectedInterests.length === 0) return "관심 기준을 하나 이상 골라주세요.";
    if (step === 3 && !(consents.age && consents.terms && consents.privacy)) return "필수 동의 세 가지를 확인해 주세요.";
    return "";
  }, [activity, birthDate, consents, email, gender, height, name, selectedInterests.length, step, weight]);

  function toggle(list: string[], setList: (value: string[]) => void, value: string) {
    if (value === "해당 없음") return setList(list.includes(value) ? [] : [value]);
    const withoutNone = list.filter((item) => item !== "해당 없음");
    setList(withoutNone.includes(value) ? withoutNone.filter((item) => item !== value) : [...withoutNone, value]);
  }

  function next() {
    if (!canContinue) {
      setAttempted(true);
      return;
    }
    setAttempted(false);
    if (step < 3) setStep((current) => current + 1);
    else {
      saveUserProfile({
        name: name.trim(),
        email: email.trim(),
        birthDate,
        birthYear: birthDate.slice(0, 4),
        gender,
        height: Number(height),
        weight: Number(weight),
        activity,
        interests: selectedInterests,
        allergens: selectedAllergens,
        provider,
        nameLocked,
        birthDateLocked,
        healthConsent: consents.health,
        marketingConsent: consents.marketing,
      });
      router.push(`/signup/targets?provider=${provider}`);
    }
  }

  const allChecked = Object.values(consents).every(Boolean);

  return (
    <div className="signup-form-shell">
      <div className="signup-progress" aria-label={`가입 ${step}/3단계`}><span style={{ transform: `scaleX(${step / 3})` }} /></div>
      <div className="signup-step-meta"><span>{providerName} 계정 연결됨</span><b>{step} / 3</b></div>

      <div className="signup-step" key={step}>
        {step === 1 && (
          <>
            <div className="auth-title"><p className="eyebrow">기본 정보</p><h1>어떻게 불러드릴까요?</h1><p>소셜 계정에서 받지 못한 정보만 직접 입력해 주세요. 하루 목표를 계산할 때 사용해요.</p></div>
            <div className="form-grid">
              <label className={`full oauth-profile-field ${nameLocked ? "is-locked" : ""}`}><span>이름 또는 닉네임 {nameLocked && <i>소셜 계정 정보</i>}</span><input value={name} onChange={(event) => setName(event.target.value)} placeholder="예: 지은" autoFocus={!nameLocked} readOnly={nameLocked} /><small className="oauth-field-note">{nameLocked ? `${providerName}에서 불러왔어요. 연결 계정의 정보와 같게 유지돼요.` : `${providerName}에서 이름을 받지 못했어요. 사용할 이름을 입력해 주세요.`}</small></label>
              <label className="full"><span>이메일</span><input type="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="예: dangdang@example.com" /><small className="oauth-field-note">중요한 안내를 받을 이메일이에요. 마이페이지에서 언제든 바꿀 수 있어요.</small></label>
              <label className={`oauth-profile-field ${birthDateLocked ? "is-locked" : ""}`}><span>생년월일 {birthDateLocked && <i>소셜 계정 정보</i>}</span><div className="birthdate-control"><input value={formatBirthDate(birthDate)} onChange={(event) => setBirthDate(birthDateDigits(event.target.value))} inputMode="numeric" placeholder="예: 20001006" readOnly={birthDateLocked} aria-describedby="birthdate-help" />{!birthDateLocked && <><input className="birthdate-picker" type="date" min="1900-01-01" max={new Date().toISOString().slice(0, 10)} value={birthDateToIso(birthDate)} onChange={(event) => setBirthDate(birthDateDigits(event.target.value))} aria-label="달력에서 생년월일 선택" /><b aria-hidden="true">달력</b></>}</div><small className="oauth-field-note" id="birthdate-help">{birthDateLocked ? `${providerName}에서 불러왔어요. 이 화면에서는 바꿀 수 없어요.` : "숫자 8자리를 입력하거나 달력에서 골라주세요."}</small></label>
              <label><span>성별</span><select value={gender} onChange={(event) => setGender(event.target.value)}><option value="">골라주세요</option><option>여성</option><option>남성</option></select></label>
              <label><span>키</span><div className="unit-input"><input value={height} onChange={(event) => setHeight(event.target.value.replace(/[^\d.]/g, ""))} inputMode="decimal" placeholder="165" /><b>cm</b></div></label>
              <label><span>몸무게</span><div className="unit-input"><input value={weight} onChange={(event) => setWeight(event.target.value.replace(/[^\d.]/g, ""))} inputMode="decimal" placeholder="55" /><b>kg</b></div></label>
              <label className="full"><span>평소 활동량</span><select value={activity} onChange={(event) => setActivity(event.target.value)}><option value="">골라주세요</option><option>주로 앉아서 생활해요</option><option>가벼운 운동을 주 1~3회 해요</option><option>운동을 주 3~5회 해요</option><option>매일 활발하게 움직여요</option></select></label>
            </div>
          </>
        )}

        {step === 2 && (
          <>
            <div className="auth-title"><p className="eyebrow">관심사와 주의 성분</p><h1>무엇을 더 자주 볼까요?</h1><p>관심사는 하나 이상 골라주세요. 주의 성분은 나중에 마이페이지에서도 바꿀 수 있어요.</p></div>
            <fieldset className="choice-field"><legend>관심 카테고리</legend><div>{interests.map((item) => <button type="button" className={selectedInterests.includes(item) ? "is-selected" : ""} onClick={() => toggle(selectedInterests, setSelectedInterests, item)} key={item}><i />{item}</button>)}</div></fieldset>
            <fieldset className="choice-field warning"><legend>주의할 알레르기 성분 <span>선택</span></legend><div>{allergens.map((item) => <button type="button" className={selectedAllergens.includes(item) ? "is-selected" : ""} onClick={() => toggle(selectedAllergens, setSelectedAllergens, item)} key={item}><i />{item}</button>)}</div></fieldset>
            <p className="form-help">알레르기 정보는 제품을 거르는 데 도움을 주지만, 의료 판단을 대신하지 않아요. 제품 포장지도 꼭 확인해 주세요.</p>
          </>
        )}

        {step === 3 && (
          <>
            <div className="auth-title"><p className="eyebrow">약관 동의</p><h1>마지막으로 확인해 주세요</h1><p>서비스 이용에 꼭 필요한 동의와 선택 동의를 나눠서 보여드려요.</p></div>
            <div className="consent-list">
              <label className="consent-all"><input type="checkbox" checked={allChecked} onChange={(event) => setConsents({ age: event.target.checked, terms: event.target.checked, privacy: event.target.checked, health: event.target.checked, marketing: event.target.checked })} /><span><i />모두 동의하기</span></label>
              {([
                ["age", "[필수] 만 14세 이상이에요"],
                ["terms", "[필수] 서비스 이용약관에 동의해요"],
                ["privacy", "[필수] 개인정보 수집·이용에 동의해요"],
                ["health", "[선택] 건강정보를 맞춤 분석에 활용해도 좋아요"],
                ["marketing", "[선택] 새 제품과 레시피 소식을 받을게요"],
              ] as const).map(([key, label]) => <label key={key}><input type="checkbox" checked={consents[key]} onChange={(event) => setConsents((current) => ({ ...current, [key]: event.target.checked }))} /><span><i />{label}</span>{key === "terms" && <Link href="/terms" target="_blank">보기</Link>}{key === "privacy" && <Link href="/privacy" target="_blank">보기</Link>}</label>)}
            </div>
            <p className="form-help">선택 동의는 하지 않아도 가입할 수 있어요. 동의 내용은 마이페이지에서 언제든 바꿀 수 있어요.</p>
          </>
        )}
      </div>

      <footer className="signup-actions">
        {step > 1 ? <button type="button" className="auth-secondary" onClick={() => setStep((current) => current - 1)}>이전</button> : <span />}
        <div className="signup-next-action">
          {attempted && validationMessage && <p role="alert">{validationMessage}</p>}
          <button type="button" className="auth-primary" aria-disabled={!canContinue} onClick={next}>{step === 3 ? "하루 목표 설정하기" : "다음"}</button>
        </div>
      </footer>
    </div>
  );
}
