"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { AdminIdentity } from "@/lib/api/admin";

const NAV_GROUPS: { title: string; links: { href: string; label: string }[] }[] = [
  {
    title: "상품 관리",
    links: [
      { href: "/admin/manage-item", label: "상품 등록·수정" },
      { href: "/admin/nutrients", label: "영양성분 등록" },
      { href: "/admin/ingredients", label: "원재료·알레르기 등록" },
    ],
  },
  {
    title: "사용자 데이터 분석",
    links: [
      { href: "/admin/research", label: "검색·비교·AI 패턴 분석" },
      { href: "/admin/suggestion", label: "개선 제안" },
    ],
  },
  {
    title: "운영",
    links: [{ href: "/admin/dashboard", label: "모니터링 대시보드" }],
  },
];

export function AdminNav({ identity, onLogout }: { identity: AdminIdentity | null; onLogout: () => void }) {
  const pathname = usePathname();

  return (
    <aside className="admin-sidebar">
      <h1>당당 관리자</h1>
      <p>{identity?.loginId ?? "-"}로 로그인됨</p>
      {NAV_GROUPS.map((group) => (
        <div className="admin-nav-group" key={group.title}>
          <h2>{group.title}</h2>
          {group.links.map((link) => (
            <Link href={link.href} key={link.href} className={pathname === link.href ? "is-active" : ""}>
              {link.label}
            </Link>
          ))}
        </div>
      ))}
      <button type="button" className="admin-logout" onClick={onLogout}>
        로그아웃
      </button>
    </aside>
  );
}
