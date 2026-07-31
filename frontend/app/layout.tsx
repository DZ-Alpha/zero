import type { Metadata } from "next";
import localFont from "next/font/local";
import { Noto_Sans_KR } from "next/font/google";
import "./globals.css";

// 2026-07-31 - SUIT 적용을 롤백하고 원래 globals.css가 이름만 지정해뒀던
// 'IBM Plex Sans KR'/'Noto Sans KR'을 실제로 불러온다. CDN 직접 참조
// (@font-face/@import) 대신 이전과 같은 이유로 next/font로 self-host한다 -
// 외부 요청 없이 로드되고, 레이아웃 시프트 방지·font-display는 next/font가
// 처리한다. Noto Sans KR은 next/font/google이 공식 지원해서 그쪽을 쓰고,
// IBM Plex Sans KR은 Google Fonts에 없어 next/font/local로 받는다.
const ibmPlexSansKr = localFont({
  src: [
    { path: "./fonts/ibm-plex-sans-kr/IBMPlexSansKR-ExtraLight.woff", weight: "200", style: "normal" },
    { path: "./fonts/ibm-plex-sans-kr/IBMPlexSansKR-Light.woff", weight: "300", style: "normal" },
    { path: "./fonts/ibm-plex-sans-kr/IBMPlexSansKR-Regular.woff", weight: "400", style: "normal" },
    { path: "./fonts/ibm-plex-sans-kr/IBMPlexSansKR-Text.woff", weight: "400", style: "normal" },
    { path: "./fonts/ibm-plex-sans-kr/IBMPlexSansKR-Medium.woff", weight: "500", style: "normal" },
    { path: "./fonts/ibm-plex-sans-kr/IBMPlexSansKR-SemiBold.woff", weight: "600", style: "normal" },
  ],
  variable: "--font-ibm-plex-sans-kr",
  display: "swap",
});

const notoSansKr = Noto_Sans_KR({
  subsets: ["latin"],
  weight: ["300", "400", "500", "700", "900"],
  variable: "--font-noto-sans-kr",
  display: "swap",
});

// 2026-07-31 요청 - 페이지마다 title/description이 바뀌어야 하고, 브라우저가
// 아닌 크롤러가 직접 들어와도(JS 미실행) 의미 있는 내용을 봐야 한다. Next
// App Router의 export const metadata/generateMetadata는 서버에서 렌더된
// HTML <head>에 그대로 박혀서 나가므로 JS 실행 여부와 무관하게 동작한다.
// title.template으로 각 페이지가 title만 짧게 넘기면 "OOO | 당당" 형태로
// 통일된다. metadataBase는 OpenGraph 등 상대 URL을 절대경로로 풀 때 기준.
export const metadata: Metadata = {
  metadataBase: new URL("https://zerodang.org"),
  title: {
    default: "당당 — 먹기 전에, 한 번 더 당당하게",
    template: "%s | 당당",
  },
  description: "식단 기록과 건강정보를 바탕으로 나에게 맞는 저당픽을 고르는 서비스",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang="ko"
      data-scroll-behavior="smooth"
      className={`${ibmPlexSansKr.variable} ${notoSansKr.variable}`}
    >
      <body>{children}</body>
    </html>
  );
}
