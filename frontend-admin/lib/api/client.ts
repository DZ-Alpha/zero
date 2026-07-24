// main-frontend의 lib/api/client.ts와 같은 패턴이다 — 다만 이 앱은 관리자
// 전용이라 인증 방식이 다르다: 일반 유저 API는 usr={JWT_TOKEN} 쿼리 파라미터를
// 쓰지만, admin/product/ingredients의 관리자 엔드포인트(get_current_admin)는
// Authorization: Bearer 헤더만 받는다(기능명세서 API-Spec 시트 AD-01xx 기준,
// backend/admin-service/app/core/security.py 확인).
export const API_PREFIX = "/b";
export const ADMIN_TOKEN_KEY = "dangdang-admin-access-token";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly payload?: unknown,
  ) {
    super(message);
  }
}

export function getAdminToken() {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(ADMIN_TOKEN_KEY);
}

export function saveAdminToken(token: string) {
  window.localStorage.setItem(ADMIN_TOKEN_KEY, token);
}

export function clearAdminToken() {
  if (typeof window !== "undefined") window.localStorage.removeItem(ADMIN_TOKEN_KEY);
}

export function readJwtPayload(token: string): Record<string, unknown> | null {
  try {
    const encoded = token.split(".")[1];
    if (!encoded) return null;
    const normalized = encoded.replace(/-/g, "+").replace(/_/g, "/");
    const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, "=");
    return JSON.parse(decodeURIComponent(Array.from(atob(padded), (char) => `%${char.charCodeAt(0).toString(16).padStart(2, "0")}`).join(""))) as Record<string, unknown>;
  } catch {
    return null;
  }
}

function apiUrl(path: string) {
  const normalized = path.startsWith("/") ? path : `/${path}`;
  return `${API_PREFIX}${normalized}`;
}

// 이 앱은 admin-service/product-service/ingredients-service를 전부 같은
// b-gateway(/b) 경유로 호출한다 — 관리자 프론트가 별도 도메인/서브도메인으로
// 뜰 경우, 그 호스트에서도 /b/* 가 b-gateway로 라우팅되도록 인프라(CI/CD) 쪽
// 라우팅 설정이 맞춰져 있어야 한다(2026-07-22 CI/CD 협의 참고).
export async function adminApiRequest<T>(path: string, init: RequestInit = {}, token?: string | null): Promise<T> {
  const authToken = token ?? getAdminToken();
  const response = await fetch(apiUrl(path), {
    cache: "no-store",
    ...init,
    headers: {
      Accept: "application/json",
      ...(init.body ? { "Content-Type": "application/json" } : {}),
      ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}),
      ...init.headers,
    },
  });

  // admin-service의 get_current_admin이 슬라이딩 세션 갱신 토큰을 이 헤더로
  // 내려준다(app/core/security.py 참고) — main-frontend와 같은 패턴.
  const refreshedToken = response.headers.get("x-refreshed-token");
  if (response.ok && refreshedToken && typeof window !== "undefined") saveAdminToken(refreshedToken);

  const contentType = response.headers.get("content-type") ?? "";
  const payload = contentType.includes("application/json")
    ? await response.json()
    : await response.text();

  if (!response.ok) {
    const detail = typeof payload === "object" && payload && "detail" in payload
      ? String((payload as { detail: unknown }).detail)
      : "요청을 처리하지 못했어요.";
    if (response.status === 401 && typeof window !== "undefined") {
      clearAdminToken();
    }
    throw new ApiError(detail, response.status, payload);
  }

  return payload as T;
}
