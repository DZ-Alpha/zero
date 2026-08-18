import Link from "next/link";
import { ChatWidget } from "@/components/ChatWidget";
import { HeaderAuth } from "@/components/HeaderAuth";
import { SavedMenuDrawer } from "@/components/SavedMenuDrawer";
import { ScrollToTop } from "@/components/ScrollToTop";
import { MobileNav, SiteNav } from "@/components/SiteNav";
import { SessionExpiredNotice } from "@/components/SystemFeedback";

export function Shell({ children }: { children: React.ReactNode }) {
  return (
    <>
      <ScrollToTop />
      <a className="skip-link" href="#main-content">본문으로 바로가기</a>
      <header className="site-header">
        {/* 온프렘(k8s.zerodang.org) 전용 표기. AWS(zerodang.org)는 "당당"이며,
            그쪽 저장소(dang-aws-service)에서 코드를 가져올 때 이 줄이 되돌아오기
            쉬우니 동기화 후 확인할 것. 두 사이트를 눈으로 구분하기 위한 것이다. */}
        <Link href="/" className="brand" aria-label="K8s당당 홈">
          <span className="brand-mark">
            <img src="/icon.svg" alt="" width={32} height={32} />
          </span>
          <span className="brand-copy"><b>K8s당당</b></span>
        </Link>
        <SiteNav />
        <HeaderAuth />
      </header>
      <div id="main-content" className="site-main" tabIndex={-1}>{children}</div>
      <MobileNav />
      <footer className="service-footer"><div className="wrap"><span>당당 · 제로·저당 선택 서비스</span><nav aria-label="서비스 정책"><Link href="/terms">이용약관</Link><Link href="/privacy">개인정보처리방침</Link></nav></div></footer>
      <SessionExpiredNotice />
      <SavedMenuDrawer />
      <ChatWidget />
    </>
  );
}
