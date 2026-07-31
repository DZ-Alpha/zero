import type { Metadata } from "next";
import { SectionPage } from "@/components/SectionPage";

export const metadata: Metadata = {
  title: "성분 상담",
  description: "성분이 어려울 때, 당당 상담에게 물어보세요.",
};

export default function Page(){return <SectionPage kind="chat"/>}
