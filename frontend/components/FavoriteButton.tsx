"use client";

import { useCallback, useState } from "react";
import { LoginPromptDialog, ActionToast } from "@/components/SystemFeedback";
import { useAuthSession } from "@/hooks/useAuthSession";

export function FavoriteButton({ label, initial = false }: { label: string; initial?: boolean }) {
  const { ready, signedIn } = useAuthSession();
  const [liked, setLiked] = useState(initial);
  const [saving, setSaving] = useState(false);
  const [loginPrompt, setLoginPrompt] = useState(false);
  const [toast, setToast] = useState("");
  const clearToast = useCallback(() => setToast(""), []);

  function toggleFavorite() {
    if (!ready || !signedIn) {
      setLoginPrompt(true);
      return;
    }
    setSaving(true);
    window.setTimeout(() => {
      setLiked((current) => {
        setToast(current ? "즐겨찾기에서 뺐어요." : "즐겨찾기에 저장했어요.");
        return !current;
      });
      setSaving(false);
    }, 260);
  }

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

export function FavoriteIconButton({ label, initial = false }: { label: string; initial?: boolean }) {
  const { ready, signedIn } = useAuthSession();
  const [liked, setLiked] = useState(initial);
  const [saving, setSaving] = useState(false);
  const [loginPrompt, setLoginPrompt] = useState(false);
  const [toast, setToast] = useState("");
  const clearToast = useCallback(() => setToast(""), []);

  function toggleFavorite() {
    if (!ready || !signedIn) {
      setLoginPrompt(true);
      return;
    }
    setSaving(true);
    window.setTimeout(() => {
      setLiked((current) => {
        setToast(current ? "즐겨찾기에서 뺐어요." : "즐겨찾기에 저장했어요.");
        return !current;
      });
      setSaving(false);
    }, 260);
  }

  return (
    <>
      <button type="button" className={liked ? "heart is-liked" : "heart"} onClick={toggleFavorite} disabled={saving} aria-pressed={liked} aria-label={`${label} 즐겨찾기`}><span aria-hidden="true">♥</span></button>
      {loginPrompt && <LoginPromptDialog onClose={() => setLoginPrompt(false)} />}
      {toast && <ActionToast message={toast} onDone={clearToast} />}
    </>
  );
}
