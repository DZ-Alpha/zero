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
    <AuthFrame asideTitle="기록하면 선택이 쉬워져요.">
      <div className="auth-card">
        <div className="auth-title"><p className="eyebrow">간편 회원가입</p><h1>소셜 계정으로 간단히 시작해요</h1></div>
        {oauth === "unavailable" && <p className="auth-service-error" role="alert">가입 서버가 응답하지 않았어요. 잠시 후 다시 시도해 주세요.</p>}
        <OAuthButtons mode="signup" />
        <div className="oauth-safety"><span>✓</span><p><b>가입에 필요한 기본 정보만 받아요.</b></p></div>
        <p className="auth-switch">이미 가입했나요? <Link href="/login">로그인</Link></p>
      </div>
    </AuthFrame>
  );
}
