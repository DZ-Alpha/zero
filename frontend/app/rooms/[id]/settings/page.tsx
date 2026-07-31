import type { Metadata } from "next";
import { RoomSettings } from "@/components/rooms/RoomSettings";
import { Shell } from "@/components/Shell";

export const metadata: Metadata = {
  title: "모임 관리",
  robots: { index: false, follow: false },
};

export default async function RoomSettingsPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;

  return (
    <Shell>
      <RoomSettings roomId={id} />
    </Shell>
  );
}
