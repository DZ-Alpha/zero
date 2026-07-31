import { HomeDashboard } from "@/components/HomeDashboard";
import { Shell } from "@/components/Shell";

// 메인("/")은 원래 타이틀("당당 — 먹기 전에, 한 번 더 당당하게")로 검색에 걸려야
// 하는데, 페이지별 title이 "오늘의 식단 기록"으로만 바뀌면 "당당" 검색과는 안
// 맞는다(2026-07-31 지적). 별도 metadata를 두지 않고 루트 레이아웃의
// default 타이틀/설명을 그대로 쓴다.
export default function Home() {
  return <Shell><HomeDashboard /></Shell>;
}
