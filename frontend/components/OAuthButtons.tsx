export const OAUTH_PROVIDERS = [
  { id: "google", label: "Google", mark: "G", className: "google", enabled: false },
  { id: "kakao", label: "카카오", mark: "K", className: "kakao", enabled: true },
  { id: "naver", label: "NAVER", mark: "N", className: "naver", enabled: true },
  { id: "apple", label: "Apple", mark: "●", className: "apple", enabled: false },
] as const;

export function OAuthButtons({ mode }: { mode: "login" | "signup" }) {
  const returnPath = mode === "login" ? "/login?oauth=unavailable" : "/signup?oauth=unavailable";

  return (
    <div className="oauth-list">
      {OAUTH_PROVIDERS.map((provider) => provider.enabled ? (
        <a
          className={`oauth-button is-${provider.className}`}
          href={`/b/social-access/${provider.id}/login?fallback=${encodeURIComponent(returnPath)}`}
          key={provider.id}
        >
          <span>{provider.mark}</span><b>{provider.label}로 {mode === "signup" ? "가입하기" : "계속하기"}</b><i className="oauth-arrow">→</i>
        </a>
      ) : (
        <button className={`oauth-button is-${provider.className} is-disabled`} type="button" disabled key={provider.id}>
          <span>{provider.mark}</span><b>{provider.label} 로그인</b><i className="oauth-soon">준비중</i>
        </button>
      ))}
    </div>
  );
}
