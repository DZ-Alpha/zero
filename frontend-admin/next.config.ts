import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // TEMPORARY (2026-07-24) - CI/CD가 zerodang.org용 edge/서브도메인 라우팅을 아직
  // 확정하지 않아서, 그 전까지는 frontend(메인)가 /admin/** 요청을 이 앱으로
  // 리버스프록시하는 임시 방식을 쓴다(frontend/app/admin/[...path]/route.ts 참고).
  // 이 방식이 통하려면 이 앱이 만드는 모든 경로(정적 자산 포함)가 /admin 접두어를
  // 달고 나가야 해서 basePath가 필요하다. 나중에 CI/CD가 edge 레벨(nginx/Cloudflare)
  // 이나 서브도메인(admin.zerodang.org)으로 라우팅을 확정하면:
  //   1. frontend/app/admin/[...path]/route.ts 삭제
  //   2. 아래 basePath 제거(서브도메인이면 필요 없고, edge 경로 라우팅이면 그쪽에서
  //      경로를 그대로 넘겨주는지 먼저 확인)
  //   3. compose.production.example.yaml의 ADMIN_APP_URL 관련 배선 제거
  basePath: "/admin",
  output: "standalone",
  poweredByHeader: false,
  reactStrictMode: true,
  async headers() {
    return [{
      source: "/:path*",
      headers: [
        { key: "X-Content-Type-Options", value: "nosniff" },
        { key: "X-Frame-Options", value: "DENY" },
        { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
        { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
        // 관리자 페이지는 검색엔진에 노출될 이유가 없다.
        { key: "X-Robots-Tag", value: "noindex, nofollow" },
      ],
    }];
  },
};

export default nextConfig;
