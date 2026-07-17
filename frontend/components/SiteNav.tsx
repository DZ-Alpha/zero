"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const links = [
  ["/", "홈"],
  ["/diet", "캘린더"],
  ["/recipes", "레시피"],
  ["/search", "식품"],
  ["/mypage", "마이"],
] as const;

export function SiteNav() {
  const pathname = usePathname();

  return (
    <nav className="top-tabs" aria-label="주요 메뉴">
      {links.map(([href, label]) => {
        const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
        return <Link className={active ? "is-active" : ""} key={href} href={href}>{label}</Link>;
      })}
    </nav>
  );
}
