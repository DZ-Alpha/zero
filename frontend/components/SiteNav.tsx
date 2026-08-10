"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const links = [
  ["/", "오늘"],
  ["/rooms", "얌로그"],
  ["/diet", "기록"],
  ["/recipes", "레시피"],
  ["/search", "저당 제품"],
  ["/mypage", "MY"],
] as const;

export function SiteNav() {
  const pathname = usePathname();

  return <nav className="top-tabs" aria-label="주요 메뉴">
    {links.map(([href, label]) => {
      const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
      return <Link className={active ? "is-active" : ""} key={href} href={href}>{label}</Link>;
    })}
  </nav>;
}

export function MobileNav() {
  const pathname = usePathname();

  return <nav className="bottom-nav" aria-label="모바일 주요 메뉴">
    {links.map(([href, label]) => {
      const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
      const iconKey = href === "/search" ? "product" : label;
      return (
        <Link className={active ? "is-active" : ""} key={href} href={href}>
          <span className={`bottom-nav-icon bottom-nav-icon-${iconKey}`} aria-hidden="true" />
          <span>{label}</span>
        </Link>
      );
    })}
  </nav>;
}
