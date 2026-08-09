import { notFound } from "next/navigation";
import { VisionSwapPreviewClient } from "@/components/VisionSwapPreviewClient";

export default function VisionSwapPreviewPage() {
  if (process.env.NEXT_PUBLIC_MOCK_MODE !== "1") notFound();
  return <VisionSwapPreviewClient />;
}
