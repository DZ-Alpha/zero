"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { AUTH_CHANGE_EVENT } from "@/hooks/useAuthSession";
import { readJwtPayload, saveAccessToken } from "@/lib/api/client";

const providerByCode: Record<string, string> = {
  NA: "naver",
  KA: "kakao",
  GL: "google",
  AP: "apple",
};

function CallbackContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [error, setError] = useState("");

  useEffect(() => {
    const oauthError = searchParams.get("error");
    const token = searchParams.get("token");
    if (oauthError) {
      setError(oauthError);
      return;
    }
    if (!token) {
      setError("로그인 정보를 받지 못했어요. 소셜 로그인을 다시 시도해 주세요.");
      return;
    }

    saveAccessToken(token);
    window.dispatchEvent(new Event(AUTH_CHANGE_EVENT));

    const payload = readJwtPayload(token);
    const provider = providerByCode[searchParams.get("social") ?? ""] ?? "naver";
    const isNewUser = searchParams.get("isNewUser")?.toLowerCase() === "true";
    if (isNewUser) {
      const next = new URLSearchParams({ provider });
      const nickname = typeof payload?.nickname === "string" ? payload.nickname : "";
      const birthday = searchParams.get("birthday") ?? "";
      if (nickname) next.set("nickname", nickname);
      if (birthday) next.set("birthday", birthday);
      router.replace(`/signup/profile?${next.toString()}`);
      return;
    }
    router.replace("/");
  }, [router, searchParams]);

  if (error) {
    return (
      <main className="oauth-callback-state">
        <p className="eyebrow">로그인 안내</p>
        <h1>로그인을 마치지 못했어요.</h1>
        <p>{error}</p>
        <Link href="/login">로그인 다시 시도하기</Link>
      </main>
    );
  }

  return <main className="oauth-callback-state" role="status"><span /><h1>계정 정보를 확인하고 있어요.</h1><p>잠시만 기다려 주세요.</p></main>;
}

export default function Page() {
  return (
    <Suspense fallback={<main className="oauth-callback-state" role="status"><span /><h1>계정 정보를 확인하고 있어요.</h1><p>잠시만 기다려 주세요.</p></main>}>
      <CallbackContent />
    </Suspense>
  );
}
