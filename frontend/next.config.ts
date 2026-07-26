import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  reactStrictMode: true,
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "recipe1.ezmember.co.kr" },
      { protocol: "https", hostname: "recipe.ezmember.co.kr" },
      { protocol: "https", hostname: "product-image.kurly.com" },
      { protocol: "https", hostname: "shopping-phinf.pstatic.net" },
    ],
    // 기본 허용 품질은 75뿐이라, quality={100}(ChatWidget의 당당이 아이콘)을
    // 쓰면 최적화 요청 자체가 400으로 거부돼 원본보다 흐리게 나오던 문제가
    // 있었다 - 실제로 curl로 재현/확인함(q=75는 200, q=100은 400).
    qualities: [75, 100],
  },
  async headers() {
    return [{
      source: "/:path*",
      headers: [
        { key: "X-Content-Type-Options", value: "nosniff" },
        { key: "X-Frame-Options", value: "DENY" },
        { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
        { key: "Permissions-Policy", value: "camera=(self), microphone=(), geolocation=()" },
      ],
    }];
  },
};

export default nextConfig;
