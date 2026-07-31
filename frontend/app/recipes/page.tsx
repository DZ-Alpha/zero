import type { Metadata } from "next";
import { RecipeFeed } from "@/components/RecipeFeed";
import { Shell } from "@/components/Shell";

export const metadata: Metadata = {
  title: "저당 레시피",
  description: "당류를 줄인 레시피를 재료·조리법과 함께 찾아보세요.",
};

export default function Page() {
  return <Shell><RecipeFeed /></Shell>;
}
