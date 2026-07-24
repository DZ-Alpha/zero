"use client";

import { useCallback, useEffect, useState } from "react";
import { AdminIdentity, getAdminMe } from "@/lib/api/admin";
import { clearAdminToken, getAdminToken, saveAdminToken } from "@/lib/api/client";

export function useAdminSession() {
  const [ready, setReady] = useState(false);
  const [token, setToken] = useState<string | null>(null);
  const [identity, setIdentity] = useState<AdminIdentity | null>(null);

  useEffect(() => {
    let active = true;
    const stored = getAdminToken();
    if (!stored) {
      setReady(true);
      return;
    }
    getAdminMe(stored)
      .then((value) => {
        if (!active) return;
        setToken(stored);
        setIdentity(value);
      })
      .catch(() => {
        // 토큰이 만료/무효면 조용히 로그아웃 상태로 남긴다 — 로그인 페이지가 유도한다.
        if (active) clearAdminToken();
      })
      .finally(() => {
        if (active) setReady(true);
      });
    return () => {
      active = false;
    };
  }, []);

  const login = useCallback((newToken: string, newIdentity: AdminIdentity) => {
    saveAdminToken(newToken);
    setToken(newToken);
    setIdentity(newIdentity);
  }, []);

  const logout = useCallback(() => {
    clearAdminToken();
    setToken(null);
    setIdentity(null);
  }, []);

  return { ready, signedIn: Boolean(token && identity), token, identity, login, logout };
}
