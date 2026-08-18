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
// 얌로그(rooms)가 보여주는 식단 사진 presigned URL 전용 - MinIO의 SigV4
// 서명은 host와 경로 전체를 포함한다(SignedHeaders=host). b-gateway를 거치면
// nginx가 "/b"를 벗겨내는 rewrite를 타면서 서명 당시 경로와 실제 도착 경로가
// 달라져 SignatureDoesNotMatch가 난다(실사용 중 재현). 이 프록시는 Node
// fetch로 경로를 한 글자도 안 건드리고 그대로 넘기므로, diet-service가
// 내부 MinIO 주소로 서명한 경로 그대로 게이트웨이를 거치지 않고 MinIO에
// 직접 요청한다.
const minioUrl = process.env.MINIO_URL?.trim().replace(/\/$/, "");

// AWS(EKS) 전용 - 상품/레시피 이미지는 CloudFront(OAC)가 S3를 서명 대리한다.
// 값이 있으면 /b/product-images/*, /b/recipe-images/* 를 302로 CDN에 넘긴다.
// DB의 image_url(/b/product-images/{key})은 그대로 두고 경계에서만 변환하므로
// 온프렘(MINIO_URL)과 AWS(IMAGE_CDN_URL) 어느 쪽에서도 같은 이미지가 동작한다.
// diet-photos는 대상이 아니다 - v3 diet-service가 presigned 절대 URL을 반환한다.
const imageCdnUrl = process.env.IMAGE_CDN_URL?.trim().replace(/\/$/, "");

// SSE(/b/ai/chatbot/stream 등)는 LLM 응답이 오래 이어진다 — 기존 b-gateway의
// proxy_read_timeout 120s와 맞춘다(Istio 전환 요청서 §5). 업로드는 10MB 사진이
// 느린 회선에서 기본 타임아웃을 넘길 수 있어 별도로 늘린다.
//
// 일반 API 12초 — 백엔드 커넥션 풀 대기(pool_timeout=10s,
// backend/*/app/core/database.py)보다 반드시 길어야 한다. 예전 8초는 풀 대기가
// 끝나기도 전에 프록시가 먼저 끊는 값이라, 부하가 몰리면 사용자는 502(FALLBACK)를
// 받는데 백엔드는 커넥션을 잡은 뒤 이미 끊긴 요청의 쿼리를 끝까지 돌려 부하만
// 키웠다(끊어봐야 줄어드는 게 없는 최악의 조합). 포기 순서를 "백엔드가 먼저
// 포기 → 프록시가 그 응답을 그대로 전달"로 정렬한다. pool_timeout을 올리면
// 이 값도 같이 올려야 한다.
const DEFAULT_TIMEOUT_MS = 12_000;
const SSE_TIMEOUT_MS = 130_000;
const UPLOAD_TIMEOUT_MS = 60_000;

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

  // 302 자체에 캐시를 붙인다 — 안 붙이면 브라우저가 이미지 한 장 볼 때마다
  // "어디로 가야 하냐"를 다시 물어보러 클러스터까지 왕복한다. 목적지 이미지는
  // CloudFront가 캐시해도 이 리다이렉트는 매번 오리진을 때린다(2026-08 cloudflared
  // 터널 실측: 전체 30,058건 중 12,031건, 40%가 이 302 한 줄이었다).
  //
  // 캐시 기간은 키가 내용에 대해 불변인지에 따라 갈린다:
  //   product-images/{uuid}.{ext} — 이미지가 바뀌면 새 uuid로 새 객체가 생기고
  //     DB의 image_url도 같이 바뀐다(image_storage.py). 진짜 불변이라 immutable.
  //   recipe-images/{recipe_id}.jpg — 같은 키에 덮어쓴다(recipe-processor/s3_store.py).
  //     immutable을 붙이면 재크롤로 썸네일을 교체해도 브라우저가 하루 동안 옛 사진을
  //     들고 있다. 그래서 1시간만 신선하다고 보고, 그 뒤에는 stale-while-revalidate로
  //     헌 이미지를 즉시 보여주면서 뒤에서 갱신한다 — 302 왕복은 여전히 사라지고
  //     교체 반영은 한 시간 안에 끝난다.
  //
  // NextResponse.redirect()는 헤더를 얹을 자리가 없어 응답을 직접 만든다.
  if (imageCdnUrl && (path[0] === "product-images" || path[0] === "recipe-images")) {
    const encodedPath = path.map(encodeURIComponent).join("/");
    const cacheControl =
      path[0] === "product-images"
        ? "public, max-age=86400, immutable"
        : "public, max-age=3600, stale-while-revalidate=86400";
    return new NextResponse(null, {
      status: 302,
      headers: {
        location: `${imageCdnUrl}/${encodedPath}`,
        "cache-control": cacheControl,
      },
    });
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
