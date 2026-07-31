"use client";

import Image from "next/image";
import { useEffect, useRef, useState } from "react";
import { ChatPanel } from "@/components/ChatPanel";
import { useExitPresence } from "@/hooks/useDelayedClose";

// 2026-07-31 - 우하단 고정 위치를 롤백하면서, 대신 유저가 겹치는 화면에서
// 직접 아이콘을 끌어다 피할 수 있게 자유 드래그를 추가한다. 위치는 DB가
// 아니라 브라우저 쿠키에만 저장(계정 불필요, 서버 부담 없음).
const POS_COOKIE = "dd_chat_fab_pos";
const POS_COOKIE_DAYS = 365;
const DRAG_BREAKPOINT = 700; // globals.css .chat-widget-fab 모바일 분기와 동일
const EDGE_MARGIN = 8;
const DRAG_THRESHOLD = 4;

type Pos = { x: number; y: number };

function readPosCookie(): Pos | null {
  const match = document.cookie.match(new RegExp(`(?:^|; )${POS_COOKIE}=([^;]*)`));
  if (!match) return null;
  const [xRaw, yRaw] = decodeURIComponent(match[1]).split(",");
  const x = Number(xRaw);
  const y = Number(yRaw);
  return Number.isFinite(x) && Number.isFinite(y) ? { x, y } : null;
}

function writePosCookie(pos: Pos) {
  const expires = new Date(Date.now() + POS_COOKIE_DAYS * 86400000).toUTCString();
  document.cookie = `${POS_COOKIE}=${encodeURIComponent(`${pos.x},${pos.y}`)}; expires=${expires}; path=/; samesite=lax`;
}

function clampPos(x: number, y: number, width: number, height: number): Pos {
  const maxX = Math.max(EDGE_MARGIN, window.innerWidth - width - EDGE_MARGIN);
  const maxY = Math.max(EDGE_MARGIN, window.innerHeight - height - EDGE_MARGIN);
  return {
    x: Math.min(Math.max(x, EDGE_MARGIN), maxX),
    y: Math.min(Math.max(y, EDGE_MARGIN), maxY),
  };
}

export function ChatWidget() {
  const [open, setOpen] = useState(false);
  const { rendered: popupView, closing: popupClosing } = useExitPresence(open ? true : null);
  const [canDrag, setCanDrag] = useState(false);
  const [dragPos, setDragPos] = useState<Pos | null>(null);
  const [dragging, setDragging] = useState(false);

  const fabRef = useRef<HTMLButtonElement>(null);
  const dragStateRef = useRef<{ pointerId: number; startX: number; startY: number; originLeft: number; originTop: number; moved: boolean } | null>(null);
  const suppressClickRef = useRef(false);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [open]);

  // 데스크톱에서만 드래그 허용 - 모바일은 스크롤 제스처와 충돌해서 기본
  // 우하단 고정 위치를 그대로 쓴다(요청 사항).
  useEffect(() => {
    const update = () => setCanDrag(window.innerWidth > DRAG_BREAKPOINT);
    update();
    window.addEventListener("resize", update);
    return () => window.removeEventListener("resize", update);
  }, []);

  useEffect(() => {
    if (!canDrag) return;
    const saved = readPosCookie();
    if (!saved || !fabRef.current) return;
    const { offsetWidth, offsetHeight } = fabRef.current;
    setDragPos(clampPos(saved.x, saved.y, offsetWidth, offsetHeight));
  }, [canDrag]);

  useEffect(() => {
    if (!canDrag || !dragPos) return;
    const onResize = () => {
      if (!fabRef.current) return;
      const { offsetWidth, offsetHeight } = fabRef.current;
      setDragPos((current) => (current ? clampPos(current.x, current.y, offsetWidth, offsetHeight) : current));
    };
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [canDrag, !!dragPos]);

  function handlePointerDown(event: React.PointerEvent<HTMLButtonElement>) {
    if (!canDrag) return;
    const rect = event.currentTarget.getBoundingClientRect();
    event.currentTarget.setPointerCapture(event.pointerId);
    dragStateRef.current = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      originLeft: rect.left,
      originTop: rect.top,
      moved: false,
    };
  }

  function handlePointerMove(event: React.PointerEvent<HTMLButtonElement>) {
    const state = dragStateRef.current;
    if (!state || state.pointerId !== event.pointerId) return;
    const dx = event.clientX - state.startX;
    const dy = event.clientY - state.startY;
    if (!state.moved) {
      if (Math.hypot(dx, dy) < DRAG_THRESHOLD) return;
      state.moved = true;
      setDragging(true);
    }
    const { offsetWidth, offsetHeight } = event.currentTarget;
    setDragPos(clampPos(state.originLeft + dx, state.originTop + dy, offsetWidth, offsetHeight));
  }

  function handlePointerUp(event: React.PointerEvent<HTMLButtonElement>) {
    const state = dragStateRef.current;
    if (!state || state.pointerId !== event.pointerId) return;
    event.currentTarget.releasePointerCapture(event.pointerId);
    dragStateRef.current = null;
    if (state.moved) {
      setDragging(false);
      suppressClickRef.current = true;
      setDragPos((current) => {
        if (current) writePosCookie(current);
        return current;
      });
    }
  }

  function handleClick() {
    if (suppressClickRef.current) {
      suppressClickRef.current = false;
      return;
    }
    setOpen((current) => !current);
  }

  const effectivePos = canDrag ? dragPos : null;
  const fabWidth = fabRef.current?.offsetWidth ?? 87;
  const fabHeight = fabRef.current?.offsetHeight ?? 78;

  const fabStyle: React.CSSProperties | undefined = effectivePos
    ? { left: effectivePos.x, top: effectivePos.y, right: "auto", bottom: "auto" }
    : undefined;

  let popupStyle: React.CSSProperties | undefined;
  if (effectivePos && typeof window !== "undefined") {
    const onRightHalf = effectivePos.x + fabWidth / 2 > window.innerWidth / 2;
    const onBottomHalf = effectivePos.y + fabHeight / 2 > window.innerHeight / 2;
    popupStyle = {
      left: onRightHalf ? "auto" : effectivePos.x,
      right: onRightHalf ? window.innerWidth - (effectivePos.x + fabWidth) : "auto",
      top: onBottomHalf ? "auto" : effectivePos.y + fabHeight + 8,
      bottom: onBottomHalf ? window.innerHeight - effectivePos.y + 8 : "auto",
      transformOrigin: `${onBottomHalf ? "bottom" : "top"} ${onRightHalf ? "right" : "left"}`,
    };
  }

  return (
    <>
      {popupView && (
        <div className={`chat-widget-popup${popupClosing ? " is-closing" : ""}`} style={popupStyle} role="dialog" aria-label="당당 상담">
          <button className="chat-widget-close" onClick={() => setOpen(false)} aria-label="상담 닫기">✕</button>
          <ChatPanel />
        </div>
      )}
      <button
        ref={fabRef}
        className={`chat-widget-fab${open ? " is-open" : ""}${dragging ? " is-dragging" : ""}`}
        style={fabStyle}
        onClick={handleClick}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerCancel={handlePointerUp}
        aria-label={open ? "상담 접기" : "상담 열기(끌어서 위치 이동 가능)"}
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
