import { NextRequest, NextResponse } from "next/server";

// frontend/app/b/[...path]/route.ts와 같은 패턴이다 - 브라우저는 상대경로 /b/*로만
// 호출하고, 이 라우트가 서버사이드에서 백엔드로 전달한다.
//
// 예전엔 "POST /admin의 menu 분기는 b-gateway Lua에만 있다"는 이유로 게이트웨이
// 없이는 502로 실패시켰는데, 그 게이트웨이가 k8s 전환에서 제거되면서 관리자 앱
// 전체가 중단되는 장애가 났다(Istio 전환 요청서 서두). 지금은 관리자 API가
// 경로 기반으로 분리돼서(§1: /admin/products/* → product-service, /admin/tags/*
// → ingredients-service, /admin/me → admin-service) 서비스별 직접 라우팅이
// 가능하다. BACKEND_GATEWAY_URL이 설정돼 있으면 여전히 게이트웨이를 우선한다.
const serviceUrls = {
  login: process.env.LOGIN_SERVICE_URL ?? "http://127.0.0.1:8000",
  admin: process.env.ADMIN_SERVICE_URL ?? "http://127.0.0.1:8008",
  product: process.env.PRODUCT_SERVICE_URL ?? "http://127.0.0.1:8016",
  ingredients: process.env.INGREDIENTS_SERVICE_URL ?? "http://127.0.0.1:8018",
} as const;

const gatewayUrl = process.env.BACKEND_GATEWAY_URL?.trim().replace(/\/$/, "");

type RouteContext = { params: Promise<{ path: string[] }> };

// 레거시 POST /b/admin의 menu 분기(태그 계열 → ingredients, 그 외 → product).
// frontend-admin 자신은 이미 새 경로를 쓰므로, 배포 전환기에 캐시된 구버전
// 클라이언트가 남아 있을 때만 탄다.
const TAG_MENUS = new Set(["create-tag", "update-tag", "deactivate-tag"]);

function selectService(parts: string[], bodyText: string | null) {
  const [first, second] = parts;
  if (["social-access", "user", "administrator-login", "administrator-signup", "webhooks", "api"].includes(first)) return serviceUrls.login;
  if (first === "admin") {
    if (second === "products") return serviceUrls.product;
    if (second === "tags") return serviceUrls.ingredients;
    if (second === undefined && bodyText) {
      try {
        const menu = (JSON.parse(bodyText) as { menu?: unknown }).menu;
        return typeof menu === "string" && TAG_MENUS.has(menu) ? serviceUrls.ingredients : serviceUrls.product;
      } catch {
        return serviceUrls.product;
      }
    }
    return serviceUrls.admin; // /b/admin/me 등
  }
  if (first === "tags") return serviceUrls.ingredients;
  if (first === "product" || first === "search") return serviceUrls.product;
  return serviceUrls.admin;
}

function buildUpstream(parts: string[], serviceBase: string | null, search: URLSearchParams) {
  const encodedPath = parts.map(encodeURIComponent).join("/");

  let upstream: URL;
  if (gatewayUrl) {
    upstream = new URL(gatewayUrl);
    const basePath = upstream.pathname.replace(/\/$/, "");
    const gatewayPath = basePath.endsWith("/b") ? basePath : `${basePath}/b`;
    upstream.pathname = `${gatewayPath}/${encodedPath}`.replace(/\/+/g, "/");
  } else {
    upstream = new URL(`/${encodedPath}`, serviceBase ?? serviceUrls.admin);
  }
  search.forEach((value, key) => upstream.searchParams.append(key, value));
  return upstream;
}

async function proxy(request: NextRequest, context: RouteContext) {
  const { path } = await context.params;
  const hasBody = !["GET", "HEAD"].includes(request.method);
  const bodyBuffer = hasBody ? await request.arrayBuffer() : undefined;

  let serviceBase: string | null = null;
  if (!gatewayUrl) {
    const bodyText = bodyBuffer && path.length === 1 && path[0] === "admin" ? new TextDecoder().decode(bodyBuffer) : null;
    serviceBase = selectService(path, bodyText);
  }

  const upstream = buildUpstream(path, serviceBase, request.nextUrl.searchParams);

  const headers = new Headers(request.headers);
  ["host", "connection", "content-length", "accept-encoding"].forEach((key) => headers.delete(key));

  try {
    const response = await fetch(upstream, {
      method: request.method,
      headers,
      body: bodyBuffer,
      redirect: "manual",
      cache: "no-store",
      signal: AbortSignal.any([request.signal, AbortSignal.timeout(8_000)]),
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
