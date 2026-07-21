"use client";

import { useCallback, useEffect, useState } from "react";
import { LoginPromptDialog, ActionToast } from "@/components/SystemFeedback";
import { useAuthSession } from "@/hooks/useAuthSession";
import { getProductFavorites, getRecipeFavorites, toggleProductFavorite, toggleRecipeFavorite } from "@/lib/api/zerocheck";

export type FavoriteKind = "product" | "recipe";

function toggleRemote(kind: FavoriteKind, id: string | number, token: string) {
  return kind === "product" ? toggleProductFavorite(String(id), token) : toggleRecipeFavorite(Number(id), token);
}

async function isAlreadyFavorited(kind: FavoriteKind, id: string | number, token: string) {
  if (kind === "recipe") {
    const result = await getRecipeFavorites(token);
    return result["list-receipe"].some((item) => String(item.id) === String(id));
  }
  const result = await getProductFavorites(token);
  return result["list-products"].some((item) => item.id === String(id));
}

// 2026-07-19: 서버 찜 API(PR-0307/0308, RC-0111/0112)에 실제로 연결한다.
// 목록(피드) 카드는 항목 수만큼 벌크 조회를 반복하는 N+1을 피하려고 checkInitial을
// 안 켠다 — initial prop 그대로 항상 false로 시작. 상세 페이지는 인스턴스가 하나뿐이라
// checkInitial로 서버에 이미 찜해둔 상태인지 확인한다. 이게 없으면 찜은 실제로 잘
// 저장되는데(POST는 성공) 페이지를 새로고침하거나 다시 들어올 때마다 항상 false로
// 초기화돼서 마치 찜이 풀린 것처럼 보이는 버그가 있었다.
function useFavoriteToggle(id: string | number | null | undefined, kind: FavoriteKind, initial: boolean, checkInitial = false) {
  const { ready, signedIn, token } = useAuthSession();
  const [liked, setLiked] = useState(initial);
  const [saving, setSaving] = useState(false);
  const [loginPrompt, setLoginPrompt] = useState(false);
  const [toast, setToast] = useState("");
  const clearToast = useCallback(() => setToast(""), []);

  useEffect(() => {
    if (!checkInitial || !ready || !signedIn || !token || !id) return;
    let active = true;
    isAlreadyFavorited(kind, id, token).then((favorited) => {
      if (active && favorited) setLiked(true);
    }).catch(() => {
      // 조회 실패해도 initial(false)을 유지 — 버튼을 눌러 다시 저장할 수 있다.
    });
    return () => {
      active = false;
    };
  }, [checkInitial, ready, signedIn, token, id, kind]);

  async function toggleFavorite() {
    if (!ready || !signedIn) {
      setLoginPrompt(true);
      return;
    }
    if (!id || !token) {
      setToast("지금은 찜을 저장할 수 없어요.");
      return;
    }
    setSaving(true);
    try {
      const result = await toggleRemote(kind, id, token);
      setLiked(result.liked);
      setToast(result.liked ? "즐겨찾기에 저장했어요." : "즐겨찾기에서 뺐어요.");
    } catch {
      setToast("찜 저장에 실패했어요. 다시 시도해 주세요.");
    } finally {
      setSaving(false);
    }
  }

  return { liked, saving, loginPrompt, setLoginPrompt, toast, clearToast, toggleFavorite };
}

type FavoriteButtonProps = {
  label: string;
  id?: string | number | null;
  kind: FavoriteKind;
  initial?: boolean;
  checkInitial?: boolean;
};

export function FavoriteButton({ label, id, kind, initial = false, checkInitial = false }: FavoriteButtonProps) {
  const { liked, saving, loginPrompt, setLoginPrompt, toast, clearToast, toggleFavorite } = useFavoriteToggle(id, kind, initial, checkInitial);

  return (
    <>
      <button type="button" className={liked ? "favorite-button is-liked" : "favorite-button"} aria-pressed={liked} aria-label={`${label} 즐겨찾기`} onClick={toggleFavorite} disabled={saving}>
        <span aria-hidden="true">♥</span>{saving ? "저장 중" : liked ? "저장됨" : "저장"}
      </button>
      {loginPrompt && <LoginPromptDialog onClose={() => setLoginPrompt(false)} />}
      {toast && <ActionToast message={toast} onDone={clearToast} />}
    </>
  );
}

export function FavoriteIconButton({ label, id, kind, initial = false, checkInitial = false }: FavoriteButtonProps) {
  const { liked, saving, loginPrompt, setLoginPrompt, toast, clearToast, toggleFavorite } = useFavoriteToggle(id, kind, initial, checkInitial);

  return (
    <>
      <button type="button" className={liked ? "heart is-liked" : "heart"} onClick={toggleFavorite} disabled={saving} aria-pressed={liked} aria-label={`${label} 즐겨찾기`}><span aria-hidden="true">♥</span></button>
      {loginPrompt && <LoginPromptDialog onClose={() => setLoginPrompt(false)} />}
      {toast && <ActionToast message={toast} onDone={clearToast} />}
    </>
  );
}
