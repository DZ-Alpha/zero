import Link from "next/link";
import { AdminShell } from "@/components/AdminShell";

const shortcuts = [
  { href: "/admin/manage-item", label: "상품 등록·수정", desc: "AD-0101/0102" },
  { href: "/admin/nutrients", label: "영양성분 등록", desc: "AD-0103" },
  { href: "/admin/ingredients", label: "원재료·알레르기 등록", desc: "AD-0104" },
  { href: "/admin/research", label: "사용자 데이터 분석", desc: "AD-0109~0112" },
  { href: "/admin/suggestion", label: "개선 제안", desc: "AD-0113" },
  { href: "/admin/dashboard", label: "모니터링 대시보드", desc: "AD-0114" },
];

export default function AdminHomePage() {
  return (
    <AdminShell>
      <div className="admin-page-head">
        <h2>관리자 홈</h2>
        <p>기능명세서 AD-01xx 기준으로 구성된 관리 메뉴예요.</p>
      </div>
      <div className="admin-form-row" style={{ gridTemplateColumns: "repeat(3, 1fr)", gap: 14 }}>
        {shortcuts.map((item) => (
          <Link href={item.href} key={item.href} className="admin-card" style={{ maxWidth: "none" }}>
            <strong style={{ display: "block", marginBottom: 6 }}>{item.label}</strong>
            <small style={{ color: "var(--muted)" }}>{item.desc}</small>
          </Link>
        ))}
      </div>
    </AdminShell>
  );
}
