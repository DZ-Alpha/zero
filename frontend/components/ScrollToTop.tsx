"use client";

import { useLayoutEffect } from "react";
import { usePathname } from "next/navigation";

let guardGeneration = 0;

// 어떤 화면이 네비게이션 직후 의도적으로 스크롤을 옮기고 싶으면(예: 방 상세가
// 헤더를 지나 탭까지 스크롤하는 것, RoomDetail.tsx) 이 함수를 그 스크롤 직전에
// 불러서 아래 "맨 위 고정" 가드를 즉시 꺼야 한다 - 안 그러면 몇 프레임 안에
// 가드가 그 의도적인 스크롤을 다시 0으로 되돌려버린다.
export function suppressScrollTopGuard() {
  guardGeneration += 1;
}

const GUARD_DURATION_MS = 2000;

export function ScrollToTop() {
  const pathname = usePathname();

  useLayoutEffect(() => {
    const root = document.documentElement;
    const previousBehavior = root.style.scrollBehavior;
    root.style.scrollBehavior = "auto";
    window.scrollTo({ top: 0, left: 0 });

    // 네비게이션 직후 아직 다 안 불러온 이미지/뱃지/광고 배너 등이 뒤늦게
    // 레이아웃을 바꾸면서 스크롤이 살짝 밀리는 문제가 있었다(overflow-anchor:
    // none만으로는 못 잡는 케이스가 있었음 - 2026-07-31 재확인됨). 원인이
    // 무엇이든 결과만 확실히 잡기 위해, 짧은 시간 동안 스크롤을 0으로 계속
    // 지켜본다. 유저가 실제로 스크롤/터치/키 조작을 하면 그 즉시 손을 뗀다 -
    // 의도적인 스크롤을 방해하지 않기 위함(RoomDetail의 자체 스크롤은
    // suppressScrollTopGuard로 별도 예외 처리).
    const generation = ++guardGeneration;
    let released = false;
    function release() {
      released = true;
    }
    window.addEventListener("wheel", release, { passive: true, once: true });
    window.addEventListener("touchmove", release, { passive: true, once: true });
    window.addEventListener("keydown", release, { once: true });

    const start = performance.now();
    let rafId = 0;
    function tick() {
      if (released || generation !== guardGeneration || performance.now() - start > GUARD_DURATION_MS) return;
      if (window.scrollY !== 0) window.scrollTo({ top: 0, left: 0 });
      rafId = requestAnimationFrame(tick);
    }
    rafId = requestAnimationFrame(tick);

    const restoreTimer = window.setTimeout(() => {
      root.style.scrollBehavior = previousBehavior;
    }, GUARD_DURATION_MS);

    return () => {
      window.removeEventListener("wheel", release);
      window.removeEventListener("touchmove", release);
      window.removeEventListener("keydown", release);
      window.cancelAnimationFrame(rafId);
      window.clearTimeout(restoreTimer);
    };
  }, [pathname]);

  return null;
}
