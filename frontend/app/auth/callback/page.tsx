import type { Metadata } from "next";
import { AuthCallbackClient } from "@/components/AuthCallbackClient";

// 소셜 로그인 리다이렉트 경유지일 뿐 실제 내용이 없다 - 검색엔진에 노출할
// 필요가 없다. metadata export는 서버 컴포넌트에서만 가능해서("use client"와
// 공존 불가) 기존 클라이언트 로직은 AuthCallbackClient.tsx로 옮겼다.
export const metadata: Metadata = {
  title: "로그인 처리 중",
  robots: { index: false, follow: false },
};

export default function Page() {
  return <AuthCallbackClient />;
}
