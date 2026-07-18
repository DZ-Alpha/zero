"use client";

export default function GlobalError({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return <html lang="ko"><body><main className="global-error-page"><p>당당</p><h1>서비스를 불러오지 못했어요.</h1><span>잠시 후 다시 시도해 주세요.</span><button type="button" onClick={reset}>다시 시도하기</button><a href="/">홈으로 가기</a></main></body></html>;
}
