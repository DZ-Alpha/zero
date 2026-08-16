import type { Metadata } from "next";
import localFont from "next/font/local";
import "./globals.css";

// 2026-07-31 - SUIT 적용을 롤백하고 원래 globals.css가 이름만 지정해뒀던
// 'IBM Plex Sans KR'/'Noto Sans KR'을 실제로 불러온다. CDN 직접 참조
// (@font-face/@import) 대신 이전과 같은 이유로 next/font로 self-host한다 -
// 외부 요청 없이 로드되고, 레이아웃 시프트 방지·font-display는 next/font가
// 처리한다.
//
// 2026-08-16 - Noto Sans KR 을 next/font/google 에서 next/font/local 로 옮긴다.
// google 쪽은 빌드 타임에 fonts.gstatic.com 에서 폰트 파일을 받아오는데,
// 구글이 같은 v39 안에서 파일 URL 을 갈아치우면(PbyC... -> Pbyk...) 캐시에
// 남은 옛 URL 이 404 가 되어 빌드가 통째로 실패한다. 실제로 파이프라인 #17 이
// 이 문제로 620개 에러를 내고 죽었다. 이미지 digest 는 고정해두고 정작 빌드
// 입력은 외부 CDN 에 매여 있던 셈이라, 폰트를 저장소에 넣어 빌드를 닫는다.
//
// 라틴/한글을 별도 패밀리로 선언하고 globals.css 에서 라틴 -> 한글 순으로
// 쌓는다. next/font/local 은 src 항목별 unicode-range 를 지원하지 않아서,
// 한 패밀리에 두 파일을 넣으면 글리프 폴백이 동작하지 않기 때문이다.
// 브라우저는 앞 패밀리에 없는 글자만 뒤 패밀리에서 찾는다.
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

const notoSansKr = localFont({
  src: [
    { path: "./fonts/noto-sans-kr/latin-300.woff2", weight: "300", style: "normal" },
    { path: "./fonts/noto-sans-kr/latin-400.woff2", weight: "400", style: "normal" },
    { path: "./fonts/noto-sans-kr/latin-500.woff2", weight: "500", style: "normal" },
    { path: "./fonts/noto-sans-kr/latin-700.woff2", weight: "700", style: "normal" },
    { path: "./fonts/noto-sans-kr/latin-900.woff2", weight: "900", style: "normal" },
  ],
  variable: "--font-noto-sans-kr",
  display: "swap",
});

const notoSansKrKo = localFont({
  src: [
    { path: "./fonts/noto-sans-kr/korean-300.woff2", weight: "300", style: "normal" },
    { path: "./fonts/noto-sans-kr/korean-400.woff2", weight: "400", style: "normal" },
    { path: "./fonts/noto-sans-kr/korean-500.woff2", weight: "500", style: "normal" },
    { path: "./fonts/noto-sans-kr/korean-700.woff2", weight: "700", style: "normal" },
    { path: "./fonts/noto-sans-kr/korean-900.woff2", weight: "900", style: "normal" },
  ],
  variable: "--font-noto-sans-kr-ko",
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
  description: "식단 기록과 건강정보를 바탕으로 나에게 맞는 저당 제품을 고르는 서비스",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang="ko"
      data-scroll-behavior="smooth"
      className={`${ibmPlexSansKr.variable} ${notoSansKr.variable} ${notoSansKrKo.variable}`}
    >
      <body>{children}</body>
    </html>
  );
}
