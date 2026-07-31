import type { Metadata } from "next";
import { PersonalPage } from "@/components/PersonalPage";
import { Shell } from "@/components/Shell";

export const metadata: Metadata = {
  title: "마이페이지",
  description: "내 정보와 목표, 찜한 메뉴를 관리해요.",
  robots: { index: false, follow: false },
};

export default function Page() {
  return <Shell><PersonalPage /></Shell>;
}
