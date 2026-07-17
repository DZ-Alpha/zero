import Link from "next/link";
import { AuthFrame } from "@/components/AuthFrame";
import { OAuthButtons } from "@/components/OAuthButtons";

export default async function Page({
  searchParams,
}: {
  searchParams: Promise<{ oauth?: string }>;
}) {
  const { oauth } = await searchParams;

  return (
    <AuthFrame asideTitle="기록할수록 내 선택이 선명해져요.">
      <div className="auth-card">
        <div className="auth-title"><p className="eyebrow">OAuth 전용 회원가입</p><h1>소셜 계정으로 간단히 시작해요</h1><p>비밀번호를 새로 만들지 않아요. 사용할 계정 하나만 골라주세요.</p></div>
        {oauth === "unavailable" && <p className="auth-service-error" role="alert">가입 서버가 응답하지 않았어요. 잠시 후 다시 시도해 주세요.</p>}
        <OAuthButtons mode="signup" />
        <div className="oauth-safety"><span>✓</span><p><b>이메일과 소셜 식별자만 먼저 받아요.</b><br />건강정보와 관심사는 다음 단계에서 직접 선택할 수 있어요.</p></div>
        <p className="auth-switch">이미 가입했나요? <Link href="/login">로그인</Link></p>
      </div>
    </AuthFrame>
  );
}
