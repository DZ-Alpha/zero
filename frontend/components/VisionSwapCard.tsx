import Link from "next/link";
import { SafeImage } from "@/components/SafeImage";
import type { DietSwapRecommendationResponse } from "@/lib/api/zerocheck";

export type VisionRecipeSuggestion = {
  id: number | string;
  name: string;
  image?: string | null;
  category?: string | null;
  sugar?: number | null;
  calories?: number | null;
};

function number(value: number) {
  return new Intl.NumberFormat("ko-KR", { maximumFractionDigits: 2 }).format(value);
}

export function VisionSwapCard({ recommendation, recipes = [], recipesAreFallback = false }: {
  recommendation?: DietSwapRecommendationResponse | null;
  recipes?: VisionRecipeSuggestion[];
  /* 레시피를 인식한 이름 그대로가 아니라 토큰·요리 접미사로 넓혀서 찾았는지.
     넓혀 찾은 결과를 "가까운 선택"이라고 부르면 안 된다 - 제육볶음이 "볶음"으로
     넓혀지면 양배추볶음이 잡힌다(2026-08-12 추가 지시서 §4). */
  recipesAreFallback?: boolean;
}) {
  const current = recommendation?.status === "AVAILABLE" ? recommendation.current : null;
  const alternatives = current ? recommendation?.alternatives ?? [] : [];
  // 조리 음식 사진에서 NO_MATCH는 정상 경로라(2026-08-12 추가 지시서 §3) 안내
  // 문구를 상시 노출하면 카탈로그 커버리지 한계를 광고하는 꼴이 된다 - 화면은
  // 조용히 두고, 관측 책임은 diet-service의 drops 카운터 로그가 전부 진다.
  if (alternatives.length === 0 && recipes.length === 0) return null;
  // 제품 대안 없이 폴백 레시피만 남은 경우엔 카드 제목까지 낮춘다 - 정확 매칭인
  // 척하는 카피 위에 넓혀 찾은 결과만 놓이면 안 된다.
  const onlyFallbackRecipes = recipesAreFallback && alternatives.length === 0;

  return (
    <section className="vision-swap" aria-label="사진 분석 결과와 연결되는 추천">
      <header>
        <p className="eyebrow">사진과 함께 연결하기</p>
        <h3>{onlyFallbackRecipes ? "이런 저당 레시피는 어때요?" : "인식한 음식과 가까운 선택이에요"}</h3>
        <p>{onlyFallbackRecipes
          ? "정확히 같은 메뉴는 아니지만, 같은 종류에서 당류를 확인한 레시피예요."
          : "레시피는 음식명을 기준으로, 제품은 같은 종류와 같은 단위일 때만 보여드려요."}</p>
      </header>
      {recipes.length > 0 && <div className="vision-swap-group">
        <h4>{recipesAreFallback ? "이런 저당 레시피는 어때요?" : "비슷한 레시피"}</h4>
        <div className="vision-swap-list is-recipes">
          {recipes.slice(0, 2).map((recipe) => (
            <Link href={`/recipes/${recipe.id}`} key={recipe.id}>
              <span className="vision-swap-image"><SafeImage src={recipe.image ?? ""} alt="" fallbackLabel="레시피" /></span>
              <span>
                <small>{recipe.category || "연결 가능한 레시피"}</small>
                <strong>{recipe.name}</strong>
                <em>{recipe.sugar != null ? `당류 ${number(recipe.sugar)}g` : "재료와 조리법 보기"}{recipe.calories != null ? ` · ${number(recipe.calories)}kcal` : ""}</em>
              </span>
              <b aria-hidden="true">→</b>
            </Link>
          ))}
        </div>
      </div>}
      {current && alternatives.length > 0 && <div className="vision-swap-group">
        <h4>같은 종류의 저당 제품</h4>
        <div className="vision-swap-current">
          <span>인식한 제품</span>
          <strong>{current.name}</strong>
          <small>{current.brand ? `${current.brand} · ` : ""}{current.serving} · 당류 {number(current.sugar)}g</small>
        </div>
        <div className="vision-swap-list">
          {alternatives.slice(0, 2).map((product) => {
            const saved = Math.max(0, current.sugar - product.sugar);
            return (
              <Link href={`/product/${product.id}`} key={product.id}>
                <span className="vision-swap-image"><SafeImage src={product.image ?? ""} alt="" fallbackLabel="대안" /></span>
                <span>
                  <small>{product.brand || product.foodType || "같은 종류"}</small>
                  <strong>{product.name}</strong>
                  <em>{product.serving} · 당류 {number(product.sugar)}g</em>
                </span>
                <b>{number(saved)}g↓</b>
              </Link>
            );
          })}
        </div>
      </div>}
    </section>
  );
}
