import type { Metadata } from "next";
import { ProductFeed } from "@/components/ProductFeed";
import { Shell } from "@/components/Shell";

export const metadata: Metadata = {
  title: "저당픽 - 성분으로 고르는 제품",
  description: "제품 사진과 성분표를 함께 보고, 당류가 적은 저당픽을 찾아보세요.",
};

export default function Page() {
  return <Shell><ProductFeed /></Shell>;
}
