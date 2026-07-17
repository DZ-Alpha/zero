import Link from "next/link";
import { Shell } from "@/components/Shell";

export default function ServiceUnavailablePage() {
  return <Shell><main className="system-page page-wrap"><section className="system-page-card wrap"><span aria-hidden="true">—</span><p className="eyebrow">서비스 점검 중</p><h1>더 안정적으로<br />돌아올게요.</h1><p>점검이 끝난 뒤 다시 접속해 주세요. 저장된 계정 정보는 그대로 유지돼요.</p><div><Link href="/">홈 새로 확인하기</Link></div></section></main></Shell>;
}
