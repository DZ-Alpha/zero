import Link from "next/link";
import type { ProductData } from "@/data/catalog";
import { SafeImage } from "@/components/SafeImage";

type SwapCardProps = {
  current: Pick<ProductData, "slug" | "title" | "brand" | "serving" | "sugar" | "calories" | "image">;
  alternatives: Array<Pick<ProductData, "slug" | "title" | "brand" | "serving" | "sugar" | "calories" | "image">>;
  eyebrow?: string;
  title?: string;
};

function number(value: number) {
  return new Intl.NumberFormat("ko-KR", { maximumFractionDigits: 2 }).format(value);
}

export function SwapCard({ current, alternatives, eyebrow = "당류를 가볍게 바꾸는 방법", title = "이거 대신 이건 어때요?" }: SwapCardProps) {
  const best = alternatives[0];
  const saved = best ? Math.max(0, current.sugar - best.sugar) : 0;

  return (
    <section className="swap-card wrap" aria-labelledby="swap-card-title">
      <header className="swap-card-heading">
        <div>
          <p className="eyebrow">{eyebrow}</p>
          <h2 id="swap-card-title">{title}</h2>
          <p>비슷한 즐거움은 남기고, 영양성분표의 당류만 비교해요.</p>
        </div>
        <span className="swap-card-delta" aria-label={`${number(saved)}그램 낮아요`}>
          <strong>{number(saved)}g</strong>
          <small>낮아요</small>
        </span>
      </header>

      <div className="swap-card-flow">
        <Link className="swap-product swap-product-current" href={`/product/${current.slug}`}>
          <span className="swap-product-label">지금 고른다면</span>
          <div className="swap-product-image"><SafeImage src={current.image} alt={`${current.title} 제품 이미지`} /></div>
          <strong>{current.title}</strong>
          <small>{current.brand} · {current.serving}</small>
          <b>{number(current.sugar)}<i>g 당류</i></b>
        </Link>

        <div className="swap-arrow" aria-hidden="true">→</div>

        <div className="swap-product-list">
          {alternatives.slice(0, 2).map((product, index) => {
            const productSaved = Math.max(0, current.sugar - product.sugar);
            return (
              <Link className="swap-product swap-product-alternative" href={`/product/${product.slug}`} key={product.slug}>
                <span className="swap-product-label">추천 {index + 1}</span>
                <div className="swap-product-image"><SafeImage src={product.image} alt={`${product.title} 제품 이미지`} /></div>
                <span className="swap-product-copy">
                  <strong>{product.title}</strong>
                  <small>{product.brand} · {product.serving}</small>
                  <b>{number(product.sugar)}<i>g 당류</i></b>
                </span>
                <em>{number(productSaved)}g 적어요</em>
              </Link>
            );
          })}
        </div>
      </div>

      <footer className="swap-card-footer">
        <span>제품 사진과 성분표를 함께 비교했어요.</span>
        <Link href="/search">저당 제품 더 찾아보기 →</Link>
      </footer>
    </section>
  );
}
