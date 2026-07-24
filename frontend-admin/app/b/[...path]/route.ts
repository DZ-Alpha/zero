import { NextRequest, NextResponse } from "next/server";

// frontend/app/b/[...path]/route.ts와 같은 패턴이다 - 브라우저는 상대경로 /b/*로만
// 호출하고, 이 라우트가 서버사이드에서 실제 게이트웨이로 전달한다.
//
// main-frontend와 달리 서비스별 직접 URL로 우회하는 폴백은 두지 않는다 - 관리자
// 앱이 쓰는 POST /admin(manage-item/manage-nutrients/create-tag 등)은
// product-service와 ingredients-service 사이의 분기가 b-gateway의 Lua 라우팅
// 로직(infra/b-gateway/nginx.conf)에만 있어서, 게이트웨이를 거치지 않으면 애초에
// 재현할 방법이 없다. BACKEND_GATEWAY_URL이 없으면 그냥 502로 명확히 실패시킨다.
const gatewayUrl = process.env.BACKEND_GATEWAY_URL?.trim().replace(/\/$/, "");

type RouteContext = { params: Promise<{ path: string[] }> };

function buildUpstream(parts: string[], search: URLSearchParams) {
  const encodedPath = parts.map(encodeURIComponent).join("/");
  const gateway = new URL(gatewayUrl!);
  const basePath = gateway.pathname.replace(/\/$/, "");
  const gatewayPath = basePath.endsWith("/b") ? basePath : `${basePath}/b`;
  gateway.pathname = `${gatewayPath}/${encodedPath}`.replace(/\/+/g, "/");
  search.forEach((value, key) => gateway.searchParams.append(key, value));
  return gateway;
}

async function proxy(request: NextRequest, context: RouteContext) {
  if (!gatewayUrl) {
    return NextResponse.json(
      { status: "ERROR", detail: "BACKEND_GATEWAY_URL이 설정돼 있지 않아요." },
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
      signal: AbortSignal.timeout(8_000),
    });

    const responseHeaders = new Headers(response.headers);
    ["content-length", "content-encoding", "transfer-encoding", "connection"].forEach((key) => responseHeaders.delete(key));

    return new NextResponse(response.body, {
      status: response.status,
      headers: responseHeaders,
    });
  } catch {
    return NextResponse.json(
      { status: "FALLBACK", detail: "서버에 연결하지 못했어요. 잠시 후 다시 시도해 주세요." },
      { status: 502 },
    );
  }
}

export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
