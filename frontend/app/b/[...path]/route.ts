import { NextRequest, NextResponse } from "next/server";
import { HttpRequest } from "@smithy/protocol-http";
import { SignatureV4 } from "@smithy/signature-v4";
import { Sha256 } from "@aws-crypto/sha256-js";
import { fromNodeProviderChain } from "@aws-sdk/credential-providers";

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
// 얌로그(rooms)가 보여주는 식단 사진 presigned URL 전용 - MinIO의 SigV4
// 서명은 host와 경로 전체를 포함한다(SignedHeaders=host). b-gateway를 거치면
// nginx가 "/b"를 벗겨내는 rewrite를 타면서 서명 당시 경로와 실제 도착 경로가
// 달라져 SignatureDoesNotMatch가 난다(실사용 중 재현). 이 프록시는 Node
// fetch로 경로를 한 글자도 안 건드리고 그대로 넘기므로, diet-service가
// 내부 MinIO 주소로 서명한 경로 그대로 게이트웨이를 거치지 않고 MinIO에
// 직접 요청한다.
const minioUrl = process.env.MINIO_URL?.trim().replace(/\/$/, "");

// SSE(/b/ai/chatbot/stream 등)는 LLM 응답이 오래 이어진다 — 기존 b-gateway의
// proxy_read_timeout 120s와 맞춘다(Istio 전환 요청서 §5). 업로드는 10MB 사진이
// 느린 회선에서 8초를 넘길 수 있어 별도로 늘린다. 나머지 일반 API는 8초 유지.
const DEFAULT_TIMEOUT_MS = 8_000;
const SSE_TIMEOUT_MS = 130_000;
const UPLOAD_TIMEOUT_MS = 60_000;

// ai(챗봇)만 Lambda Function URL이고, 스트리밍 응답 때문에 AWS_IAM 인증이 필수다
// (API Gateway는 SSE를 못 버틴다 - docs/01-code-blockers.md ⑧). Function URL은
// SigV4로 서명된 요청만 받으므로, 브라우저 fetch가 못 하는 서명을 여기(서버쪽
// Node 런타임)에서 대신 해준다. 크리덴셜은 fromNodeProviderChain이 알아서 찾는다
// (~/.aws/credentials, 환경변수, SSO 등) - 여기 하드코딩하지 않는다.
const LAMBDA_FUNCTION_URL_HOST_RE = /\.lambda-url\.([a-z0-9-]+)\.on\.aws$/;
// 리전별로 따로 캐시한다. 서명자를 하나만 들고 있으면 첫 호출의 리전이 굳어버려서,
// 다른 리전의 Function URL이 생기는 순간 잘못된 리전으로 서명해 403이 난다.
const signers = new Map<string, SignatureV4>();

function getSigner(region: string) {
  let signer = signers.get(region);
  if (!signer) {
    signer = new SignatureV4({
      service: "lambda",
      region,
      sha256: Sha256,
      credentials: fromNodeProviderChain(),
    });
    signers.set(region, signer);
  }
  return signer;
}

async function signIfFunctionUrl(
  upstream: URL,
  method: string,
  headers: Headers,
  body: ArrayBuffer | undefined,
  bodyIsStreamed: boolean,
) {
  const match = upstream.hostname.match(LAMBDA_FUNCTION_URL_HOST_RE);
  if (!match) return;

  // SigV4는 본문 해시까지 서명한다. 스트리밍 본문(업로드)은 여기서 해시를 낼 수
  // 없어 "빈 본문"으로 서명되는데 실제로는 본문이 실려 나가므로 403
  // SignatureDoesNotMatch가 된다. 지금은 /b/uploads가 diet(API Gateway)로 가서
  // 이 경로에 닿지 않지만, Function URL 서비스가 업로드를 받게 되면 조용히
  // 깨진다. 원인을 못 쫓는 403 대신 여기서 소리내어 멈춘다.
  if (bodyIsStreamed) {
    throw new Error(
      `SigV4 서명 불가: ${upstream.hostname}는 Function URL인데 본문이 스트리밍이다. ` +
        "본문을 버퍼링하도록 프록시를 고치거나 UNSIGNED-PAYLOAD를 검토해야 한다.",
    );
  }

  // ai-service의 /chatbot, /chatbot/stream은 JWT를 body의 usr 필드로 받아서
  // Authorization 헤더와 충돌하지 않는다. 다만 /chatbot/history는 레거시로
  // Authorization: Bearer도 받으므로, SigV4가 그 자리를 써야 하는 이상 원래
  // 값은 백엔드가 안 보는 이름으로 옮겨서 최소한 유실은 안 시킨다(완전한 해결은
  // 아니다 - 그 엔드포인트는 usr 쿼리 파라미터 폴백으로만 로그인 상태 유지 가능,
  // app/api/chatbot.py의 2026-08-02 QA 코멘트 참고).
  const originalAuth = headers.get("authorization");
  if (originalAuth) {
    headers.set("x-app-authorization", originalAuth);
    headers.delete("authorization");
  }

  const plainHeaders: Record<string, string> = { host: upstream.host };
  headers.forEach((value, key) => {
    plainHeaders[key] = value;
  });

  // 같은 키가 여러 번 오는 쿼리(?a=1&a=2)를 살려서 서명한다. 위쪽 buildUpstream이
  // searchParams.append를 쓰기 때문에 URL에는 둘 다 남는데, Object.fromEntries는
  // 마지막 값만 남겨 뭉갠다 — 서명 대상과 실제 전송이 달라져 SignatureDoesNotMatch가
  // 난다. @smithy/signature-v4는 값으로 string[]을 받는다.
  const query: Record<string, string | string[]> = {};
  const seenKeys = new Set<string>();
  upstream.searchParams.forEach((_value, key) => {
    if (seenKeys.has(key)) return;
    seenKeys.add(key);
    const values = upstream.searchParams.getAll(key);
    query[key] = values.length > 1 ? values : values[0];
  });

  const signable = new HttpRequest({
    method,
    protocol: upstream.protocol,
    hostname: upstream.hostname,
    port: upstream.port ? Number(upstream.port) : undefined,
    path: upstream.pathname,
    query,
    headers: plainHeaders,
    body: body ? Buffer.from(body) : undefined,
  });

  const signed = await getSigner(match[1]).sign(signable);
  Object.entries(signed.headers).forEach(([key, value]) => {
    if (key.toLowerCase() === "host") return; // fetch가 URL 기준으로 다시 채운다
    headers.set(key, value as string);
  });
}

