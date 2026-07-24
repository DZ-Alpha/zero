import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "당당 관리자",
  description: "당당 상품/원재료 관리 및 데이터 분석 관리자 페이지",
  robots: { index: false, follow: false },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}
