import { ProductDetail } from "@/components/ProductDetail";
import { Shell } from "@/components/Shell";

export default async function Page({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  return <Shell><ProductDetail slug={slug} /></Shell>;
}
