export const API_PREFIX = "/b";
export const AUTH_TOKEN_KEY = "dangdang-access-token";
export const AUTH_EXPIRED_EVENT = "dangdang-auth-expired";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly payload?: unknown,
  ) {
    super(message);
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

  const refreshedToken = response.headers.get("x-refreshed-token");
  if (refreshedToken && typeof window !== "undefined") saveAccessToken(refreshedToken);

  const contentType = response.headers.get("content-type") ?? "";
  const payload = contentType.includes("application/json")
    ? await response.json()
    : await response.text();

  if (!response.ok) {
    const detail = typeof payload === "object" && payload && "detail" in payload
      ? String((payload as { detail: unknown }).detail)
      : "요청을 처리하지 못했어요.";
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
