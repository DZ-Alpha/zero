import { RoomSettings } from "@/components/rooms/RoomSettings";
import { Shell } from "@/components/Shell";

export default async function RoomSettingsPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;

  return (
    <Shell>
      <RoomSettings roomId={id} />
    </Shell>
  );
}
