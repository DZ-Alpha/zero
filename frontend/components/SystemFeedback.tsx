"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { AUTH_EXPIRED_EVENT } from "@/lib/api/client";

export function ConfirmDialog({
  title,
  description,
  confirmLabel,
  cancelLabel = "취소",
  destructive = false,
  busy = false,
  onConfirm,
  onClose,
}: {
  title: string;
  description: string;
  confirmLabel: string;
  cancelLabel?: string;
  destructive?: boolean;
  busy?: boolean;
  onConfirm: () => void;
  onClose: () => void;
}) {
  const cancelRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    cancelRef.current?.focus();
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape" && !busy) onClose();
    }
    document.addEventListener("keydown", closeOnEscape);
    return () => document.removeEventListener("keydown", closeOnEscape);
  }, [busy, onClose]);

  return (
    <div className="system-dialog-backdrop" role="presentation" onMouseDown={() => !busy && onClose()}>
      <section className="system-dialog" role="alertdialog" aria-modal="true" aria-labelledby="system-dialog-title" aria-describedby="system-dialog-description" onMouseDown={(event) => event.stopPropagation()}>
        <span className="system-dialog-mark" aria-hidden="true" />
        <h2 id="system-dialog-title">{title}</h2>
        <p id="system-dialog-description">{description}</p>
        <div>
          <button ref={cancelRef} type="button" onClick={onClose} disabled={busy}>{cancelLabel}</button>
          <button type="button" className={destructive ? "is-destructive" : "is-primary"} onClick={onConfirm} disabled={busy}>{busy ? "처리하고 있어요" : confirmLabel}</button>
        </div>
      </section>
    </div>
  );
}

export function LoginPromptDialog({ onClose }: { onClose: () => void }) {
  const loginRef = useRef<HTMLAnchorElement>(null);
  useEffect(() => {
    loginRef.current?.focus();
    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    document.addEventListener("keydown", closeOnEscape);
    return () => document.removeEventListener("keydown", closeOnEscape);
  }, [onClose]);

  return (
    <div className="system-dialog-backdrop" role="presentation" onMouseDown={onClose}>
      <section className="system-dialog auth-required-dialog" role="dialog" aria-modal="true" aria-labelledby="login-required-title" onMouseDown={(event) => event.stopPropagation()}>
        <span className="system-dialog-mark" aria-hidden="true" />
        <h2 id="login-required-title">로그인하면 이어서 저장할 수 있어요.</h2>
        <p>즐겨찾기와 식단 기록을 계정에 남기려면 먼저 로그인해 주세요.</p>
        <div><button type="button" onClick={onClose}>다음에</button><Link ref={loginRef} href="/login" className="is-primary">로그인하기</Link></div>
      </section>
    </div>
  );
}

export function SessionExpiredNotice() {
  const [open, setOpen] = useState(false);
  useEffect(() => {
    const show = () => setOpen(true);
    window.addEventListener(AUTH_EXPIRED_EVENT, show);
    return () => window.removeEventListener(AUTH_EXPIRED_EVENT, show);
  }, []);
  if (!open) return null;
  return (
    <div className="session-expired-notice" role="alert">
      <div><b>로그인이 만료됐어요.</b><span>다시 로그인하면 하던 내용을 이어갈 수 있어요.</span></div>
      <Link href="/login">다시 로그인</Link>
      <button type="button" onClick={() => setOpen(false)} aria-label="알림 닫기">×</button>
    </div>
  );
}

export function ActionToast({ message, onDone }: { message: string; onDone?: () => void }) {
  useEffect(() => {
    const timeout = window.setTimeout(() => onDone?.(), 1900);
    return () => window.clearTimeout(timeout);
  }, [message, onDone]);
  return <div className="action-toast" role="status"><span aria-hidden="true" />{message}</div>;
}
