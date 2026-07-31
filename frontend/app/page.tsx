import type { Metadata } from "next";
import { HomeDashboard } from "@/components/HomeDashboard";
import { Shell } from "@/components/Shell";

export const metadata: Metadata = {
  title: "오늘의 식단 기록",
  description: "오늘 먹은 음식과 당류·칼로리를 기록하고 하루 목표를 확인해요.",
};

export default function Home() {
  return <Shell><HomeDashboard /></Shell>;
}
