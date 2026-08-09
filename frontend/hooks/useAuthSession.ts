"use client";

import { useEffect, useState } from "react";
import { AUTH_TOKEN_KEY } from "@/lib/api/client";

export const AUTH_KEY = "dangdang-auth-session";
export const LEGACY_AUTH_KEY = "dangdang-demo-auth";
export const AUTH_CHANGE_EVENT = "dangdang-auth-change";
const MOCK_MODE = process.env.NEXT_PUBLIC_MOCK_MODE === "1";

function readAuthSession() {
  if (typeof window === "undefined") return false;
  return MOCK_MODE || Boolean(window.localStorage.getItem(AUTH_TOKEN_KEY));
}

export function useAuthSession() {
  const [ready, setReady] = useState(MOCK_MODE);
  const [signedIn, setSignedIn] = useState(MOCK_MODE);
  const [token, setToken] = useState<string | null>(null);

  useEffect(() => {
    function syncSession() {
      setSignedIn(readAuthSession());
      setToken(window.localStorage.getItem(AUTH_TOKEN_KEY));
      setReady(true);
    }

    syncSession();
    window.addEventListener("storage", syncSession);
    window.addEventListener(AUTH_CHANGE_EVENT, syncSession);
    return () => {
      window.removeEventListener("storage", syncSession);
      window.removeEventListener(AUTH_CHANGE_EVENT, syncSession);
    };
  }, []);

  return { ready, signedIn, token, isMockSession: MOCK_MODE || (signedIn && !token) };
}
