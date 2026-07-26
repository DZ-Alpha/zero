"use client";

import { useEffect, useRef } from "react";
import Script from "next/script";

// 관리자 로그인(POST /administrator-login)이 캡차 토큰을 필수로 검증한다
// (login-service/app/services/turnstile.py — 토큰이 없거나 무효하면 항상 401).
// 코드베이스 어디에도 Turnstile 위젯을 렌더링하는 프론트 코드가 없어서
// (일반 회원가입 흐름은 이 검증을 안 탄다) 여기서 새로 붙인다.
declare global {
  interface Window {
    turnstile?: {
      render: (
        el: HTMLElement,
        opts: {
          sitekey: string;
          callback: (token: string) => void;
          "expired-callback"?: () => void;
          "error-callback"?: () => void;
        },
      ) => string;
    };
  }
}

export function TurnstileWidget({ onToken }: { onToken: (token: string) => void }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const rendered = useRef(false);

  function renderWidget() {
    const siteKey = process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY;
    if (!containerRef.current || !window.turnstile || rendered.current || !siteKey) return;
    rendered.current = true;
    window.turnstile.render(containerRef.current, {
      sitekey: siteKey,
      callback: onToken,
      "expired-callback": () => onToken(""),
      "error-callback": () => onToken(""),
    });
  }

  useEffect(() => {
    if (window.turnstile) renderWidget();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const siteKey = process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY;
  if (!siteKey) {
    return (
      <p className="auth-error">
        NEXT_PUBLIC_TURNSTILE_SITE_KEY가 설정되지 않았어요 — 이 값 없이는 캡차 검증을 통과할 수 없어서 로그인이 항상 실패해요.
      </p>
    );
  }

  return (
    <>
      <Script src="https://challenges.cloudflare.com/turnstile/v0/api.js" strategy="afterInteractive" onLoad={renderWidget} />
      <div ref={containerRef} />
    </>
  );
}
