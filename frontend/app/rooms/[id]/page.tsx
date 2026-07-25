import { RoomDetail } from "@/components/rooms/RoomDetail";
import { Shell } from "@/components/Shell";

export default async function RoomPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;

  return (
    <Shell>
      <RoomDetail roomId={id} />
    </Shell>
  );
}

