import type { RecipeData } from "@/data/catalog";
import { SafeImage } from "@/components/SafeImage";

export function RecipeCover({ recipe, hero = false }: { recipe: RecipeData; hero?: boolean }) {
  const hasImage = Boolean(recipe.thumbnail);

  return (
    <div className={`recipe-data-cover tone-${recipe.tone}${hero ? " is-hero" : ""}${hasImage ? " has-image" : ""}`}>
      {hasImage && <SafeImage className="recipe-cover-image" src={recipe.thumbnail} alt={`${recipe.title} 레시피`} loading={hero ? "eager" : "lazy"} fallbackLabel="레시피 이미지 준비 중" />}
      <div className="recipe-cover-top"><span>{recipe.category}</span><b>{recipe.time}</b></div>
      <div className="recipe-cover-copy">
        <small>{recipe.keywords.join(" · ")}</small>
        <strong>{recipe.title}</strong>
      </div>
      {!hasImage && <div className="recipe-cover-shapes" aria-hidden="true"><i /><i /><i /></div>}
    </div>
  );
}
