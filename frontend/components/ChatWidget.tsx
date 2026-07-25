"use client";

import Image from "next/image";
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
        <div className="chat-widget-popup" role="dialog" aria-label="당당 상담">
          <button className="chat-widget-close" onClick={() => setOpen(false)} aria-label="상담 닫기">✕</button>
          <ChatPanel />
        </div>
      )}
      <button
        className={`chat-widget-fab${open ? " is-open" : ""}`}
        onClick={() => setOpen((current) => !current)}
        aria-label={open ? "상담 접기" : "상담 열기"}
        aria-expanded={open}
      >
        <Image
          className="chat-widget-character"
          src="/dangdang-support.png"
          alt=""
          width={87}
          height={78}
          priority
          draggable={false}
        />
      </button>
    </>
  );
}
