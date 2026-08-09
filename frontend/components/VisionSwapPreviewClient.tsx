"use client";

import { RecordMealModal } from "@/components/RecordMealModal";
import { Shell } from "@/components/Shell";

export function VisionSwapPreviewClient() {
  return (
    <Shell>
      <main aria-label="사진 분석 스왑 카드 개발 미리보기" />
      <RecordMealModal meal="점심" mockPreview onClose={() => undefined} />
    </Shell>
  );
}
