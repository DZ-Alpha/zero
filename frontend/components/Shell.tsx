import Link from "next/link";
import { ChatWidget } from "@/components/ChatWidget";
import { HeaderAuth } from "@/components/HeaderAuth";
import { SiteNav } from "@/components/SiteNav";
import { SessionExpiredNotice } from "@/components/SystemFeedback";

export function Shell({ children }: { children: React.ReactNode }) {
  return (
    <>
      <a className="skip-link" href="#main-content">본문으로 바로가기</a>
      <header className="site-header">
        <Link href="/" className="brand" aria-label="상상 홈">
          <span className="brand-mark"><img src="/brand-trophy.jpg" alt="" /></span>
          <span className="brand-copy"><b>상상</b></span>
        </Link>
        <SiteNav />
        <HeaderAuth />
      </header>
      <div id="main-content" tabIndex={-1}>{children}</div>
      <footer className="service-footer"><div className="wrap"><span>당당 · 제로·저당 식품 선택 서비스</span><nav aria-label="서비스 정책"><Link href="/terms">이용약관</Link><Link href="/privacy">개인정보처리방침</Link></nav></div></footer>
      <SessionExpiredNotice />
      <ChatWidget />
    </>
  );
}
