import type { Metadata } from "next";
import { ProductDetail } from "@/components/ProductDetail";
import { Shell } from "@/components/Shell";
import { productBySlug, products } from "@/data/catalog";
import { fetchProductForMetadata } from "@/lib/api/metadataFetch";

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const { slug } = await params;
  const catalogDetail = productBySlug[slug] ?? products.find((product) => product.backendId === slug) ?? null;
  const productId = catalogDetail?.backendId
    ?? (/^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(slug) ? slug : null);

  let name = catalogDetail?.title ?? null;
  let brand = catalogDetail?.brand ?? null;
  let sugar = catalogDetail?.sugar ?? null;
  let calories = catalogDetail?.calories ?? null;

  if (productId) {
    try {
      const live = await fetchProductForMetadata(productId);
      if (live?.name) name = live.name;
      if (live?.brand) brand = live.brand;
      if (typeof live?.dang === "number") sugar = live.dang;
      if (typeof live?.cal === "number") calories = live.cal;
    } catch {
      // 백엔드 미응답 - 위 카탈로그 목업 값을 그대로 쓴다.
    }
  }

  if (!name) {
    return { title: "제품 정보", description: "당당에서 제품의 당류와 칼로리를 확인해보세요." };
  }

  const description = [brand, sugar != null ? `당류 ${sugar}g` : null, calories != null ? `${calories}kcal` : null]
    .filter(Boolean)
    .join(" · ") || `${name} - 당당에서 성분과 영양정보를 확인해보세요.`;

  return {
    title: name,
    description,
    openGraph: { title: name, description },
  };
}

export default async function Page({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  return <Shell><ProductDetail slug={slug} /></Shell>;
}
