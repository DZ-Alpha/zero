export function ProductArt({ label, tone = "stone" }: { label: string; tone?: "stone" | "lime" | "blue" | "sand" }) {
  return <div className={`product-art tone-${tone}`}><span className="pack"><b>{label}</b><small>DD SELECT</small></span></div>;
}
