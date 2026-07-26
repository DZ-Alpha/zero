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
        {/* quality={100}을 쓰지 않는다 - Next의 WebP 인코더가 이 PNG를 quality=100으로
            변환하면 색이 거의 다 날아간 흰색 유령 이미지가 된다(실측 확인, quality=75는
            정상). 기본 quality(75)가 이 이미지에서는 오히려 더 선명하다. */}
        <Image
          className="chat-widget-character"
          src="/dangdang-support.png"
          alt=""
          width={87}
          height={78}
          sizes="87px"
          priority
          draggable={false}
        />
      </button>
    </>
  );
}
