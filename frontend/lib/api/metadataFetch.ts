// generateMetadata()는 서버에서만 실행되는데, lib/api/client.ts의 apiRequest는
// "/b/..." 상대경로로 fetch한다 - 브라우저에선 현재 origin 기준으로 풀리지만
// Node 서버 컨텍스트엔 그런 기준이 없어 상대경로 fetch가 그냥 실패한다. app/b/
// [...path]/route.ts가 쓰는 것과 같은 서비스 URL 환경변수로 백엔드에 절대경로로
// 바로 붙는다(그 프록시를 다시 거치는 자기 자신 호출 왕복을 피함).
const gatewayUrl = process.env.BACKEND_GATEWAY_URL?.trim().replace(/\/$/, "");
const productServiceUrl = process.env.PRODUCT_SERVICE_URL ?? "http://127.0.0.1:8016";
const recipeServiceUrl = process.env.RECIPE_SERVICE_URL ?? "http://127.0.0.1:8014";

function backendUrl(serviceBase: string, path: string, searchParams?: Record<string, string>) {
  let url: URL;
  if (gatewayUrl) {
    const gateway = new URL(gatewayUrl);
    const basePath = gateway.pathname.replace(/\/$/, "");
    const gatewayPath = basePath.endsWith("/b") ? basePath : `${basePath}/b`;
    gateway.pathname = `${gatewayPath}${path}`.replace(/\/+/g, "/");
    url = gateway;
  } else {
    url = new URL(path, serviceBase);
  }
  if (searchParams) {
    Object.entries(searchParams).forEach(([key, value]) => url.searchParams.set(key, value));
  }
  return url;
}

// 실패해도(백엔드 미기동 등) generateMetadata 자체가 페이지 렌더를 막으면
// 안 되니, 호출부가 항상 try/catch로 감싸고 실패 시 data/catalog.ts 목업으로
// 대체한다(컴포넌트 쪽 기존 폴백 패턴과 동일).
export async function fetchProductForMetadata(id: string): Promise<{ name?: string | null; brand?: string | null; dang?: number | null; cal?: number | null } | null> {
  const url = backendUrl(productServiceUrl, "/product", { id });
  const response = await fetch(url, { cache: "no-store", signal: AbortSignal.timeout(3000) });
  if (!response.ok) return null;
  return response.json();
}

export async function fetchRecipeForMetadata(id: number): Promise<{ name?: string | null; nutrition?: { totalSugarG?: number | null; totalKcal?: number | null } | null } | null> {
  const url = backendUrl(recipeServiceUrl, `/recipes/${id}`);
  const response = await fetch(url, { cache: "no-store", signal: AbortSignal.timeout(3000) });
  if (!response.ok) return null;
  return response.json();
}
