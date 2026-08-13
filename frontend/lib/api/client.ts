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

// 공용 fetch에 타임아웃이 없어서, 백엔드가 느려지면 요청이 무한정 매달려 있었다.
// 화면 쪽 타임아웃(RoomsHome의 Promise.race 4.5초)은 프로미스만 버릴 뿐 요청은
// 계속 살아 있어서, 사용자가 새로고침할수록 이미 포화된 서비스에 요청이 쌓였다
// (2026-08-13 감사 A-4: "느리다"가 아니라 "느려지면 더 느려진다").
//
// 15초는 관측된 최악값(rooms 5.5초)의 약 3배다. 지금 성공하는 요청을 실패로
// 바꾸지 않으면서 무한 대기만 끊는 게 목적이라 일부러 넉넉하게 잡았다.
// LLM 호출처럼 더 오래 걸리는 게 정상인 경로는 timeoutMs로 개별 조정한다.
export const DEFAULT_TIMEOUT_MS = 15_000;

export class ApiTimeoutError extends Error {
  constructor(readonly timeoutMs: number) {
    super("요청이 응답하지 않아 취소했어요.");
    this.name = "ApiTimeoutError";
  }
}

export type ApiRequestInit = RequestInit & {
  /** 0이면 타임아웃 없음(스트리밍 등). 기본 DEFAULT_TIMEOUT_MS. */
  timeoutMs?: number;
};

// AbortSignal.any()는 지원 브라우저가 아직 좁아서(Safari 17.4+) 직접 합친다.
// 호출부가 준 signal(언마운트 취소)과 타임아웃 중 먼저 오는 쪽이 요청을 끊는다.
function linkAbort(external: AbortSignal | null | undefined, timeoutMs: number) {
  const controller = new AbortController();
  let timedOut = false;

  const timer = timeoutMs > 0
    ? setTimeout(() => {
        timedOut = true;
        controller.abort();
      }, timeoutMs)
    : null;

  const onExternalAbort = () => controller.abort();
  if (external) {
    if (external.aborted) controller.abort();
    else external.addEventListener("abort", onExternalAbort, { once: true });
  }

  return {
    signal: controller.signal,
    didTimeOut: () => timedOut,
    release: () => {
      if (timer !== null) clearTimeout(timer);
      external?.removeEventListener("abort", onExternalAbort);
    },
  };
}

export async function apiRequest<T>(path: string, init: ApiRequestInit = {}): Promise<T> {
  const { timeoutMs = DEFAULT_TIMEOUT_MS, signal: callerSignal, ...rest } = init;
  const abort = linkAbort(callerSignal, timeoutMs);

  let response: Response;
  try {
    response = await fetch(apiUrl(path), {
      cache: "no-store",
      ...rest,
      signal: abort.signal,
      headers: {
        Accept: "application/json",
        ...(init.body ? { "Content-Type": "application/json" } : {}),
        ...init.headers,
      },
    });
  } catch (error) {
    // 타임아웃으로 우리가 끊은 것과 호출부가 언마운트로 끊은 것을 구분한다.
    // 후자는 그대로 AbortError로 흘려보내야 호출부의 무시 로직이 동작한다.
    if (abort.didTimeOut()) throw new ApiTimeoutError(timeoutMs);
    throw error;
  } finally {
    abort.release();
  }

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

// 실패를 조용히 삼키고 빈 값을 돌려주므로, 홈 화면은 백엔드가 느리거나 500이어도
// 그냥 빈 섹션으로 보인다 — rooms 지연(감사 A-2)이 오래 안 드러난 직접적인 이유다.
// 사용자에게 노출하는 동작은 그대로 두되(빈 섹션이 에러 토스트보다 낫다),
// 삼킨 실패는 로그에 한 줄 남긴다. label은 어느 호출이 죽었는지 구분용.
export async function withMockFallback<T>(request: () => Promise<T>, fallback: T, label?: string): Promise<T> {
  try {
    const value = await request();
    if (typeof value === "object" && value && "status" in value && (value as { status?: string }).status === "PREPARING") {
      return fallback;
    }
    return value;
  } catch (error) {
    // 언마운트로 인한 취소는 실패가 아니다 — 로그를 더럽히지 않는다.
    if (error instanceof DOMException && error.name === "AbortError") return fallback;
    console.warn(`[api] ${label ?? "request"} failed, using fallback:`, error);
    return fallback;
  }
}