function normalizePath(parts: string[]) {
  if (parts[0] === "receipe") return ["recipes", ...parts.slice(1)];
  // b-gateway 시절부터 있던 경로 예외 - /b/ingredients/gam-list|gam-detail은
  // ingredients-service의 /community/gam-list|gam-detail로 매핑된다
  // (infra/b-gateway/nginx.conf 참고). "/b 벗기면 곧 내부 경로" 규칙의 유일한
  // 예외라 Istio 전환 명세(docs/API_ROUTING_SPEC.md)에 별도 기록돼 있다.
  if (parts[0] === "ingredients" && (parts[1] === "gam-list" || parts[1] === "gam-detail")) {
    return ["community", ...parts.slice(1)];
  }
  return parts;
}

// 서버간 전용 엔드포인트 - 브라우저가 직접 호출하면 임의 userIds로 남의
// 식단을 보거나(diet/internal) 아무 방에나 스레드를 만들 수 있다(rooms/
// internal). 백엔드에 공유 시크릿 검사가 한 번 더 있지만, 기존 b-gateway처럼
// 진입 계층에서도 404로 차단한다(Istio 전환 요청서 §4 - 이중 방어).
function isInternalOnly(parts: string[]) {
  return (parts[0] === "diet" || parts[0] === "rooms") && parts[1] === "internal";
}

function selectService(parts: string[], rawParts: string[]) {
  const [first, second] = parts;
  // /b/api/*는 login-service 소유(webhooks 등과 같은 묶음) - b-gateway 규칙과 동일.
  if (["social-access", "user", "administrator-login", "administrator-signup", "webhooks", "api"].includes(first)) return serviceUrls.login;
  // /b/home/user-sugar-calorie만 diet-service(오늘 당/칼로리 게이지), 나머지 /b/home/*은 main.
  if (first === "home") return second === "user-sugar-calorie" ? serviceUrls.diet : serviceUrls.main;
  if (first === "diet") return serviceUrls.diet;
  // gateway가 MinIO diet-photos에 저장하는 자리 — diet-service가 이 라우트를 갖는다.
  if (first === "uploads") return serviceUrls.diet;
  if (first === "recipes") return serviceUrls.recipe;
  if (first === "product" || first === "search") return serviceUrls.product;
  if (first === "tags") return serviceUrls.ingredients;
  if (first === "community") return serviceUrls.community;
  // /b/ingredients/gam-*는 normalizePath에서 community/*로 바뀌지만 소유
  // 서비스는 ingredients다 - 원본 경로(rawParts)로 판별한다.
  if (rawParts[0] === "ingredients") return serviceUrls.ingredients;
  // 얌로그(rooms)는 community-service 소유 - 예전에 이 매핑이 빠져 main으로
  // 흘러가던 버그가 있었다(Istio 전환 요청서 §3).
  if (first === "rooms") return serviceUrls.community;
  if (first === "ai") return serviceUrls.ai;
  return serviceUrls.main;
}

// 관리자 API 소유 서비스 분리(Istio 전환 요청서 §1):
//   /b/admin/me         → admin-service
//   /b/admin/products/* → product-service
//   /b/admin/tags/*     → ingredients-service
//   POST /b/admin(레거시) → body의 menu 값으로 product/ingredients 분기
//                          (b-gateway Lua 라우팅과 동일 - frontend-admin이 새
//                          경로로 전환 완료되면 제거 예정)
const _TAG_MENUS = new Set(["create-tag", "update-tag", "deactivate-tag"]);

