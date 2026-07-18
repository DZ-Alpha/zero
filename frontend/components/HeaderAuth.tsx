"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { AUTH_CHANGE_EVENT, AUTH_KEY, LEGACY_AUTH_KEY } from "@/hooks/useAuthSession";
import { useAuthSession } from "@/hooks/useAuthSession";
import { clearAccessToken, getAccessToken, readJwtPayload } from "@/lib/api/client";
import { useUserSettings } from "@/hooks/useUserSettings";
import { ConfirmDialog } from "@/components/SystemFeedback";

function PersonIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="8" r="3.25" />
      <path d="M5.8 19c.55-4.1 2.65-6.15 6.2-6.15S17.65 14.9 18.2 19" />
    </svg>
  );
}

export function HeaderAuth() {
  const { profile } = useUserSettings();
  const { ready, signedIn } = useAuthSession();
  const [open, setOpen] = useState(false);
  const [confirmingSignOut, setConfirmingSignOut] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const tokenNickname = getAccessToken() ? readJwtPayload(getAccessToken()!)?.nickname : null;
  const displayName = profile.name?.trim() || (typeof tokenNickname === "string" ? tokenNickname.trim() : "") || "사용자";

  useEffect(() => {
    function closeOnOutside(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) setOpen(false);
    }

    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }

    document.addEventListener("mousedown", closeOnOutside);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("mousedown", closeOnOutside);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, []);

  function signOut() {
    const url = new URL(window.location.href);
    url.searchParams.delete("signedIn");
    const cleanLocation = `${url.pathname}${url.search}${url.hash}`;
    window.history.replaceState(window.history.state, "", cleanLocation);
    window.localStorage.removeItem(AUTH_KEY);
    window.localStorage.removeItem(LEGACY_AUTH_KEY);
    clearAccessToken();
    setOpen(false);
    window.dispatchEvent(new Event(AUTH_CHANGE_EVENT));
    window.location.replace(cleanLocation);
  }

  if (!ready) return <div className="header-auth-placeholder" aria-hidden="true" />;

  return (
    <>
    <div className="header-actions" ref={menuRef}>
      <button
        type="button"
        className={`header-account-trigger ${signedIn ? "is-signed-in" : "is-signed-out"}`}
        onClick={() => setOpen((current) => !current)}
        aria-label={signedIn ? `${displayName}님 계정 메뉴 열기` : "로그인 메뉴 열기"}
        aria-expanded={open}
        aria-haspopup="menu"
      >
        {signedIn ? <span aria-hidden="true">{displayName.slice(0, 1)}</span> : <PersonIcon />}
      </button>

      {open && (
        <div className="header-account-menu" role="menu">
          <p>{signedIn ? `${displayName}님` : "반가워요"}</p>
          {signedIn ? (
            <>
              <Link href="/mypage" role="menuitem" onClick={() => setOpen(false)}>마이페이지</Link>
              <button type="button" role="menuitem" onClick={() => { setOpen(false); setConfirmingSignOut(true); }}>로그아웃</button>
            </>
          ) : (
            <>
              <Link href="/login" role="menuitem" onClick={() => setOpen(false)}>로그인</Link>
              <Link href="/signup" role="menuitem" onClick={() => setOpen(false)}>회원가입</Link>
            </>
          )}
        </div>
      )}
    </div>
    {confirmingSignOut && <ConfirmDialog title="로그아웃할까요?" description="이 기기에 저장된 로그인 정보만 지워져요. 다시 로그인하면 계정 기록을 이어서 볼 수 있어요." confirmLabel="로그아웃하기" onClose={() => setConfirmingSignOut(false)} onConfirm={signOut} />}
    </>
  );
}
