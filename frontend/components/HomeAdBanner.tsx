"use client";

import type { CSSProperties, FocusEvent } from "react";
import { useEffect, useState } from "react";
import Image from "next/image";
import Link from "next/link";

const adSlides = [
  {
    id: "popcorn",
    eyebrow: "WEEKEND ZERO",
    title: "영화 고르기 전에\n팝콘부터 제로",
    copy: "주말의 바삭함은 그대로, 당류는 0g.",
    product: "롯데시네마 제로팝콘",
    badge: "당류 0g",
    image: "/product-data/lotte-zero-popcorn.png",
    href: "/product/lotte-cinema-zero-popcorn",
    background: "#f0cf4a",
    foreground: "#172019",
    accent: "#fff4bf",
  },
  {
    id: "plum-bar",
    eyebrow: "COOL DOWN",
    title: "더운 오후엔\n자두 제로바 한 입",
    copy: "달콤하고 시원하게, 열량은 0kcal.",
    product: "라라스윗 자두 제로바",
    badge: "0 kcal",
    image: "/product-data/lalasweet-plum-zero-bar.jpg",
    href: "/product/lalasweet-plum-zero-bar",
    background: "#f06a83",
    foreground: "#21191c",
    accent: "#d5f238",
  },
  {
    id: "oat-cookie",
    eyebrow: "COOKIE BREAK",
    title: "오후 네 시,\n쿠키는 포기하지 말기",
    copy: "오트로 구운 바삭함, 당류는 0g.",
    product: "잇츠베러 제로슈가쿠키 스윗오트",
    badge: "당류 0g",
    image: "/product-data/itsbetter-sweet-oat-cookie.jpg",
    href: "/product/itsbetter-sweet-oat-cookie",
    background: "#d9bd96",
    foreground: "#2b211a",
    accent: "#fff1dc",
  },
] as const;

export function HomeAdBanner() {
  const [active, setActive] = useState(0);
  const [paused, setPaused] = useState(false);
  const slide = adSlides[active];

  useEffect(() => {
    if (paused) return;
    const timer = window.setInterval(() => {
      setActive((current) => (current + 1) % adSlides.length);
    }, 5200);
    return () => window.clearInterval(timer);
  }, [paused]);

  function handleBlur(event: FocusEvent<HTMLElement>) {
    if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setPaused(false);
  }

  const style = {
    "--ad-bg": slide.background,
    "--ad-ink": slide.foreground,
    "--ad-accent": slide.accent,
  } as CSSProperties;

  return (
    <section
      className="home-ad-banner wrap"
      style={style}
      aria-label="추천 광고"
      aria-roledescription="carousel"
      data-paused={paused || undefined}
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      onFocusCapture={() => setPaused(true)}
      onBlurCapture={handleBlur}
    >
      <Link className="home-ad-full-link" href={slide.href} aria-label={`${slide.product} 보기`} />
      <div className="home-ad-copy" key={`${slide.id}-copy`}>
        <div className="home-ad-labels">
          <span>광고</span>
          <b>{slide.eyebrow}</b>
        </div>
        <h2>{slide.title.split("\n").map((line) => <span key={line}>{line}</span>)}</h2>
        <p>{slide.copy}</p>
        <Link href={slide.href}>
          <span>{slide.product}</span>
          <b>제품 보기 →</b>
        </Link>
      </div>

      <div className="home-ad-stage" key={`${slide.id}-stage`} aria-hidden="true">
        <span className="home-ad-zero">ZERO</span>
        <Image
          src={slide.image}
          alt=""
          width={520}
          height={520}
          sizes="(max-width: 700px) 45vw, 420px"
          priority={active === 0}
        />
        <span className="home-ad-badge">{slide.badge}</span>
      </div>

      <div className="home-ad-controls">
        <span>{String(active + 1).padStart(2, "0")} / {String(adSlides.length).padStart(2, "0")}</span>
        <div>
          {adSlides.map((item, index) => (
            <button
              type="button"
              key={item.id}
              aria-label={`${index + 1}번째 광고 보기: ${item.product}`}
              aria-current={index === active ? "true" : undefined}
              onClick={() => setActive(index)}
            >
              <i />
            </button>
          ))}
        </div>
      </div>
    </section>
  );
}
