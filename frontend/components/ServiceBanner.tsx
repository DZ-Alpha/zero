"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

const AUTO_PLAY_MS = 5600;

const slides = [
  {
    label: "오늘 기록",
    title: "먹은 걸 기록하면 오늘의 당과 칼로리가 보여요.",
    description: "레시피·식품·사진 중 편한 방법으로 기록해보세요.",
    href: null,
    action: null,
    background: "#eef8d8",
  },
  {
    label: "성분 읽기",
    title: "‘제로’라는 말보다 성분표를 쉽게 읽어드려요.",
    description: "당류와 감미료 정보를 어려운 용어 없이 정리해요.",
    href: "/search",
    action: "식품 찾아보기",
    background: "#e7f2ec",
  },
  {
    label: "다음 선택",
    title: "오늘 먹은 걸 바탕으로 다음 한 끼를 골라보세요.",
    description: "식단 기록과 관심 정보를 함께 살펴보고 선택을 제안해요.",
    href: "/recipes",
    action: "레시피 둘러보기",
    background: "#f1f4df",
  },
] as const;

export function ServiceBanner() {
  const [active, setActive] = useState(0);
  const [direction, setDirection] = useState<"next" | "prev">("next");
  const [isPaused, setIsPaused] = useState(false);

  useEffect(() => {
    if (isPaused || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    const timer = window.setTimeout(() => {
      setDirection("next");
      setActive((current) => (current + 1) % slides.length);
    }, AUTO_PLAY_MS);

    return () => window.clearTimeout(timer);
  }, [active, isPaused]);

  function move(step: -1 | 1) {
    setDirection(step === 1 ? "next" : "prev");
    setActive((current) => (current + step + slides.length) % slides.length);
  }

  const slide = slides[active];

  return (
    <section
      className="service-banner"
      style={{ backgroundColor: slide.background }}
      aria-label="당당 서비스 안내"
      onMouseEnter={() => setIsPaused(true)}
      onMouseLeave={() => setIsPaused(false)}
      onFocusCapture={() => setIsPaused(true)}
      onBlurCapture={() => setIsPaused(false)}
    >
      <div className="service-banner-shell">
        <button type="button" className="service-banner-arrow is-prev" onClick={() => move(-1)} aria-label="이전 안내">
          <span aria-hidden="true">←</span>
        </button>

        <div className={`service-banner-slide is-${direction}`} key={active}>
          <div className="service-banner-message">
            <span className="service-banner-kicker">{String(active + 1).padStart(2, "0")} · {slide.label}</span>
            <h1>{slide.title}</h1>
            <p>{slide.description}</p>
          </div>
          {slide.href && slide.action ? <Link className="service-banner-link" href={slide.href}>{slide.action}<span aria-hidden="true">↗</span></Link> : <span className="service-banner-spacer" aria-hidden="true" />}
        </div>

        <button type="button" className="service-banner-arrow is-next" onClick={() => move(1)} aria-label="다음 안내">
          <span aria-hidden="true">→</span>
        </button>
      </div>
    </section>
  );
}
