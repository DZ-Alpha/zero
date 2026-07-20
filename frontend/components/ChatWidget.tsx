"use client";

import { useEffect, useState } from "react";
import { ChatPanel } from "@/components/ChatPanel";

export function ChatWidget() {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [open]);

  return (
    <>
      {open && (
        <div className="chat-widget-popup" role="dialog" aria-modal="true" aria-label="당당 상담">
          <button className="chat-widget-close" onClick={() => setOpen(false)} aria-label="상담 닫기">✕</button>
          <ChatPanel />
        </div>
      )}
      {!open && (
        <button
          className="chat-widget-fab"
          onClick={() => setOpen(true)}
          aria-label="상담 열기"
          aria-expanded={false}
        >
          💬
        </button>
      )}
    </>
  );
}