function selectAdminService(parts: string[], bodyText: string | null) {
  const second = parts[1];
  if (second === "products") return serviceUrls.product;
  if (second === "tags") return serviceUrls.ingredients;
  if (second === undefined && bodyText) {
    try {
      const menu = (JSON.parse(bodyText) as { menu?: unknown }).menu;
      return typeof menu === "string" && _TAG_MENUS.has(menu) ? serviceUrls.ingredients : serviceUrls.product;
    } catch {
      return serviceUrls.product;
    }
  }
  return serviceUrls.admin; // /b/admin/me 등
}

function safeFallback(request: NextRequest) {
  const fallback = request.nextUrl.searchParams.get("fallback");
  if (!fallback?.startsWith("/") || fallback.startsWith("//")) return null;
  return new URL(fallback, request.nextUrl.origin);
}

function buildUpstream(parts: string[], serviceBase: string | null) {
  const encodedPath = parts.map(encodeURIComponent).join("/");

  if (parts[0] === "diet-photos" && minioUrl) {
    return new URL(`/${encodedPath}`, minioUrl);
  }

  // 상품 이미지는 공개 버킷(product-images)이라 서명 없이 그대로 MinIO로 중계한다
  // (diet-photos는 비공개+presigned지만 이건 공개 read). image_url이
  // /b/product-images/{key}로 저장돼 있어 이 경로로 들어온다.
  if (parts[0] === "product-images" && minioUrl) {
    return new URL(`/${encodedPath}`, minioUrl);
  }

  if (!gatewayUrl) {
    return new URL(`/${encodedPath}`, serviceBase ?? serviceUrls.main);
  }

  const gateway = new URL(gatewayUrl);
  const basePath = gateway.pathname.replace(/\/$/, "");
  const gatewayPath = basePath.endsWith("/b") ? basePath : `${basePath}/b`;
  gateway.pathname = `${gatewayPath}/${encodedPath}`.replace(/\/+/g, "/");
  return gateway;
}

async function proxy(request: NextRequest, context: RouteContext) {
  const { path } = await context.params;

  if (isInternalOnly(path)) {
    return NextResponse.json({ detail: "Not Found" }, { status: 404 });
  }

  const normalizedPath = normalizePath(path);
  const isUpload = path[0] === "uploads";
  const isSse = path[0] === "ai";
  const hasBody = !["GET", "HEAD"].includes(request.method);

  // 업로드는 body를 메모리에 통째로 올리지 않고 스트리밍으로 넘긴다(Istio 전환
  // 요청서 §6 - 12MB 사진 동시 업로드 시 frontend 메모리 사용량 방지). 크기/
  // MIME 검증은 diet-service(app/routers/uploads.py, 10MB + 화이트리스트)가 한다.
  // 그 외 요청은 기존대로 버퍼링 - 레거시 POST /b/admin의 menu 분기가 body를
  // 읽어야 해서다.
  const bodyBuffer = hasBody && !isUpload ? await request.arrayBuffer() : undefined;

  let serviceBase: string | null = null;
  if (!gatewayUrl) {
    if (path[0] === "admin") {
      const bodyText = bodyBuffer && path.length === 1 ? new TextDecoder().decode(bodyBuffer) : null;
      serviceBase = selectAdminService(path, bodyText);
    } else {
      serviceBase = selectService(normalizedPath, path);
    }
  }

  const upstream = buildUpstream(normalizedPath, serviceBase);
  request.nextUrl.searchParams.forEach((value, key) => {
    if (key !== "fallback") upstream.searchParams.append(key, value);
  });

  const headers = new Headers(request.headers);
  ["host", "connection", "content-length", "accept-encoding"].forEach((key) => headers.delete(key));

  const timeoutMs = isSse ? SSE_TIMEOUT_MS : isUpload ? UPLOAD_TIMEOUT_MS : DEFAULT_TIMEOUT_MS;

  await signIfFunctionUrl(upstream, request.method, headers, bodyBuffer, hasBody && isUpload);

  try {
    const response = await fetch(upstream, {
      method: request.method,
      headers,
      body: hasBody ? (isUpload ? request.body : bodyBuffer) : undefined,
      // 스트리밍 request body(업로드)는 fetch 스펙상 half-duplex 명시가 필요하다.
      ...(isUpload && hasBody ? { duplex: "half" as const } : {}),
      redirect: "manual",
      cache: "no-store",
      // 클라이언트(브라우저)가 연결을 끊으면 request.signal이 abort되고, 그때
      // upstream 요청도 같이 취소된다(Istio 전환 요청서 §5) - SSE를 130초까지
      // 열어두더라도 사용자가 떠나면 백엔드 작업을 붙들지 않는다.
      signal: AbortSignal.any([request.signal, AbortSignal.timeout(timeoutMs)]),
    });

    const responseHeaders = new Headers(response.headers);
    ["content-length", "content-encoding", "transfer-encoding", "connection"].forEach((key) => responseHeaders.delete(key));

    const location = responseHeaders.get("location");
    if (location?.startsWith("http://localhost:3000/")) {
      responseHeaders.set("location", location.replace("http://localhost:3000", request.nextUrl.origin));
    }

    // response.body를 그대로 통과시키므로 SSE 중간 응답이 버퍼링되지 않는다.
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
