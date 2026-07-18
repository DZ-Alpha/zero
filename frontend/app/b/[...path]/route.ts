import { NextRequest, NextResponse } from "next/server";

type RouteContext = { params: Promise<{ path: string[] }> };

const serviceUrls = {
  login: process.env.LOGIN_SERVICE_URL ?? "http://127.0.0.1:8000",
  main: process.env.MAIN_SERVICE_URL ?? "http://127.0.0.1:8010",
  community: process.env.COMMUNITY_SERVICE_URL ?? "http://127.0.0.1:8012",
  recipe: process.env.RECIPE_SERVICE_URL ?? "http://127.0.0.1:8014",
  product: process.env.PRODUCT_SERVICE_URL ?? "http://127.0.0.1:8016",
  ingredients: process.env.INGREDIENTS_SERVICE_URL ?? "http://127.0.0.1:8018",
  diet: process.env.DIET_SERVICE_URL ?? "http://127.0.0.1:8020",
  admin: process.env.ADMIN_SERVICE_URL ?? "http://127.0.0.1:8008",
  ai: process.env.AI_SERVICE_URL ?? "http://127.0.0.1:8022",
} as const;

const gatewayUrl = process.env.BACKEND_GATEWAY_URL?.trim().replace(/\/$/, "");

function normalizePath(parts: string[]) {
  if (parts[0] === "receipe") return ["recipes", ...parts.slice(1)];
  return parts;
}

function selectService(parts: string[]) {
  const [first, second] = parts;
  if (["social-access", "user", "administrator-login", "administrator-signup", "webhooks"].includes(first)) return serviceUrls.login;
  if (first === "home" || (first === "search" && second === "lens")) return serviceUrls.main;
  if (first === "diet") return serviceUrls.diet;
  if (first === "recipes") return serviceUrls.recipe;
  if (first === "product" || first === "search") return serviceUrls.product;
  if (first === "tags") return serviceUrls.ingredients;
  if (first === "community") return serviceUrls.community;
  if (first === "admin") return serviceUrls.admin;
  if (first === "ai") return serviceUrls.ai;
  return serviceUrls.main;
}

function safeFallback(request: NextRequest) {
  const fallback = request.nextUrl.searchParams.get("fallback");
  if (!fallback?.startsWith("/") || fallback.startsWith("//")) return null;
  return new URL(fallback, request.nextUrl.origin);
}

function buildUpstream(parts: string[]) {
  const encodedPath = parts.map(encodeURIComponent).join("/");

  if (!gatewayUrl) {
    return new URL(`/${encodedPath}`, selectService(parts));
  }

  const gateway = new URL(gatewayUrl);
  const basePath = gateway.pathname.replace(/\/$/, "");
  const gatewayPath = basePath.endsWith("/b") ? basePath : `${basePath}/b`;
  gateway.pathname = `${gatewayPath}/${encodedPath}`.replace(/\/+/g, "/");
  return gateway;
}

async function proxy(request: NextRequest, context: RouteContext) {
  const { path } = await context.params;
  const normalizedPath = normalizePath(path);
  const upstream = buildUpstream(normalizedPath);
  request.nextUrl.searchParams.forEach((value, key) => {
    if (key !== "fallback") upstream.searchParams.append(key, value);
  });

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

    const location = responseHeaders.get("location");
    if (location?.startsWith("http://localhost:3000/")) {
      responseHeaders.set("location", location.replace("http://localhost:3000", request.nextUrl.origin));
    }

    return new NextResponse(response.body, {
      status: response.status,
      headers: responseHeaders,
    });
  } catch {
    const fallback = safeFallback(request);
    if (fallback) return NextResponse.redirect(fallback);
    return NextResponse.json(
      {
        status: "FALLBACK",
        detail: "서버에 연결하지 못했어요. 잠시 후 다시 시도해 주세요.",
      },
      { status: 502 },
    );
  }
}

export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
