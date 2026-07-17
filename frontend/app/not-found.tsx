import Link from "next/link";
import { Shell } from "@/components/Shell";

export default function NotFound() {
  return <Shell><main className="system-page page-wrap"><section className="system-page-card wrap"><span aria-hidden="true">404</span><p className="eyebrow">페이지를 찾을 수 없어요</p><h1>주소가 바뀌었거나<br />없는 페이지예요.</h1><p>홈으로 돌아가 식단 기록이나 제품 검색을 이어가세요.</p><div><Link href="/">홈으로 가기</Link><Link href="/search">제품 찾아보기</Link></div></section></main></Shell>;
}
