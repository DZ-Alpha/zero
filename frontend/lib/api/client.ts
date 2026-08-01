export const API_PREFIX = "/b";
export const AUTH_TOKEN_KEY = "dangdang-access-token";
export const AUTH_EXPIRED_EVENT = "dangdang-auth-expired";

// FastAPI가 detail=str(...)로 던지는 대부분의 서비스는 payload.detail이 그냥
// 문자열이지만, community-service(얌로그 §12 오류 응답 규약)는 detail이
// {code, detail} 중첩 객체다 - 이 경우를 String()으로 바로 감싸면 JS가
// "[object Object]"로 stringify해서 그대로 토스트에 떠버린다. 두 형태 모두
// 안에 있는 실제 메시지 문자열과 code를 찾아서 쓴다.
//
// 세 번째 형태 - pydantic이 요청 바디를 검증하다 실패하면(422) FastAPI가
// detail을 문자열이 아니라 [{type, loc, msg, ...}] 배열로 준다. field_validator가
// 던진 ValueError("몸무게는 20~300kg 사이여야 해요.") 같은 메시지는 pydantic이
// msg 앞에 "Value error, "를 붙인다 - 그대로 보여주면 실제 검증 실패 이유가
// "요청을 처리하지 못했어요"로 뭉개져서 사용자가 뭘 고쳐야 하는지 알 수 없다
// (main-service/app/routers/health_profile.py의 2026-07-30 주석과 동일한 문제).
function extractDetail(payload: unknown): { message: string; code?: string } {
  if (typeof payload !== "object" || payload === null || !("detail" in payload)) {
    return { message: "요청을 처리하지 못했어요." };
  }
  const detail = (payload as { detail: unknown }).detail;
  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0] as { msg?: unknown };
    const msg = typeof first?.msg === "string" ? first.msg : null;
    return { message: msg ? msg.replace(/^Value error,\s*/, "") : "입력값을 확인해 주세요." };
  }
  if (typeof detail === "object" && detail !== null && "detail" in detail) {
    const nested = detail as { detail: unknown; code?: unknown };
    return {
      message: typeof nested.detail === "string" ? nested.detail : "요청을 처리하지 못했어요.",
      code: nested.code !== undefined ? String(nested.code) : undefined,
    };
  }
  return { message: typeof detail === "string" ? detail : "요청을 처리하지 못했어요." };
}

export class ApiError extends Error {
  readonly code?: string;

  constructor(
    message: string,
    readonly status: number,
    readonly payload?: unknown,
  ) {
    super(message);
    this.code = extractDetail(payload).code;
  }
}

export function getAccessToken() {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(AUTH_TOKEN_KEY);
}

export function saveAccessToken(token: string) {
  window.localStorage.setItem(AUTH_TOKEN_KEY, token);
}

export function clearAccessToken() {
  if (typeof window !== "undefined") window.localStorage.removeItem(AUTH_TOKEN_KEY);
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

export async function apiRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(apiUrl(path), {
    cache: "no-store",
    ...init,
    headers: {
      Accept: "application/json",
      ...(init.body ? { "Content-Type": "application/json" } : {}),
      ...init.headers,
    },
  });

  // response.ok일 때만 저장한다 — 백엔드가 토큰 디코드 성공 시 유저 존재 여부를
  // 확인하기 전에 X-Refreshed-Token부터 세팅해서, 탈퇴(404)/그 외 실패 응답에도
  // 이 헤더가 실려온다. 여기서 무조건 저장하면 회원탈퇴 직후에도 이미 삭제된
  // 유저의 토큰이 계속 갱신·저장되며 세션이 되살아나는 버그가 있었다.
  const refreshedToken = response.headers.get("x-refreshed-token");
  if (response.ok && refreshedToken && typeof window !== "undefined") saveAccessToken(refreshedToken);

  const contentType = response.headers.get("content-type") ?? "";
  const payload = contentType.includes("application/json")
    ? await response.json()
    : await response.text();

  if (!response.ok) {
    const { message: detail } = extractDetail(payload);
    if (response.status === 401 && typeof window !== "undefined") {
      clearAccessToken();
      window.localStorage.removeItem("dangdang-auth-session");
      window.localStorage.removeItem("dangdang-demo-auth");
      window.dispatchEvent(new Event("dangdang-auth-change"));
      window.dispatchEvent(new CustomEvent(AUTH_EXPIRED_EVENT, { detail }));
    }
    throw new ApiError(detail, response.status, payload);
  }

  return payload as T;
}

export async function withMockFallback<T>(request: () => Promise<T>, fallback: T): Promise<T> {
  try {
    const value = await request();
    if (typeof value === "object" && value && "status" in value && (value as { status?: string }).status === "PREPARING") {
      return fallback;
    }
    return value;
  } catch {
    return fallback;
  }
}
