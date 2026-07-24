"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { AdminNav } from "@/components/AdminNav";
import { useAdminSession } from "@/hooks/useAdminSession";

export function AdminShell({ children }: { children: React.ReactNode }) {
  const { ready, signedIn, identity, logout } = useAdminSession();
  const router = useRouter();

  useEffect(() => {
    if (ready && !signedIn) router.replace("/login");
  }, [ready, signedIn, router]);

  if (!ready) return <div className="auth-loading">확인하고 있어요…</div>;
  if (!signedIn) return <div className="auth-loading">로그인 화면으로 이동하고 있어요…</div>;

  function handleLogout() {
    logout();
    router.replace("/login");
  }

  return (
    <div className="admin-shell">
      <AdminNav identity={identity} onLogout={handleLogout} />
      <main className="admin-main">{children}</main>
    </div>
  );
}
