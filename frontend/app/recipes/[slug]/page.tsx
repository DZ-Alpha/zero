import type { Metadata } from "next";
import { RecipeDetail } from "@/components/RecipeDetail";
import { Shell } from "@/components/Shell";
import { recipeBySlug, recipes } from "@/data/catalog";
import { fetchRecipeForMetadata } from "@/lib/api/metadataFetch";

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const { slug } = await params;
  const catalogDetail = recipeBySlug[slug] ?? recipes.find((recipe) => recipe.databaseId === slug) ?? null;
  const parsedId = Number(catalogDetail?.databaseId ?? slug);

  let name = catalogDetail?.title ?? null;
  let sugar = catalogDetail?.estimatedSugar ?? null;
  let calories = catalogDetail?.estimatedCalories ?? null;

  if (Number.isFinite(parsedId)) {
    try {
      const live = await fetchRecipeForMetadata(parsedId);
      if (live?.name) name = live.name;
      if (typeof live?.nutrition?.totalSugarG === "number") sugar = live.nutrition.totalSugarG;
      if (typeof live?.nutrition?.totalKcal === "number") calories = live.nutrition.totalKcal;
    } catch {
      // 백엔드 미응답 - 위 카탈로그 목업 값을 그대로 쓴다.
    }
  }

  if (!name) {
    return { title: "레시피", description: "당당에서 당류를 줄인 레시피를 확인해보세요." };
  }

  const description = [sugar != null ? `당류 ${sugar}g` : null, calories != null ? `${calories}kcal` : null]
    .filter(Boolean)
    .join(" · ") || `${name} - 당당에서 재료와 조리법을 확인해보세요.`;

  return {
    title: name,
    description,
    openGraph: { title: name, description },
  };
}

export default async function Page({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  return <Shell><RecipeDetail slug={slug} /></Shell>;
}
