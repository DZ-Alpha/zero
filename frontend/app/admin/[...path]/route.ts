import { NextRequest, NextResponse } from "next/server";

// TEMPORARY (2026-07-24) - CI/CD가 zerodang.org용 edge/서브도메인 라우팅을 아직
// 확정하지 않아서, 그 전까지는 이 route.ts가 frontend-admin 앱 전체(페이지+정적
// 자산+/admin/b API 프록시)를 zerodang.org/admin/**으로 리버스프록시한다. app/b/
// [...path]/route.ts(백엔드 게이트웨이 프록시)와 같은 패턴을, 대상만 게이트웨이가
// 아니라 frontend-admin 컨테이너로 바꾼 것.
//
// frontend-admin 쪽 next.config.ts의 basePath: "/admin" 설정과 반드시 짝을
// 이뤄야 한다 - basePath가 있어야 frontend-admin이 만드는 모든 경로(HTML, JS
// 청크, /admin/b API 호출)가 /admin 접두어를 달고 나가서 이 라우트 하나로 다
// 걸러진다.
//
// 복구 방법(CI/CD가 edge/서브도메인 라우팅을 확정하면):
//   1. 이 파일(frontend/app/admin/[...path]/route.ts) 삭제
//   2. frontend-admin/next.config.ts의 basePath 제거(관련 주석도 같이)
//   3. frontend-admin/Dockerfile의 헬스체크 경로를 /admin/api/health -> /api/health로 되돌림
//   4. frontend/compose.production.example.yaml의 ADMIN_APP_URL 배선 제거
const adminAppUrl = process.env.ADMIN_APP_URL?.trim().replace(/\/$/, "");

type RouteContext = { params: Promise<{ path: string[] }> };

function buildUpstream(parts: string[], search: URLSearchParams) {
  const encodedPath = parts.map(encodeURIComponent).join("/");
  const upstream = new URL(`/admin/${encodedPath}`.replace(/\/+/g, "/"), adminAppUrl!);
  search.forEach((value, key) => upstream.searchParams.append(key, value));
  return upstream;
}

async function proxy(request: NextRequest, context: RouteContext) {
  if (!adminAppUrl) {
    return NextResponse.json(
      { status: "ERROR", detail: "ADMIN_APP_URL이 설정돼 있지 않아요." },
      { status: 502 },
    );
  }

  const { path } = await context.params;
  const upstream = buildUpstream(path, request.nextUrl.searchParams);

  const headers = new Headers(request.headers);
  ["host", "connection", "content-length", "accept-encoding"].forEach((key) => headers.delete(key));

  try {
    const response = await fetch(upstream, {
      method: request.method,
      headers,
      body: ["GET", "HEAD"].includes(request.method) ? undefined : await request.arrayBuffer(),
      redirect: "manual",
      cache: "no-store",
      // /b 프록시(순수 API, 8초)보다 넉넉하게 잡는다 - 여긴 페이지 HTML+JS 청크
      // 전체를 릴레이해서 첫 로드 시 더 오래 걸릴 수 있다.
      signal: AbortSignal.timeout(15_000),
    });

    const responseHeaders = new Headers(response.headers);
    ["content-length", "content-encoding", "transfer-encoding", "connection"].forEach((key) => responseHeaders.delete(key));

    // frontend-admin이 내부 호스트(예: http://dangdang-frontend-admin:3000/admin/...)로
    // 리다이렉트하면 브라우저 입장에선 깨진다 - 같은 origin의 /admin/... 경로로 되돌린다.
    const location = responseHeaders.get("location");
    if (location?.startsWith(adminAppUrl)) {
      responseHeaders.set("location", location.replace(adminAppUrl, request.nextUrl.origin));
    }

    return new NextResponse(response.body, {
      status: response.status,
      headers: responseHeaders,
    });
  } catch {
    return NextResponse.json(
      { status: "FALLBACK", detail: "관리자 서버에 연결하지 못했어요. 잠시 후 다시 시도해 주세요." },
      { status: 502 },
    );
  }
}

export const GET = proxy;
export const HEAD = proxy;
export const POST = proxy;
export const PUT = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
