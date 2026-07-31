import type { Metadata } from "next";
import { CalendarDashboard } from "@/components/CalendarDashboard";
import { Shell } from "@/components/Shell";

export const metadata: Metadata = {
  title: "기록 캘린더",
  description: "달력으로 내가 기록한 식단과 당류·칼로리 흐름을 한눈에 확인해요.",
  robots: { index: false, follow: false },
};

export default function Page() {
  return <Shell><CalendarDashboard /></Shell>;
}
