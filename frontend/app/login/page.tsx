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
    <AuthFrame>
      <div className="auth-card">
        <div className="auth-title"><p className="eyebrow">다시 만나서 반가워요</p><h1>식단 기록을 이어볼까요?</h1><p>가입할 때 사용한 소셜 계정으로 로그인해 주세요.</p></div>
        {oauth === "unavailable" && <p className="auth-service-error" role="alert">로그인 서버가 응답하지 않았어요. 잠시 후 다시 시도해 주세요.</p>}
        <OAuthButtons mode="login" />
        <p className="auth-switch">아직 계정이 없나요? <Link href="/signup">회원가입</Link></p>
      </div>
    </AuthFrame>
  );
}
