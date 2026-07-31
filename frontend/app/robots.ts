import type { MetadataRoute } from "next";

// 개별 페이지의 robots:{index:false} 메타(rooms/*, mypage, diet, chat 로그인
// 전용 등)와 별개로, 로그인 없인 어차피 못 보는 개인/비공개 영역은 크롤링
// 자체를 여기서 막는다 - noindex 메타는 "이미 링크된 페이지를 색인에서
// 빼는" 용도라 크롤링을 막는 이 파일과 상호보완적이다.
export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: "*",
      allow: "/",
      disallow: ["/mypage", "/diet", "/rooms", "/auth/callback", "/signup/profile", "/signup/targets", "/signup/success"],
    },
    sitemap: "https://zerodang.org/sitemap.xml",
  };
}
