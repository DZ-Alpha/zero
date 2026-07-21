import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "상상 — 먹기 전에, 한 번 더 당당하게",
  description: "식단 기록과 건강정보를 바탕으로 제로·저당 식품을 고르는 서비스",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}
