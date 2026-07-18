import Link from "next/link";

export function AuthFrame({ children, asideTitle = "먹은 만큼 알고, 다음 선택은 가볍게." }: { children: React.ReactNode; asideTitle?: string }) {
  return (
    <main className="auth-page">
      <header className="auth-header">
        <Link href="/" className="brand" aria-label="당당 홈"><span className="brand-mark"><i /></span><span className="brand-copy"><b>당당</b></span></Link>
        <Link href="/" className="auth-home-link">홈으로 돌아가기</Link>
      </header>
      <div className="auth-layout">
        <aside className="auth-aside">
          <p className="eyebrow">ZERO · LOW SUGAR · FOOD LOG</p>
          <h1>{asideTitle}</h1>
          <p>식단을 기록하면 당류와 열량을 한눈에 보고, 실제 제품과 저당 레시피를 이어서 찾을 수 있어요.</p>
          <ol><li><span>01</span>오늘 먹은 음식 기록</li><li><span>02</span>당류와 열량 바로 계산</li><li><span>03</span>내 관심사에 맞는 식품 추천</li></ol>
        </aside>
        <section className="auth-content">{children}</section>
      </div>
      <nav className="auth-policy-links" aria-label="서비스 정책"><Link href="/terms">이용약관</Link><Link href="/privacy">개인정보처리방침</Link></nav>
    </main>
  );
}
