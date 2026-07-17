"use client";

import Link from "next/link";
import { useEffect } from "react";
import { Shell } from "@/components/Shell";

export default function ErrorPage({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => { console.error(error); }, [error]);
  return <Shell><main className="system-page page-wrap"><section className="system-page-card wrap"><span aria-hidden="true">!</span><p className="eyebrow">화면을 열지 못했어요</p><h1>잠시 후 다시<br />시도해 주세요.</h1><p>연결이 잠시 불안정해요. 같은 문제가 계속되면 홈으로 돌아가 주세요.</p><div><button type="button" onClick={reset}>다시 시도하기</button><Link href="/">홈으로 가기</Link></div></section></main></Shell>;
}
