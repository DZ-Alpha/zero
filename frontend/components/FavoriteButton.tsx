"use client";

import { useCallback, useState } from "react";
import { LoginPromptDialog, ActionToast } from "@/components/SystemFeedback";
import { useAuthSession } from "@/hooks/useAuthSession";
import { toggleProductFavorite, toggleRecipeFavorite } from "@/lib/api/zerocheck";

export type FavoriteKind = "product" | "recipe";

function toggleRemote(kind: FavoriteKind, id: string | number, token: string) {
  return kind === "product" ? toggleProductFavorite(String(id), token) : toggleRecipeFavorite(Number(id), token);
}

// 2026-07-19: 서버 찜 API(PR-0307/0308, RC-0111/0112)에 실제로 연결한다.
// 목록/상세 진입 시 서버에 이미 찜한 상태인지는 아직 조회하지 않는다(N+1 방지 위해
// 별도 벌크 조회가 필요 — 지금은 initial prop 그대로 사용, 항상 false 기본값).
function useFavoriteToggle(id: string | number | null | undefined, kind: FavoriteKind, initial: boolean) {
  const { ready, signedIn, token } = useAuthSession();
  const [liked, setLiked] = useState(initial);
  const [saving, setSaving] = useState(false);
  const [loginPrompt, setLoginPrompt] = useState(false);
  const [toast, setToast] = useState("");
  const clearToast = useCallback(() => setToast(""), []);

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
};

export function FavoriteButton({ label, id, kind, initial = false }: FavoriteButtonProps) {
  const { liked, saving, loginPrompt, setLoginPrompt, toast, clearToast, toggleFavorite } = useFavoriteToggle(id, kind, initial);

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

export function FavoriteIconButton({ label, id, kind, initial = false }: FavoriteButtonProps) {
  const { liked, saving, loginPrompt, setLoginPrompt, toast, clearToast, toggleFavorite } = useFavoriteToggle(id, kind, initial);

  return (
    <>
      <button type="button" className={liked ? "heart is-liked" : "heart"} onClick={toggleFavorite} disabled={saving} aria-pressed={liked} aria-label={`${label} 즐겨찾기`}><span aria-hidden="true">♥</span></button>
      {loginPrompt && <LoginPromptDialog onClose={() => setLoginPrompt(false)} />}
      {toast && <ActionToast message={toast} onDone={clearToast} />}
    </>
  );
}
