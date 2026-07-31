import type { Metadata } from "next";
import { RoomsHome } from "@/components/rooms/RoomsHome";
import { Shell } from "@/components/Shell";

export const metadata: Metadata = {
  title: "얌로그 - 모임과 함께 기록해요",
  description: "친구들과 모임을 만들어 서로의 오늘 식탁을 확인하고, 콕 찔러 응원해요.",
};

export default function RoomsPage() {
  return (
    <Shell>
      <RoomsHome />
    </Shell>
  );
}

