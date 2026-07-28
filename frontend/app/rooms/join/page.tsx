import { JoinRoomPreview } from "@/components/rooms/JoinRoomPreview";
import { Shell } from "@/components/Shell";

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
