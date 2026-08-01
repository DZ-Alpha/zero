"use client";

import { useEffect, useState } from "react";
import type { RecipeData } from "@/data/catalog";
import { SafeImage } from "@/components/SafeImage";

export function RecipeCover({ recipe, hero = false }: { recipe: RecipeData; hero?: boolean }) {
  const hasImage = Boolean(recipe.thumbnail);
  // 유튜브 수집 레시피(video_id 있음)만, 그리고 상세 히어로에서만 재생 버튼을 띄운다.
  // 목록 카드/비슷한 레시피(hero=false)는 지금처럼 썸네일만 보여준다.
  const canPlay = hero && Boolean(recipe.videoId);
  const [playing, setPlaying] = useState(false);

  // 다른 레시피로 이동해 videoId가 바뀌면 재생 상태를 초기화한다 — 안 그러면 이전
  // 영상 iframe이 새 레시피 커버에 그대로 남는다.
  useEffect(() => {
    setPlaying(false);
  }, [recipe.videoId]);

  return (
    <div className={`recipe-data-cover tone-${recipe.tone}${hero ? " is-hero" : ""}${hasImage ? " has-image" : ""}`}>
      {playing && recipe.videoId ? (
        <iframe
          className="recipe-cover-video"
          src={`https://www.youtube.com/embed/${recipe.videoId}?autoplay=1&rel=0`}
          title={`${recipe.title} 조리 영상`}
          allow="autoplay; encrypted-media; picture-in-picture; fullscreen"
          allowFullScreen
        />
      ) : (
        <>
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
          {canPlay && (
            <button type="button" className="recipe-cover-play" aria-label="조리 영상 재생" onClick={() => setPlaying(true)}>
              <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M8 5v14l11-7z" /></svg>
            </button>
          )}
        </>
      )}
    </div>
  );
}
