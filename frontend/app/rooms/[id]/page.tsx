import type { Metadata } from "next";
import { RoomDetail } from "@/components/rooms/RoomDetail";
import { Shell } from "@/components/Shell";

// 로그인한 멤버만 볼 수 있는 비공개 모임 데이터라 검색엔진에 노출되면 안 된다
// - 방 이름 등 실제 내용은 메타데이터에 넣지 않고 noindex만 건다.
export const metadata: Metadata = {
  title: "얌로그 모임",
  robots: { index: false, follow: false },
};

export default async function RoomPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;

  return (
    <Shell>
      <RoomDetail roomId={id} />
    </Shell>
  );
}

