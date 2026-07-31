import type { Metadata } from "next";
import { JoinRoomPreview } from "@/components/rooms/JoinRoomPreview";
import { Shell } from "@/components/Shell";

export const metadata: Metadata = {
  title: "모임 참여",
  description: "초대 코드로 모임을 미리 보고 참여해요.",
  robots: { index: false, follow: false },
};

export default async function JoinRoomPage({
  searchParams,
}: {
  searchParams: Promise<{ code?: string }>;
}) {
  const { code = "" } = await searchParams;

  return (
    <Shell>
      <JoinRoomPreview code={code.toUpperCase().slice(0, 6)} />
    </Shell>
  );
}
