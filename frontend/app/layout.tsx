import type { Metadata } from "next";
import localFont from "next/font/local";
import "./globals.css";

// 2026-07-31 요청 - 그동안 globals.css가 'IBM Plex Sans KR'/'Noto Sans KR'을
// font-family로 지정하고 있었지만, 이 프로젝트 어디에도 그 폰트를 실제로
// 불러오는 코드(next/font, Google Fonts 링크, @font-face)가 없어서 브라우저가
// 두 이름을 다 못 찾고 그다음 sans-serif(OS 기본 산세리프)로 넘어갔다 -
// "OS마다 다르게 보인다"던 증상의 원인. next/font/local로 SUIT을 실제로
// 불러와서 self-host한다(CDN 직접 참조 대신 - 외부 요청 없음, 레이아웃 시프트
// 방지, font-display 자동 최적화는 next/font가 처리).
const suit = localFont({
  src: [
    { path: "./fonts/suit/SUIT-Thin.woff2", weight: "100", style: "normal" },
    { path: "./fonts/suit/SUIT-ExtraLight.woff2", weight: "200", style: "normal" },
    { path: "./fonts/suit/SUIT-Light.woff2", weight: "300", style: "normal" },
    { path: "./fonts/suit/SUIT-Regular.woff2", weight: "400", style: "normal" },
    { path: "./fonts/suit/SUIT-Medium.woff2", weight: "500", style: "normal" },
    { path: "./fonts/suit/SUIT-SemiBold.woff2", weight: "600", style: "normal" },
    { path: "./fonts/suit/SUIT-Bold.woff2", weight: "700", style: "normal" },
    { path: "./fonts/suit/SUIT-ExtraBold.woff2", weight: "800", style: "normal" },
    { path: "./fonts/suit/SUIT-Heavy.woff2", weight: "900", style: "normal" },
  ],
  variable: "--font-suit",
  display: "swap",
});

export const metadata: Metadata = {
  title: "당당 — 먹기 전에, 한 번 더 당당하게",
  description: "식단 기록과 건강정보를 바탕으로 나에게 맞는 저당픽을 고르는 서비스",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ko" data-scroll-behavior="smooth" className={suit.variable}>
      <body>{children}</body>
    </html>
  );
}
