import type { RecipeData } from "@/data/catalog";
import { SafeImage } from "@/components/SafeImage";

export function RecipeCover({ recipe, hero = false }: { recipe: RecipeData; hero?: boolean }) {
  const hasImage = Boolean(recipe.thumbnail);

  return (
    <div className={`recipe-data-cover tone-${recipe.tone}${hero ? " is-hero" : ""}${hasImage ? " has-image" : ""}`}>
      {hasImage && <SafeImage className="recipe-cover-image" src={recipe.thumbnail} alt={`${recipe.title} 레시피`} loading={hero ? "eager" : "lazy"} fallbackLabel="레시피 이미지 준비 중" />}
      {/* 조리 시간은 상세(hero)에서만 보여준다 — DB 레시피 대부분이 아직 시간
          데이터가 없어 목록 카드마다 "조리 시간 준비 중"이 도배되는 문제(2026-07-22,
          데이터 채워지면 되돌리기). */}
      <div className="recipe-cover-top"><span>{recipe.category}</span>{hero && <b>{recipe.time}</b>}</div>
      <div className="recipe-cover-copy">
        <small>{recipe.keywords.join(" · ")}</small>
        <strong>{recipe.title}</strong>
      </div>
      {!hasImage && <div className="recipe-cover-shapes" aria-hidden="true"><i /><i /><i /></div>}
    </div>
  );
}
